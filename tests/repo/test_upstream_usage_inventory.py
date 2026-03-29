from backend.integration_adapter.repository import list_upstream_component_paths, load_upstream_usage_inventory


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
