#!/usr/bin/env python3
"""Stage and deploy the Hugging Face Space without uploading the local wrapper."""

from __future__ import annotations

import argparse
import fnmatch
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


DEFAULT_SPACE_ID = "fanyang0610/Erickson-Coach-App"
ROOT = Path(__file__).resolve().parents[1]


def _load_hfignore(root: Path) -> list[str]:
    ignore_file = root / ".hfignore"
    if not ignore_file.exists():
        return []

    patterns = []
    for line in ignore_file.read_text(encoding="utf-8").splitlines():
        pattern = line.strip()
        if pattern and not pattern.startswith("#"):
            patterns.append(pattern)
    return patterns


def _is_ignored(relative_path: Path, is_dir: bool, patterns: list[str]) -> bool:
    path = relative_path.as_posix()
    parts = relative_path.parts

    for pattern in patterns:
        directory_pattern = pattern.endswith("/")
        clean_pattern = pattern.rstrip("/")

        if directory_pattern:
            if any(fnmatch.fnmatch(part, clean_pattern) for part in parts):
                return True
            if path == clean_pattern or path.startswith(f"{clean_pattern}/"):
                return True
            continue

        if fnmatch.fnmatch(path, pattern):
            return True
        if "/" not in pattern and any(fnmatch.fnmatch(part, pattern) for part in parts):
            return True
        if is_dir and fnmatch.fnmatch(f"{path}/", pattern):
            return True

    return False


def stage_space(root: Path, stage_dir: Path) -> list[Path]:
    root = root.resolve()
    stage_dir = stage_dir.resolve()
    patterns = _load_hfignore(root)
    explicit_local_only = {"app.py", "web_app.py", ".git"}

    if stage_dir == root or root in stage_dir.parents:
        raise SystemExit("Stage directory must be outside the project folder.")
    if stage_dir.exists() and any(stage_dir.iterdir()):
        raise SystemExit(f"Stage directory must be empty: {stage_dir}")
    stage_dir.mkdir(parents=True, exist_ok=True)

    for source_dir, dirnames, filenames in os.walk(root):
        source_path = Path(source_dir)
        relative_dir = source_path.relative_to(root)

        kept_dirs = []
        for dirname in dirnames:
            relative_path = relative_dir / dirname
            if relative_path.as_posix() in explicit_local_only:
                continue
            if _is_ignored(relative_path, True, patterns):
                continue
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in filenames:
            relative_path = relative_dir / filename
            relative_name = relative_path.as_posix()
            if relative_name in explicit_local_only:
                continue
            if _is_ignored(relative_path, False, patterns):
                continue

            destination = stage_dir / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / relative_path, destination)

    shutil.copy2(root / "web_app.py", stage_dir / "app.py")
    _verify_stage(root, stage_dir)
    return sorted(path.relative_to(stage_dir) for path in stage_dir.rglob("*") if path.is_file())


def _verify_stage(root: Path, stage_dir: Path) -> None:
    staged_app = stage_dir / "app.py"
    local_web_app = root / "web_app.py"
    local_wrapper = root / "app.py"

    if not staged_app.exists():
        raise SystemExit("Staged Space is missing remote app.py.")
    if (stage_dir / "web_app.py").exists():
        raise SystemExit("Staged Space must not upload web_app.py under its local name.")
    if staged_app.read_bytes() != local_web_app.read_bytes():
        raise SystemExit("Staged app.py must be copied from local web_app.py.")
    if staged_app.read_bytes() == local_wrapper.read_bytes():
        raise SystemExit("Refusing to upload the local wrapper app.py as the Space entrypoint.")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage web_app.py as remote app.py, then upload this Space safely."
    )
    parser.add_argument(
        "space_id",
        nargs="?",
        default=os.environ.get("HF_SPACE_ID", DEFAULT_SPACE_ID),
        help=f"Hugging Face Space id. Defaults to {DEFAULT_SPACE_ID} or HF_SPACE_ID.",
    )
    parser.add_argument(
        "--commit-message",
        default="Deploy web app as Space entrypoint",
        help="Commit message for hf upload.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and verify the staging directory without uploading.",
    )
    parser.add_argument(
        "--stage-dir",
        type=Path,
        help="Optional empty directory to use for staging. Mainly useful for inspection.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    if args.stage_dir:
        stage_dir = args.stage_dir.resolve()
        staged_files = stage_space(ROOT, stage_dir)
        cleanup = None
    else:
        cleanup = tempfile.TemporaryDirectory(prefix="erickson-hf-space-")
        stage_dir = Path(cleanup.name)
        staged_files = stage_space(ROOT, stage_dir)

    print(f"Staged {len(staged_files)} files for {args.space_id} in {stage_dir}")
    print("Verified: local web_app.py is staged as remote app.py; local wrapper app.py is excluded.")

    if args.dry_run:
        for path in staged_files:
            print(path.as_posix())
        if cleanup:
            cleanup.cleanup()
        return 0

    subprocess.run(
        [
            "hf",
            "upload",
            args.space_id,
            str(stage_dir),
            ".",
            "--type",
            "space",
            "--commit-message",
            args.commit_message,
        ],
        check=True,
    )

    if cleanup:
        cleanup.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
