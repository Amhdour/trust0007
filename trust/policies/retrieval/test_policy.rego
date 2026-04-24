package retrieval.security_test

import data.retrieval.security


test_allow_with_trusted_labels if {
  input := {
    "tenant_id": "tenant-a",
    "source": "qdrant",
    "trust_labels": ["trusted"]
  }
  decision := security.decision with input as input
  decision.allow
  decision.mode == "allow"
}


test_degrade_without_trusted_labels if {
  input := {
    "tenant_id": "tenant-a",
    "source": "qdrant",
    "trust_labels": []
  }
  decision := security.decision with input as input
  decision.allow
  decision.mode == "degrade"
}


test_deny_for_unallowlisted_source if {
  input := {
    "tenant_id": "tenant-a",
    "source": "unknown",
    "trust_labels": ["trusted"]
  }
  decision := security.decision with input as input
  not decision.allow
  decision.mode == "deny"
}
