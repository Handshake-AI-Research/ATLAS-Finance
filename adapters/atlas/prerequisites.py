#!/usr/bin/env python3
"""Check everything needed before a run, and say exactly what to fix.

    uv run python -m adapters.atlas.prerequisites
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from adapters.atlas.config import (
    DEFAULT_DATA_DIR, DEFAULT_OUTPUT_DIR, GANDALF_REPO, GANDALF_VERSION, REPO_ROOT,
)

OK, BAD = "  ok  ", " FAIL "


def _docker() -> tuple[bool, str]:
    if not shutil.which("docker"):
        return False, "docker not on PATH - install Docker Desktop"
    r = subprocess.run(["docker", "info"], capture_output=True, text=True)
    return (r.returncode == 0, "Docker Desktop is not running" if r.returncode else "running")


def _harbor() -> tuple[bool, str]:
    if not shutil.which("harbor"):
        return False, "harbor not on PATH - uv tool install --upgrade 'harbor>=0.3.0'"
    r = subprocess.run(["harbor", "--version"], capture_output=True, text=True)
    return r.returncode == 0, r.stdout.strip() or r.stderr.strip()


def _hf_token() -> tuple[bool, str]:
    if os.environ.get("HF_TOKEN"):
        return True, "HF_TOKEN set"
    if (Path.home() / ".cache/huggingface/token").exists():
        return True, "cached token"
    return False, "no HF credentials - `uv run hf auth login` or export HF_TOKEN"


def _gandalf_public() -> tuple[bool, str]:
    """The verifier image clones gandalf with no credentials, so it must be public."""
    url = f"{GANDALF_REPO}/releases/tag/{GANDALF_VERSION}"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status == 200, f"{GANDALF_VERSION} reachable anonymously"
    except Exception as exc:  # noqa: BLE001
        return False, (
            f"cannot read {GANDALF_REPO}@{GANDALF_VERSION} anonymously ({exc}). "
            "Every verifier image build will fail until this repo is publicly readable."
        )


def _data() -> tuple[bool, str]:
    d = REPO_ROOT / DEFAULT_DATA_DIR
    packs = sorted((d / "env-packs").glob("*.zip")) if d.exists() else []
    if not packs:
        return False, "no packs yet - uv run python scripts/download_from_hf.py"
    return True, f"{len(packs)} pack(s) in {DEFAULT_DATA_DIR}/env-packs"


def _tasks() -> tuple[bool, str]:
    out = REPO_ROOT / DEFAULT_OUTPUT_DIR
    dirs = [p for p in out.glob("*") if (p / "task.toml").exists()] if out.exists() else []
    if not dirs:
        return False, "no task dirs yet - uv run python -m adapters.atlas.run_adapter"
    return True, f"{len(dirs)} task dir(s) in {DEFAULT_OUTPUT_DIR}"


CHECKS = [
    ("Docker", _docker), ("Harbor", _harbor), ("HuggingFace auth", _hf_token),
    ("gandalf reachable", _gandalf_public), ("Downloaded packs", _data),
    ("Generated tasks", _tasks),
]


def main() -> int:
    failures = 0
    for name, fn in CHECKS:
        good, detail = fn()
        print(f"[{OK if good else BAD}] {name:20s} {detail}")
        failures += 0 if good else 1
    if failures:
        print(f"\n{failures} check(s) need attention.")
    else:
        print("\nall good - harbor run -c job.yaml -p datasets/atlas")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
