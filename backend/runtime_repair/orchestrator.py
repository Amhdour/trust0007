from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.trust_readiness.readiness import compute_fleet_readiness, compute_runtime_readiness

from .diagnostics.base import DiagnosticContext
from .diagnostics.dify import DifyDiagnosticAdapter
from .diagnostics.onyx import OnyxDiagnosticAdapter
from .enums import RemediationStatus, RepairMode, RepairRunStatus, RuntimeLane
from .models import DiagnosticReport, RemediationPlan, RepairRun, iso_now, new_id
from .policies import RepairPolicyEngine
from .remediations.actions import actions_for_findings, execute_remediation_action
from .store import AUDIT_RECORDS_PATH, REPAIR_EVENTS_PATH, RepairArtifactStore


class GovernedRuntimeRepairOrchestrator:
    def __init__(self, root: Path | None = None, *, policy_engine: RepairPolicyEngine | None = None) -> None:
        self.root = root
        self.policy_engine = policy_engine or RepairPolicyEngine.from_repo(root)
        self.store = RepairArtifactStore(root)

    def diagnose(
        self,
        lane: RuntimeLane,
        *,
        tenant_id: str,
        actor_id: str,
        correlation_id: str = "",
        environment: str = "dev",
        prober=None,
    ) -> DiagnosticReport:
        context = DiagnosticContext(
            tenant_id=tenant_id,
            actor_id=actor_id,
            correlation_id=correlation_id or new_id("repair-correlation"),
            root=self.root,
            environment=environment,
            prober=prober,
        )
        adapter = self._adapter(lane)
        report = adapter.diagnose(context)
        self.store.save_report(report.to_dict())
        self._audit(
            event_type="runtime_repair.diagnose",
            lane=lane,
            tenant_id=tenant_id,
            actor_id=actor_id,
            runtime_id=report.runtime_id,
            correlation_id=report.correlation_id,
            decision_id=context.decision_id,
            result="diagnosed",
            reason_codes=[reason for finding in report.findings for reason in finding.reason_codes] or ["repair.diagnosed"],
            details={"report_id": report.report_id, "finding_count": len(report.findings)},
        )
        return report

    def plan(
        self,
        lane: RuntimeLane,
        *,
        tenant_id: str,
        actor_id: str,
        actor_roles: list[str] | None = None,
        correlation_id: str = "",
        environment: str = "dev",
        approved_actions: list[str] | None = None,
        prober=None,
    ) -> RemediationPlan:
        report = self.diagnose(
            lane,
            tenant_id=tenant_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            environment=environment,
            prober=prober,
        )
        approved = set(approved_actions or [])
        actions = actions_for_findings(lane, report.findings)
        evidence_mode = str(report.readiness_before.get("signals", [{}])[0].get("details", {}).get("evidence_mode", "live"))
        decisions = [
            self.policy_engine.evaluate_action(
                action,
                tenant_id=tenant_id,
                actor_id=actor_id,
                actor_roles=actor_roles or [],
                environment=environment,
                approved=action.action_id in approved,
                evidence_mode=evidence_mode,
            )
            for action in actions
        ]
        allowed_count = sum(1 for decision in decisions if decision.allow)
        plan = RemediationPlan(
            plan_id=new_id("repair-plan"),
            report_id=report.report_id,
            lane=lane,
            tenant_id=tenant_id,
            runtime_id=report.runtime_id,
            correlation_id=report.correlation_id,
            actor_id=actor_id,
            generated_at=iso_now(),
            actions=actions,
            policy_decisions=decisions,
            findings=report.findings,
            readiness_before=report.readiness_before,
            summary=f"Planned {len(actions)} remediation action(s); {allowed_count} are policy-allowed for execution.",
        )
        self.store.save_plan(plan.to_dict())
        self._audit(
            event_type="runtime_repair.plan",
            lane=lane,
            tenant_id=tenant_id,
            actor_id=actor_id,
            runtime_id=plan.runtime_id,
            correlation_id=plan.correlation_id,
            decision_id=",".join(decision.decision_id for decision in decisions),
            result="planned",
            reason_codes=[reason for decision in decisions for reason in decision.reason_codes],
            details={"plan_id": plan.plan_id, "allowed_action_count": allowed_count},
        )
        return plan

    def run(
        self,
        lane: RuntimeLane,
        *,
        mode: RepairMode,
        tenant_id: str,
        actor_id: str,
        actor_roles: list[str] | None = None,
        correlation_id: str = "",
        environment: str = "dev",
        approved_actions: list[str] | None = None,
        action_id: str = "",
        dry_run: bool = False,
        prober=None,
    ) -> RepairRun:
        started_at = iso_now()
        readiness_before = compute_runtime_readiness(self.root, runtime_id=lane.value).to_dict()
        report: DiagnosticReport | None = None
        plan: RemediationPlan | None = None
        results = []

        if mode == RepairMode.DIAGNOSE:
            report = self.diagnose(lane, tenant_id=tenant_id, actor_id=actor_id, correlation_id=correlation_id, environment=environment, prober=prober)
            status = RepairRunStatus.DIAGNOSED
            summary = report.summary
        else:
            plan = self.plan(
                lane,
                tenant_id=tenant_id,
                actor_id=actor_id,
                actor_roles=actor_roles,
                correlation_id=correlation_id,
                environment=environment,
                approved_actions=approved_actions,
                prober=prober,
            )
            report = DiagnosticReport(
                report_id=plan.report_id,
                lane=plan.lane,
                tenant_id=plan.tenant_id,
                runtime_id=plan.runtime_id,
                correlation_id=plan.correlation_id,
                actor_id=plan.actor_id,
                generated_at=plan.generated_at,
                findings=plan.findings,
                evidence_refs={},
                readiness_before=plan.readiness_before,
                summary=plan.summary,
            )
            if mode == RepairMode.PLAN:
                status = RepairRunStatus.PLANNED
                summary = plan.summary
            else:
                run_id = new_id("repair-run")
                target_actions = plan.actions
                if mode == RepairMode.EXECUTE_ACTION and action_id:
                    target_actions = [action for action in plan.actions if action.action_id == action_id]
                decision_by_action = {decision.action_id: decision for decision in plan.policy_decisions}
                for action in target_actions:
                    decision = decision_by_action.get(action.action_id)
                    if decision is None or not decision.allow:
                        results.append(
                            self._blocked_result(
                                run_id=run_id,
                                action_id=action.action_id,
                                lane=lane,
                                tenant_id=tenant_id,
                                runtime_id=plan.runtime_id,
                                correlation_id=plan.correlation_id,
                                actor_id=actor_id,
                                decision_id=decision.decision_id if decision else "",
                                reason_codes=decision.reason_codes if decision else ["repair.policy.missing_decision"],
                            )
                        )
                        continue
                    if mode == RepairMode.EXECUTE_SAFE and not action.safe_to_auto_execute:
                        results.append(
                            self._blocked_result(
                                run_id=run_id,
                                action_id=action.action_id,
                                lane=lane,
                                tenant_id=tenant_id,
                                runtime_id=plan.runtime_id,
                                correlation_id=plan.correlation_id,
                                actor_id=actor_id,
                                decision_id=decision.decision_id,
                                reason_codes=["repair.action_not_safe_for_auto_execute"],
                            )
                        )
                        continue
                    results.append(
                        execute_remediation_action(
                            action,
                            repair_run_id=run_id,
                            tenant_id=tenant_id,
                            runtime_id=plan.runtime_id,
                            correlation_id=plan.correlation_id,
                            actor_id=actor_id,
                            decision_id=decision.decision_id,
                            root=self.root,
                            dry_run=dry_run or mode == RepairMode.DRY_RUN,
                            findings=plan.findings,
                        )
                    )
                if not results:
                    status = RepairRunStatus.BLOCKED
                elif any(result.status == RemediationStatus.EXECUTED for result in results):
                    status = RepairRunStatus.EXECUTED if all(result.status in {RemediationStatus.EXECUTED, RemediationStatus.DRY_RUN} for result in results) else RepairRunStatus.PARTIAL
                elif any(result.status == RemediationStatus.DRY_RUN for result in results):
                    status = RepairRunStatus.DRY_RUN
                else:
                    status = RepairRunStatus.BLOCKED
                summary = f"Repair execution produced {len(results)} action result(s); status={status.value}."

        readiness_after = compute_runtime_readiness(self.root, runtime_id=lane.value).to_dict()
        completed_at = iso_now()
        run = RepairRun(
            run_id=locals().get("run_id", new_id("repair-run")),
            mode=mode,
            lane=lane,
            tenant_id=tenant_id,
            runtime_id=lane.value,
            correlation_id=(plan.correlation_id if plan else report.correlation_id if report else correlation_id or new_id("repair-correlation")),
            actor_id=actor_id,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            report=report,
            plan=plan,
            execution_results=results,
            readiness_before=readiness_before,
            readiness_after=readiness_after,
            audit_refs=[AUDIT_RECORDS_PATH],
            evidence_refs=[REPAIR_EVENTS_PATH],
            summary=summary,
        )
        self.store.save_run(run.to_dict())
        self._audit(
            event_type="runtime_repair.run",
            lane=lane,
            tenant_id=tenant_id,
            actor_id=actor_id,
            runtime_id=lane.value,
            correlation_id=run.correlation_id,
            decision_id=",".join(result.decision_id for result in results),
            result=status.value,
            reason_codes=[reason for result in results for reason in result.reason_codes] or ["repair.run.completed"],
            details={"run_id": run.run_id, "mode": mode.value, "readiness_after": readiness_after},
        )
        return run

    def fleet_repair_status(self, *, tenant_id: str = "tenant-a") -> dict[str, Any]:
        readiness = {item.runtime_id: item for item in compute_fleet_readiness(self.root)}
        reports = self.store.reports()
        plans = self.store.plans()
        runs = self.store.runs()
        lanes = []
        for lane in RuntimeLane:
            latest_report = next((item for item in reports if item.get("lane") == lane.value), None)
            latest_plan = next((item for item in plans if item.get("lane") == lane.value), None)
            latest_run = next((item for item in runs if item.get("lane") == lane.value), None)
            safe_candidates = []
            blocked = []
            if latest_plan:
                decisions = {item.get("action_id"): item for item in latest_plan.get("policy_decisions", [])}
                for action in latest_plan.get("actions", []):
                    decision = decisions.get(action.get("action_id"), {})
                    if action.get("safe_to_auto_execute") and decision.get("allow"):
                        safe_candidates.append(action)
                    if not decision.get("allow", False):
                        blocked.append({"action": action, "decision": decision})
            lanes.append(
                {
                    "lane": lane.value,
                    "tenant_id": tenant_id,
                    "runtime_id": lane.value,
                    "generated_at": iso_now(),
                    "readiness": readiness[lane.value].to_dict(),
                    "latest_report": latest_report,
                    "latest_plan": latest_plan,
                    "latest_run": latest_run,
                    "safe_auto_remediation_candidates": safe_candidates,
                    "blocked_remediation_attempts": blocked,
                    "audit_refs": [AUDIT_RECORDS_PATH],
                }
            )
        return {
            "page": "Repair Center / Governed Runtime Repair",
            "generated_at": iso_now(),
            "lanes": lanes,
            "recent_repair_runs": runs[:25],
            "remediation_plans": plans[:25],
            "latest_findings_by_lane": {lane.value: next((item.get("findings", []) for item in reports if item.get("lane") == lane.value), []) for lane in RuntimeLane},
        }

    def _adapter(self, lane: RuntimeLane):
        return OnyxDiagnosticAdapter() if lane == RuntimeLane.ONYX else DifyDiagnosticAdapter()

    def _blocked_result(
        self,
        *,
        run_id: str,
        action_id: str,
        lane: RuntimeLane,
        tenant_id: str,
        runtime_id: str,
        correlation_id: str,
        actor_id: str,
        decision_id: str,
        reason_codes: list[str],
    ):
        from .models import RepairExecutionResult
        from .enums import FreshnessStatus

        now = iso_now()
        return RepairExecutionResult(
            result_id=new_id("repair-result"),
            repair_run_id=run_id,
            action_id=action_id,
            lane=lane,
            tenant_id=tenant_id,
            runtime_id=runtime_id,
            correlation_id=correlation_id,
            actor_id=actor_id,
            decision_id=decision_id,
            status=RemediationStatus.POLICY_DENIED,
            result="blocked by repair policy",
            reason_codes=reason_codes,
            evidence_refs=[],
            started_at=now,
            completed_at=now,
            freshness=FreshnessStatus.FRESH,
        )

    def _audit(
        self,
        *,
        event_type: str,
        lane: RuntimeLane,
        tenant_id: str,
        actor_id: str,
        runtime_id: str,
        correlation_id: str,
        decision_id: str,
        result: str,
        reason_codes: list[str],
        details: dict[str, Any],
    ) -> None:
        record = {
            "event_type": event_type,
            "action": event_type,
            "repair_run_id": details.get("run_id", ""),
            "correlation_id": correlation_id,
            "trace_id": correlation_id,
            "tenant_id": tenant_id,
            "actor_id": actor_id,
            "lane": lane.value,
            "runtime_id": runtime_id,
            "decision_id": decision_id,
            "action_id": details.get("action_id", ""),
            "result": result,
            "outcome": result,
            "reason_codes": reason_codes,
            "timestamps": {"captured_at": iso_now()},
            "timestamp": iso_now(),
            "freshness": "fresh",
            "trace_links": [],
            "source_references": [REPAIR_EVENTS_PATH],
            "details": details,
        }
        self.store.append_audit(record)
        self.store.append_event(record)
