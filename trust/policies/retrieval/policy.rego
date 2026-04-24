package retrieval.security

default decision := {
  "allow": false,
  "mode": "deny",
  "reasons": ["default deny"],
}

source_allowlist := ["qdrant", "kb", "docs"]
trusted_labels := ["trusted", "verified", "internal"]
tenant_source_allow := {
  "tenant-a": ["qdrant", "kb"],
  "tenant-dashboard": ["qdrant", "kb"],
  "tenant-b": ["qdrant", "docs"],
}

kill_switch_enabled if {
  object.get(input, "kill_switch", false)
}

source_allowed if {
  source := object.get(input, "source", "")
  source in source_allowlist
}

tenant_source_allowed if {
  tenant := object.get(input, "tenant_id", "")
  source := object.get(input, "source", "")
  allowed_sources := object.get(tenant_source_allow, tenant, [])
  source in allowed_sources
}

untrusted_label_present if {
  labels := object.get(input, "trust_labels", [])
  some label in labels
  not label in trusted_labels
}

trusted_request if {
  labels := object.get(input, "trust_labels", [])
  count(labels) > 0
  not untrusted_label_present
}

decision := {
  "allow": false,
  "mode": "deny",
  "reasons": ["kill switch enabled"],
} if {
  kill_switch_enabled
}

decision := {
  "allow": false,
  "mode": "deny",
  "reasons": [sprintf("source not allowlisted: %s", [object.get(input, "source", "")])],
} if {
  not kill_switch_enabled
  not source_allowed
}

decision := {
  "allow": false,
  "mode": "deny",
  "reasons": [sprintf("tenant/source boundary violation: %s/%s", [object.get(input, "tenant_id", ""), object.get(input, "source", "")])],
} if {
  not kill_switch_enabled
  source_allowed
  not tenant_source_allowed
}

decision := {
  "allow": true,
  "mode": "degrade",
  "reasons": ["trust labels missing or untrusted; degraded retrieval mode"],
} if {
  not kill_switch_enabled
  source_allowed
  tenant_source_allowed
  not trusted_request
}

decision := {
  "allow": true,
  "mode": "allow",
  "reasons": [],
} if {
  not kill_switch_enabled
  source_allowed
  tenant_source_allowed
  trusted_request
}
