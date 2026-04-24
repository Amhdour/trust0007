#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
PROOF_DIR = ARTIFACTS / "proof-pack"
MANIFEST = PROOF_DIR / "manifest.json"

FILES_TO_CAPTURE = [
    Path("artifacts/smoke-junit.xml"),
    Path("artifacts/integration-junit.xml"),
    Path("artifacts/opa-report.json"),
    Path("artifacts/sbom-cyclonedx.json"),
    Path("artifacts/pip-audit.json"),
    Path("artifacts/reason-codes-summary.txt"),
    Path("overlays/myStarterKit/artifacts/governed-flow-summary.json"),
    Path("overlays/myStarterKit/artifacts/launch-gate-result.json"),
    Path("overlays/myStarterKit/artifacts/onyx-runtime-proof.json"),
    Path("overlays/myStarterKit/artifacts/onyx-agent-runtime-proof.json"),
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    PROOF_DIR.mkdir(parents=True, exist_ok=True)

    entries: list[dict[str, object]] = []
    for rel in FILES_TO_CAPTURE:
        src = ROOT / rel
        if not src.exists():
            continue

        dst = PROOF_DIR / rel.name
        dst.write_bytes(src.read_bytes())
        entries.append(
            {
                "source": str(rel),
                "copied_to": str(dst.relative_to(ROOT)),
                "size_bytes": dst.stat().st_size,
                "sha256": _sha256(dst),
            }
        )

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": "trust0007",
        "bundle": str(PROOF_DIR.relative_to(ROOT)),
        "files": entries,
        "file_count": len(entries),
    }
    MANIFEST.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"proof-pack manifest written: {MANIFEST}")
    print(f"captured files: {len(entries)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
