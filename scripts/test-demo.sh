#!/usr/bin/env bash
set -euo pipefail

bash scripts/run-demo.sh

python - <<'PY'
import json
from pathlib import Path

events_path = Path('artifacts/demo/events.jsonl')
launch_path = Path('artifacts/demo/launch-gate.json')

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
