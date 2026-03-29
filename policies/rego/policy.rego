package umbrella.policy

import future.keywords.if
import future.keywords.in

default decision := {
  "allow": false,
  "default_deny": true,
  "fallback_to_rag": false,
  "kill_switch": false,
  "matched_surface": "",
  "reason_codes": ["policy.default_deny"],
  "reasons": ["policy.default_deny"],
}

default matched_surface := ""

runtime_policy := object.get(input, "runtime_policy", {})
content_rules := object.get(runtime_policy, "content_rules", {})
tool_rules := object.get(runtime_policy, "tools", {})
retrieval_rules := object.get(runtime_policy, "retrieval", {})
surface_rules := object.get(object.get(runtime_policy, "surfaces", {}), "path_policies", [])
identity_rules := object.get(runtime_policy, "identity", {})

prompt := lower(object.get(input, "prompt", ""))
metadata := object.get(input, "metadata", {})
request_ctx := object.get(input, "request", {})
identity_ctx := object.get(input, "identity", {})
legacy_tool := object.get(object.get(input, "tool", {}), "name", "")
legacy_confirmed := object.get(object.get(input, "tool", {}), "confirmed", false)
legacy_requested_fields := object.get(input, "requested_fields", [])
requested_tools := object.get(input, "requested_tools", [])
requested_path := object.get(request_ctx, "path", object.get(metadata, "requested_path", ""))
requested_query := object.get(request_ctx, "query", object.get(metadata, "surface_query", {}))
retrieval_needed := object.get(object.get(input, "retrieval", {}), "needed", object.get(input, "retrieval_needed", false))
retrieval_source := object.get(object.get(input, "retrieval", {}), "source", object.get(input, "retrieval_source", ""))

allowed_tools := {tool | tool := object.get(tool_rules, "allowed_tools", [])[ _ ]}
confirmation_required_tools := {tool | tool := object.get(tool_rules, "confirmation_required_tools", [])[ _ ]}
forbidden_tools := {tool | tool := object.get(tool_rules, "forbidden_tools", [])[ _ ]}
fallback_forbidden_terms := {"hack", "exploit", "bypass"}
forbidden_terms := {term |
  term := lower(object.get(content_rules, "forbidden_terms", [])[ _ ])
} if count(object.get(content_rules, "forbidden_terms", [])) > 0
forbidden_terms := fallback_forbidden_terms if count(object.get(content_rules, "forbidden_terms", [])) == 0

requested_tool_names[tool] if {
  tool := requested_tools[_]
}
requested_tool_names[legacy_tool] if legacy_tool != ""

tenant := object.get(identity_ctx, "tenant_id", "") if object.get(identity_ctx, "tenant_id", "") != ""
tenant := object.get(input, "tenant_id", "") if {
  object.get(identity_ctx, "tenant_id", "") == ""
  object.get(input, "tenant_id", "") != ""
}
tenant := object.get(input, "tenant", "") if {
  object.get(identity_ctx, "tenant_id", "") == ""
  object.get(input, "tenant_id", "") == ""
}

roles[role] if {
  role := object.get(identity_ctx, "roles", [])[ _ ]
}
roles[role] if {
  count(object.get(identity_ctx, "roles", [])) == 0
  role := object.get(metadata, "identity_roles", [])[ _ ]
}

requested_fields[field] if {
  field := legacy_requested_fields[_]
}

kill_switch_enabled if {
  object.get(input, "kill_switch", false)
}

kill_switch_enabled if {
  object.get(object.get(input, "flags", {}), "kill_switch", false)
}

tenant_missing if tenant == ""

allowed_tenants[tenant_id] if {
  tenant_id := object.keys(object.get(identity_rules, "tenant_roles", {}))[ _ ]
}
allowed_tenants[tenant_id] if {
  count(object.keys(object.get(identity_rules, "tenant_roles", {}))) == 0
  tenant_id := {"tenant-a", "tenant-b"}[_]
}

tenant_invalid if {
  tenant != ""
  not tenant in allowed_tenants
}

live_identity_required if lower(object.get(request_ctx, "evidence_mode", object.get(metadata, "evidence_mode", ""))) == "live"

