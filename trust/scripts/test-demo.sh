#!/usr/bin/env bash
set -euo pipefail

ARTIFACT_DIR="${CONTROL_PLANE_DEMO_ARTIFACTS_DIR:-artifacts/demo}"

bash scripts/run-demo.sh

ARTIFACT_DIR="$ARTIFACT_DIR" python - <<'PY'
import json
import os
from pathlib import Path

artifact_dir = Path(os.environ['ARTIFACT_DIR'])
events_path = artifact_dir / 'events.jsonl'
launch_path = artifact_dir / 'launch-gate.json'

assert events_path.exists(), 'missing events artifact'
assert launch_path.exists(), 'missing launch-gate artifact'

lines = [json.loads(x) for x in events_path.read_text().splitlines() if x.strip()]
required = {
    'request.start',
    'identity.established',
    'policy.decision',
    'retrieval.decision',
    'tool.decision',
    'tool.execution_attempt',
    'request.end',
}
seen = {x['event_type'] for x in lines}
missing = required - seen
assert not missing, f'missing required demo events: {missing}'

launch = json.loads(launch_path.read_text())
assert launch['machine']['decision'] in {'pass', 'conditional_go', 'no_go'}
assert 'human' in launch
print('demo test checks passed')
PY
