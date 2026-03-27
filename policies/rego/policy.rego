package umbrella.policy

import future.keywords.in

# Baseline policy sets (can be externalized later).
tool_allowlist := {"search", "retrieve", "summarize", "classify"}
confirmation_required_tools := {"email.send", "ticket.create", "payment.charge"}
forbidden_tools := {"shell.exec", "http.post.untrusted", "db.drop"}
forbidden_fields := {"ssn", "credit_card", "api_key", "password"}
retrieval_source_allowlist := {"qdrant", "docs", "kb"}
allowed_tenants := {"tenant-a", "tenant-b"}

kill_switch_enabled if {
  object.get(input, "kill_switch", false)
}

kill_switch_enabled if {
  object.get(object.get(input, "flags", {}), "kill_switch", false)
}

requested_tool := object.get(object.get(input, "tool", {}), "name", "")
requested_fields := object.get(input, "requested_fields", [])
retrieval_source := object.get(object.get(input, "retrieval", {}), "source", "")
retrieval_requested := object.get(object.get(input, "retrieval", {}), "needed", false)

request_tenant := object.get(object.get(input, "request", {}), "tenant", "")
root_tenant := object.get(input, "tenant", "")

tenant := root_tenant if root_tenant != ""
tenant := request_tenant if {
  root_tenant == ""
  request_tenant != ""
}

tenant_valid if {
  tenant != ""
  tenant in allowed_tenants
}

tool_requested if requested_tool != ""

tool_forbidden if {
  tool_requested
  requested_tool in forbidden_tools
}

tool_not_allowlisted if {
  tool_requested
  not requested_tool in tool_allowlist
  not requested_tool in confirmation_required_tools
  not requested_tool in forbidden_tools
}

confirmation_required if requested_tool in confirmation_required_tools

confirmation_provided if object.get(object.get(input, "tool", {}), "confirmed", false)

tool_confirmation_missing if {
  confirmation_required
  not confirmation_provided
}

forbidden_field_requested[field] if {
  field := requested_fields[_]
  field in forbidden_fields
}

retrieval_source_invalid if {
  retrieval_requested
  retrieval_source != ""
  not retrieval_source in retrieval_source_allowlist
}

tenant_missing if tenant == ""

tenant_invalid if {
  tenant != ""
  not tenant in allowed_tenants
}

violation["kill switch enabled"] if kill_switch_enabled
violation[msg] if {
  tool_forbidden
  msg := sprintf("forbidden tool: %s", [requested_tool])
}
violation[msg] if {
  tool_not_allowlisted
  msg := sprintf("tool not in allowlist: %s", [requested_tool])
}
violation[msg] if {
  tool_confirmation_missing
  msg := sprintf("tool requires confirmation: %s", [requested_tool])
}
violation[msg] if {
  field := forbidden_field_requested[_]
  msg := sprintf("forbidden field requested: %s", [field])
}
violation[msg] if {
  retrieval_source_invalid
  msg := sprintf("retrieval source not allowed: %s", [retrieval_source])
}
violation["tenant missing"] if tenant_missing
violation[msg] if {
  tenant_invalid
  msg := sprintf("tenant not allowed: %s", [tenant])
}

allow if count(violation) == 0

default_deny if not allow

rag_eligible if {
  retrieval_requested
  retrieval_source in retrieval_source_allowlist
  tenant_valid
  not kill_switch_enabled
}

fallback_to_rag if {
  tool_requested
  not allow
  rag_eligible
}

decision := {
  "allow": allow,
  "default_deny": default_deny,
  "fallback_to_rag": fallback_to_rag,
  "kill_switch": kill_switch_enabled,
  "reasons": sort([r | violation[r]]),
}
