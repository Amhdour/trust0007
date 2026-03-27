package retrieval.security

# Initial framework-agnostic retrieval policy model.
# Local development baseline only.

default decision := {
  "allow": false,
  "mode": "deny",
  "reasons": ["default deny"],
}

source_allowlist := {"qdrant", "kb", "docs"}
trusted_labels := {"trusted", "verified", "internal"}

# Tenant/source boundaries (example baseline).
tenant_source_allow := {
  "tenant-a": {"qdrant", "kb"},
  "tenant-b": {"qdrant", "docs"},
}

kill_switch if object.get(input, "kill_switch", false)

source_allowed if {
  source := object.get(input, "source", "")
  source in source_allowlist
}

tenant_allowed_source if {
  tenant := object.get(input, "tenant_id", "")
  source := object.get(input, "source", "")
  source in object.get(tenant_source_allow, tenant, set())
}

trusted_request if {
  labels := object.get(input, "trust_labels", [])
  count(labels) > 0
  every l in labels { l in trusted_labels }
}

decision := {
  "allow": false,
  "mode": "deny",
  "reasons": ["kill switch enabled"],
} if kill_switch

decision := {
  "allow": false,
  "mode": "deny",
  "reasons": [sprintf("source not allowlisted: %s", [object.get(input, "source", "")])],
} if {
  not kill_switch
  not source_allowed
}

decision := {
  "allow": false,
  "mode": "deny",
  "reasons": [sprintf("tenant/source boundary violation: %s/%s", [object.get(input, "tenant_id", ""), object.get(input, "source", "")])],
} if {
  not kill_switch
  source_allowed
  not tenant_allowed_source
}

# Policy failure/degraded-trust behavior: allow retrieval in degraded mode
# if trust labels are missing/untrusted but boundaries pass.
decision := {
  "allow": true,
  "mode": "degrade",
  "reasons": ["trust labels missing or untrusted; degraded retrieval mode"],
} if {
  not kill_switch
  source_allowed
  tenant_allowed_source
  not trusted_request
}

decision := {
  "allow": true,
  "mode": "allow",
  "reasons": [],
} if {
  not kill_switch
  source_allowed
  tenant_allowed_source
  trusted_request
}