identity_not_live if {
  live_identity_required
  lower(object.get(identity_ctx, "source", object.get(metadata, "identity_source", ""))) != "keycloak_userinfo"
}

forbidden_prompt_term if {
  term := forbidden_terms[_]
  contains(prompt, term)
}

tool_confirmation_missing[tool] if {
  tool := requested_tool_names[_]
  tool in confirmation_required_tools
  not legacy_confirmed
}

tool_forbidden[tool] if {
  tool := requested_tool_names[_]
  tool in forbidden_tools
}

tool_not_allowlisted[tool] if {
  tool := requested_tool_names[_]
  not tool in allowed_tools
  not tool in confirmation_required_tools
  not tool in forbidden_tools
}

retrieval_source_invalid if {
  retrieval_needed
  tenant != ""
  allowed_sources := object.get(retrieval_rules, "tenant_allowed_sources", {})
  tenant_sources := object.get(allowed_sources, tenant, [])
  not retrieval_source in {source | source := tenant_sources[_]}
}

matches_surface(rule) if {
  rule := surface_rules[_]
  requested_path == object.get(rule, "path", "")
  expected_query := object.get(rule, "query", {})
  every pair in object.keys(expected_query) {
    object.get(requested_query, pair, "") == object.get(expected_query, pair, "")
  }
}

matched_surface := object.get(rule, "surface", "") if {
  matches_surface(rule)
}

surface_not_registered if {
  requested_path != ""
  matched_surface == ""
}

surface_role_denied if {
  matched_surface != ""
  rule := surface_rules[_]
  matches_surface(rule)
  allowed_roles := object.get(rule, "allowed_roles", [])
  count(allowed_roles) > 0
  not any_allowed_role(allowed_roles)
}

any_allowed_role(allowed_roles) if {
  some index
  role := allowed_roles[index]
  role in roles
}

role_not_allowed[role] if {
  allowed_tenant_roles := object.get(object.get(identity_rules, "tenant_roles", {}), tenant, [])
  count(allowed_tenant_roles) > 0
  role := roles[_]
  not role in allowed_tenant_roles
}

violation["policy.kill_switch_enabled"] if kill_switch_enabled
violation["policy.forbidden_content"] if forbidden_prompt_term
violation["tenant.missing"] if tenant_missing
violation[msg] if {
  tenant_invalid
  msg := sprintf("tenant.not_allowed:%s", [tenant])
}
violation["identity.source_not_live"] if identity_not_live
violation[msg] if {
  role := role_not_allowed[_]
  msg := sprintf("policy.identity_role_not_allowed:%s", [role])
}
violation[msg] if {
  surface_not_registered
  msg := sprintf("policy.surface_not_registered:%s", [requested_path])
}
violation[msg] if {
  surface_role_denied
  msg := sprintf("policy.surface_role_denied:%s", [matched_surface])
}
violation[msg] if {
  tool := tool_forbidden[_]
  msg := sprintf("tool.forbidden:%s", [tool])
}
violation[msg] if {
  tool := tool_not_allowlisted[_]
  msg := sprintf("tool.not_allowed:%s", [tool])
}
violation[msg] if {
  tool := tool_confirmation_missing[_]
  msg := sprintf("tool.confirmation_required:%s", [tool])
}
violation[msg] if {
  field := requested_fields[_]
  field in {"ssn", "credit_card", "api_key", "password"}
  msg := sprintf("field.forbidden:%s", [field])
}
violation[msg] if {
  retrieval_source_invalid
  msg := sprintf("retrieval.source_not_allowed:%s", [retrieval_source])
}

allow if count(violation) == 0

default_deny if not allow

rag_eligible if {
  retrieval_needed
  retrieval_source != ""
  tenant != ""
  not kill_switch_enabled
}

fallback_to_rag if {
  some code in violation
  startswith(code, "tool.")
  rag_eligible
}

decision := {
  "allow": allow,
  "default_deny": default_deny,
  "fallback_to_rag": fallback_to_rag,
  "kill_switch": kill_switch_enabled,
  "matched_surface": matched_surface,
  "reason_codes": sort([code | violation[code]]),
  "reasons": sort([code | violation[code]]),
}
