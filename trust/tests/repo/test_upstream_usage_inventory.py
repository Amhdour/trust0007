from backend.integration_adapter.repository import (
    list_upstream_component_paths,
    load_upstream_source_lock,
    load_upstream_usage_inventory,
)


def test_upstream_inventory_covers_every_vendored_component_once() -> None:
    inventory = load_upstream_usage_inventory()
    components = inventory["components"]
    repo_paths = list_upstream_component_paths()
    classified_paths = [component["upstream_path"] for component in components]

    assert sorted(classified_paths) == repo_paths
    assert len(classified_paths) == len(set(classified_paths))
    assert inventory["audit"]["inventory_covers_all_upstreams"] is True


def test_upstream_inventory_components_include_required_reviewer_fields() -> None:
    inventory = load_upstream_usage_inventory()

    for component in inventory["components"]:
        assert component["component_name"]
        assert component["classification"] in {"used_now", "partially_used", "optional_future", "reference_only"}
        assert component["runtime_path_status"] in {"mandatory", "supporting", "optional", "reference"}
        assert component["runtime_role"]
        assert component["runtime_location"]
        assert component["necessity_rationale"]
        assert component["governance_signals"]
        assert component["evidence_artifacts"]
        assert component["missing_integration_depth"]
        assert component["removal_impact"]
        assert component["checkout_policy"] in {"default", "opt_in"}
        assert component["integration_decision"] in {"active_now", "platform_only", "opt_in_only", "reference_only"}
        assert component["provenance_mode"] in {
            "content_fingerprint",
            "manual_pin",
            "standalone_git_pin",
            "manual_pin+content_fingerprint",
            "standalone_git_pin+content_fingerprint",
        }
        assert "source_ref" in component
        assert "source_commit" in component
        assert component["snapshot_fingerprint"]
        assert component["snapshot_file_count"] > 0
        assert component["snapshot_bytes"] > 0


def test_upstream_source_lock_covers_every_vendored_component_once() -> None:
    lock_manifest = load_upstream_source_lock()
    repo_paths = list_upstream_component_paths()
    declared_paths = [component["upstream_path"] for component in lock_manifest["components"]]

    assert sorted(declared_paths) == repo_paths
    assert len(declared_paths) == len(set(declared_paths))
    assert lock_manifest["audit"]["lock_covers_all_upstreams"] is True
    assert lock_manifest["managed_submodules"] == ["overlays/myStarterKit"]
    assert lock_manifest["audit"]["checkout_policies_consistent"] is True
    assert lock_manifest["audit"]["integration_decisions_consistent"] is True
    assert lock_manifest["audit"]["envoy_platform_only_locked"] is True
    assert lock_manifest["pin_coverage"]["total_count"] == len(repo_paths)
    assert isinstance(lock_manifest["pin_coverage"]["pinned_count"], int)
    assert lock_manifest["audit"]["fingerprints_complete"] is True
    assert lock_manifest["provenance_coverage"]["fingerprinted_count"] == len(repo_paths)


def test_upstream_inventory_and_lock_manifest_stay_aligned() -> None:
    inventory = load_upstream_usage_inventory()

    assert inventory["tracking_model"]["lock_path"] == "evidence/upstream.lock.json"
    assert inventory["tracking_model"]["managed_submodules"] == ["overlays/myStarterKit"]
    assert inventory["tracking_model"]["opt_in_checkout_paths"]
    assert "Envoy" in inventory["tracking_model"]["platform_only_components"]
    assert isinstance(inventory["tracking_model"]["pinned_source_count"], int)
    assert inventory["tracking_model"]["total_source_count"] == len(list_upstream_component_paths())
    assert inventory["tracking_model"]["fingerprinted_source_count"] == len(list_upstream_component_paths())
    assert inventory["audit"]["lock_consistent"] is True
    assert inventory["audit"]["checkout_policies_consistent"] is True
    assert inventory["audit"]["integration_decisions_consistent"] is True
    assert inventory["audit"]["envoy_platform_only_locked"] is True
    assert inventory["audit"]["fingerprints_complete"] is True
