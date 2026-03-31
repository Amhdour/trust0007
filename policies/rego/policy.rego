package umbrella.policy

default decision := {
  "allow": false,
  "default_deny": true,
  "fallback_to_rag": false,
  "kill_switch": false,
  "matched_surface": "",
  "reason_codes": ["policy.default_deny"],
  "reasons": ["policy.default_deny"],
}

runtime_policy := object.get(input, "runtime_policy", {})
content_rules := object.get(runtime_policy, "content_rules", {})
tool_rules := object.get(runtime_policy, "tools", {})
surface_rules := object.get(object.get(runtime_policy, "surfaces", {}), "path_policies", [])
identity_rules := object.get(runtime_policy, "identity", {})
retrieval_rules := object.get(runtime_policy, "retrieval", {})

request_ctx := object.get(input, "request", {})
identity_ctx := object.get(input, "identity", {})
metadata := object.get(input, "metadata", {})
retrieval_ctx := object.get(input, "retrieval", {})

requested_path := object.get(request_ctx, "path", object.get(metadata, "requested_path", ""))
requested_query := object.get(request_ctx, "query", object.get(metadata, "surface_query", {}))
requested_tools := object.get(input, "requested_tools", [])
retrieval_needed := object.get(retrieval_ctx, "needed", object.get(input, "retrieval_needed", false))
retrieval_source := object.get(retrieval_ctx, "source", object.get(input, "retrieval_source", ""))
prompt := lower(object.get(input, "prompt", ""))
requested_evidence_mode := lower(object.get(request_ctx, "evidence_mode", object.get(metadata, "evidence_mode", "")))
identity_source := lower(object.get(identity_ctx, "source", object.get(metadata, "identity_source", "")))

resolved_tenant := tenant if {
  tenant := object.get(identity_ctx, "tenant_id", "")
  tenant != ""
} else := tenant if {
  tenant := object.get(input, "tenant_id", "")
  tenant != ""
} else := ""

identity_roles := roles if {
  roles := object.get(identity_ctx, "roles", [])
  count(roles) > 0
} else := object.get(metadata, "identity_roles", [])

forbidden_terms := terms if {
  terms := object.get(content_rules, "forbidden_terms", [])
  count(terms) > 0
} else := ["hack", "exploit", "bypass"]

tenant_role_allowlist := object.get(object.get(identity_rules, "tenant_roles", {}), resolved_tenant, [])
allowed_retrieval_sources := object.get(object.get(retrieval_rules, "tenant_allowed_sources", {}), resolved_tenant, [])
allowed_tools := object.get(tool_rules, "allowed_tools", [])
confirmation_required_tools := object.get(tool_rules, "confirmation_required_tools", [])
forbidden_tools := object.get(tool_rules, "forbidden_tools", [])

default matched_surface := ""

matched_surface := surface if {
  some rule in surface_rules
  object.get(rule, "path", "") == requested_path
  surface := object.get(rule, "surface", "")
  surface != ""
  query_matches(rule)
}

default matched_surface_allowed_roles := []

matched_surface_allowed_roles := roles if {
  some rule in surface_rules
  object.get(rule, "path", "") == requested_path
  object.get(rule, "surface", "") == matched_surface
  query_matches(rule)
  roles := object.get(rule, "allowed_roles", [])
}

query_matches(rule) if {
  expected_query := object.get(rule, "query", {})
  count(object.keys(expected_query)) == 0
}

query_matches(rule) if {
  expected_query := object.get(rule, "query", {})
  count(object.keys(expected_query)) > 0
  not query_mismatch(rule)
}

query_mismatch(rule) if {
  expected_query := object.get(rule, "query", {})
  some key in object.keys(expected_query)
  object.get(requested_query, key, "") != object.get(expected_query, key, "")
}

tenant_present if {
  resolved_tenant != ""
}

live_identity_satisfied if {
  requested_evidence_mode != "live"
}

live_identity_satisfied if {
  requested_evidence_mode == "live"
  identity_source == "keycloak_userinfo"
}

forbidden_content_detected if {
  some term in forbidden_terms
  contains(prompt, lower(term))
}

surface_registered if {
  requested_path == ""
}

surface_registered if {
  matched_surface != ""
}

surface_role_allowed if {
  count(matched_surface_allowed_roles) == 0
}

surface_role_allowed if {
  some role in identity_roles
  role in matched_surface_allowed_roles
}

tenant_role_allowed if {
  count(tenant_role_allowlist) == 0
}

tenant_role_allowed if {
  some role in identity_roles
  role in tenant_role_allowlist
}

retrieval_source_allowed if {
  not retrieval_needed
}

retrieval_source_allowed if {
  retrieval_needed
  retrieval_source == ""
}

retrieval_source_allowed if {
  retrieval_needed
  retrieval_source != ""
  retrieval_source in allowed_retrieval_sources
}

forbidden_tool_used if {
  some tool in requested_tools
  tool in forbidden_tools
}

unallowlisted_tool_used if {
  some tool in requested_tools
  not tool in allowed_tools
  not tool in confirmation_required_tools
  not tool in forbidden_tools
}

allow if {
  tenant_present
  live_identity_satisfied
  not forbidden_content_detected
  surface_registered
  surface_role_allowed
  tenant_role_allowed
  retrieval_source_allowed
  not forbidden_tool_used
  not unallowlisted_tool_used
}

reason_code := "tenant.missing" if {
  not tenant_present
} else := "identity.source_not_live" if {
  not live_identity_satisfied
} else := "policy.forbidden_content" if {
  forbidden_content_detected
} else := sprintf("policy.surface_not_registered:%s", [requested_path]) if {
  not surface_registered
  requested_path != ""
} else := sprintf("policy.surface_role_denied:%s", [matched_surface]) if {
  surface_registered
  not surface_role_allowed
  matched_surface != ""
} else := sprintf("policy.identity_role_not_allowed:%s", [role]) if {
  not tenant_role_allowed
  some role in identity_roles
  not role in tenant_role_allowlist
} else := sprintf("retrieval.source_not_allowed:%s", [retrieval_source]) if {
  not retrieval_source_allowed
  retrieval_source != ""
} else := sprintf("tool.forbidden:%s", [tool]) if {
  some tool in requested_tools
  tool in forbidden_tools
} else := sprintf("tool.not_allowed:%s", [tool]) if {
  some tool in requested_tools
  not tool in allowed_tools
  not tool in confirmation_required_tools
  not tool in forbidden_tools
} else := "policy.default_deny"

decision := {
  "allow": true,
  "default_deny": false,
  "fallback_to_rag": false,
  "kill_switch": false,
  "matched_surface": matched_surface,
  "reason_codes": ["policy.allow"],
  "reasons": ["policy.allow"],
} if {
  allow
}

decision := {
  "allow": false,
  "default_deny": true,
  "fallback_to_rag": false,
  "kill_switch": false,
  "matched_surface": matched_surface,
  "reason_codes": [reason_code],
  "reasons": [reason_code],
} if {
  not allow
}
