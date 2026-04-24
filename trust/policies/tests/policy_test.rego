package umbrella.policy_test

import data.umbrella.policy

base_input := {
  "tenant": "tenant-a",
  "requested_fields": ["title"],
  "retrieval": {"needed": false, "source": "qdrant"}
}

test_allowlisted_tool_allowed if {
  decision := policy.decision with input as object.union(base_input, {"tool": {"name": "search"}})
  decision.allow
  not decision.default_deny
}

test_default_deny_when_tool_not_allowlisted if {
  decision := policy.decision with input as object.union(base_input, {"tool": {"name": "unknown.tool"}})
  not decision.allow
  decision.default_deny
  "tool not in allowlist: unknown.tool" in decision.reasons
}

test_forbidden_tool_denied if {
  decision := policy.decision with input as object.union(base_input, {"tool": {"name": "shell.exec"}})
  not decision.allow
  "forbidden tool: shell.exec" in decision.reasons
}

test_confirmation_required_tool_denied_without_confirmation if {
  decision := policy.decision with input as object.union(base_input, {"tool": {"name": "email.send"}})
  not decision.allow
  "tool requires confirmation: email.send" in decision.reasons
}

test_confirmation_required_tool_allowed_with_confirmation if {
  decision := policy.decision with input as object.union(base_input, {"tool": {"name": "email.send", "confirmed": true}})
  decision.allow
}

test_forbidden_fields_denied if {
  input_obj := object.union(base_input, {"tool": {"name": "search"}, "requested_fields": ["title", "ssn"]})
  decision := policy.decision with input as input_obj
  not decision.allow
  "forbidden field requested: ssn" in decision.reasons
}

test_retrieval_source_allowlist_enforced if {
  input_obj := object.union(base_input, {"tool": {"name": "search"}, "retrieval": {"needed": true, "source": "unknown-store"}})
  decision := policy.decision with input as input_obj
  not decision.allow
  "retrieval source not allowed: unknown-store" in decision.reasons
}

test_tenant_restriction_enforced if {
  decision := policy.decision with input as object.union(base_input, {"tenant": "tenant-z", "tool": {"name": "search"}})
  not decision.allow
  "tenant not allowed: tenant-z" in decision.reasons
}

test_fallback_to_rag_enabled_when_tool_blocked_and_retrieval_allowed if {
  input_obj := {
    "tenant": "tenant-a",
    "tool": {"name": "shell.exec"},
    "requested_fields": ["title"],
    "retrieval": {"needed": true, "source": "qdrant"}
  }
  decision := policy.decision with input as input_obj
  not decision.allow
  decision.fallback_to_rag
}

test_kill_switch_denies_all if {
  input_obj := object.union(base_input, {"kill_switch": true, "tool": {"name": "search"}, "retrieval": {"needed": true, "source": "qdrant"}})
  decision := policy.decision with input as input_obj
  not decision.allow
  decision.kill_switch
  not decision.fallback_to_rag
  "kill switch enabled" in decision.reasons
}
