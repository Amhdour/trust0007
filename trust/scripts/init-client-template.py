#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil


TOKEN_PATTERN = re.compile(r"{{([A-Z0-9_]+)}}")
ENGAGEMENT_TRACKS = {"layer-retrofit", "secure-starter-kit", "launch-gate"}
TEMPLATE_VERSION = "client-template-v1"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    if not slug:
        raise ValueError("Client slug must contain at least one letter or number.")
    return slug


def _track_label(track: str) -> str:
    return track.replace("-", " ").title()


def _render_text(text: str, context: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in context:
            raise KeyError(f"Unknown template token: {key}")
        return context[key]

    rendered = TOKEN_PATTERN.sub(replace, text)
    unresolved = sorted(set(TOKEN_PATTERN.findall(rendered)))
    if unresolved:
        raise ValueError(f"Unresolved template tokens remain: {', '.join(unresolved)}")
    return rendered


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_context(
    *,
    client_name: str,
    client_slug: str,
    engagement_track: str,
    primary_runtime: str,
    output_overlay: str,
    tenant_id: str,
    keycloak_realm: str,
    qdrant_collection: str,
    vault_secret_path: str,
    policy_bundle_path: str,
    dashboard_brand: str,
) -> dict[str, str]:
    runtime_slug = _slugify(primary_runtime).replace("-", "_")
    return {
        "TEMPLATE_VERSION": TEMPLATE_VERSION,
        "CLIENT_NAME": client_name,
        "CLIENT_SLUG": client_slug,
        "TENANT_ID": tenant_id,
        "ENGAGEMENT_TRACK": engagement_track,
        "ENGAGEMENT_TRACK_LABEL": _track_label(engagement_track),
        "PRIMARY_RUNTIME": primary_runtime,
        "PRIMARY_RUNTIME_SLUG": runtime_slug,
        "OUTPUT_OVERLAY": output_overlay,
        "KEYCLOAK_REALM": keycloak_realm,
        "QDRANT_COLLECTION": qdrant_collection,
        "VAULT_SECRET_PATH": vault_secret_path,
        "POLICY_BUNDLE_PATH": policy_bundle_path,
        "DASHBOARD_BRAND": dashboard_brand,
    }


def _materialize_template(source_root: Path, output_root: Path, context: dict[str, str]) -> None:
    if not source_root.exists():
        raise FileNotFoundError(f"Template source not found: {source_root}")

    output_root.mkdir(parents=True, exist_ok=True)
    for source_path in sorted(source_root.rglob("*")):
        relative_path = source_path.relative_to(source_root)
        destination_path = output_root / relative_path
        if source_path.is_dir():
            destination_path.mkdir(parents=True, exist_ok=True)
            continue
        rendered = _render_text(source_path.read_text(encoding="utf-8"), context)
        _write_text(destination_path, rendered)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a tokenized client overlay scaffold from overlays/client-template/."
    )
    parser.add_argument("--client-name", required=True, help="Human-readable client name.")
    parser.add_argument("--client-slug", required=True, help="Stable slug used for the overlay directory.")
    parser.add_argument(
        "--engagement-track",
        default="secure-starter-kit",
        choices=sorted(ENGAGEMENT_TRACKS),
        help="Primary engagement track for this client template.",
    )
    parser.add_argument(
        "--primary-runtime",
        default="Onyx",
        help="Primary governed runtime label used in the generated scaffold. Defaults to the repo's reference runtime, Onyx.",
    )
    parser.add_argument(
        "--tenant-id",
        default="",
        help="Tenant identifier to embed in the scaffold. Defaults to tenant-<client-slug>.",
    )
    parser.add_argument(
        "--keycloak-realm",
        default="",
        help="Realm name placeholder. Defaults to <client-slug>-dev.",
    )
    parser.add_argument(
        "--qdrant-collection",
        default="",
        help="Retrieval collection placeholder. Defaults to <client-slug>_governed_docs.",
    )
    parser.add_argument(
        "--vault-secret-path",
        default="",
        help="Vault path placeholder. Defaults to secret/data/clients/<client-slug>/runtime.",
    )
    parser.add_argument(
        "--policy-bundle-path",
        default="",
        help="Policy bundle placeholder. Defaults to overlays/client-<client-slug>/policy/runtime-governance.json.",
    )
    parser.add_argument(
        "--dashboard-brand",
        default="",
        help="Dashboard brand string. Defaults to '<client-name> AI Trust & Security Readiness Control Plane'.",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Optional explicit output directory. Defaults to overlays/client-<client-slug>/.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing generated overlay directory if it already exists.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    source_root = repo_root / "overlays" / "client-template"
    client_slug = _slugify(args.client_slug)

    output_root = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else (repo_root / "overlays" / f"client-{client_slug}").resolve()
    )
    output_overlay = (
        str(output_root.relative_to(repo_root))
        if repo_root in output_root.parents or output_root == repo_root
        else str(output_root)
    )

    tenant_id = args.tenant_id.strip() or f"tenant-{client_slug}"
    keycloak_realm = args.keycloak_realm.strip() or f"{client_slug}-dev"
    qdrant_collection = args.qdrant_collection.strip() or f"{client_slug}_governed_docs"
    vault_secret_path = args.vault_secret_path.strip() or f"secret/data/clients/{client_slug}/runtime"
    policy_bundle_path = args.policy_bundle_path.strip() or f"{output_overlay}/policy/runtime-governance.json"
    dashboard_brand = args.dashboard_brand.strip() or f"{args.client_name.strip()} AI Trust & Security Readiness Control Plane"

    context = _build_context(
        client_name=args.client_name.strip(),
        client_slug=client_slug,
        engagement_track=args.engagement_track,
        primary_runtime=args.primary_runtime.strip(),
        output_overlay=output_overlay,
        tenant_id=tenant_id,
        keycloak_realm=keycloak_realm,
        qdrant_collection=qdrant_collection,
        vault_secret_path=vault_secret_path,
        policy_bundle_path=policy_bundle_path,
        dashboard_brand=dashboard_brand,
    )

    if output_root.exists():
        if not args.force:
            raise SystemExit(
                f"Refusing to overwrite existing output directory: {output_root}. Use --force to replace it."
            )
        shutil.rmtree(output_root)

    _materialize_template(source_root, output_root, context)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "template_version": TEMPLATE_VERSION,
        "template_source": str(source_root.relative_to(repo_root)),
        "output_overlay": output_overlay,
        "context": context,
    }
    manifest_path = output_root / "generated-from-template.json"
    _write_text(manifest_path, json.dumps(manifest, indent=2, sort_keys=True))

    print(f"Created client overlay scaffold at {output_root}")
    print(f"Manifest written to {manifest_path}")
    print("Next steps:")
    print("1. Replace scaffold policy, retrieval, secrets, and readiness placeholders with client-specific decisions.")
    print("2. Decide whether this engagement stays demo-only or must prove live identity, policy, retrieval, and launch-gate evidence.")
    print("3. Decide whether the generated overlay keeps the default reference runtime or swaps to another governed runtime profile.")
    print("4. Redirect evidence output paths before reusing any generated artifacts for a client demonstration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
