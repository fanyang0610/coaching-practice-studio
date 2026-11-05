#!/usr/bin/env python3
"""Stage the runtime files and deploy them to an existing Hugging Face Space."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import tempfile


DEFAULT_SPACE_ID = "fanyang0610/Coaching-Practice-Studio"
ROOT = Path(__file__).resolve().parents[1]
LOCAL_ENTRYPOINT_SOURCE = Path("web_app.py")
REMOTE_ENTRYPOINT = Path("app.py")

# A public Space only receives these files. Both staging and the change checker
# use this mapping, so new local files are private by default.
SPACE_FILES = {
    Path(name): Path(name) for name in (
        "README.md",
        "requirements.txt",
        "account_pages.py",
        "accounts.py",
        "coach_agent.py",
        "coach_data.py",
        "coachee_agent.py",
        "coachee_data.py",
        "coaching_core.py",
        "db.py",
        "mailer.py",
        "memory.py",
        "quota.py",
        "safety.py",
        "studio_config.py",
        "web_assets.py",
        "site.webmanifest",
        "assets/icons/studio-icon-180.png",
        "assets/icons/studio-icon-192.png",
        "assets/icons/studio-icon-512.png",
    )
}
SPACE_FILES[LOCAL_ENTRYPOINT_SOURCE] = REMOTE_ENTRYPOINT


def stage_space(root: Path, stage_dir: Path) -> list[Path]:
    root = root.resolve()
    stage_dir = stage_dir.resolve()
    if stage_dir == root or root in stage_dir.parents:
        raise SystemExit("Stage directory must be outside the project folder.")
    if stage_dir.exists() and any(stage_dir.iterdir()):
        raise SystemExit(f"Stage directory must be empty: {stage_dir}")

    for local_path in SPACE_FILES:
        source = root / local_path
        if not source.is_file() or source.resolve() != source:
            raise SystemExit(f"Space source must be a regular project file: {local_path}")

    stage_dir.mkdir(parents=True, exist_ok=True)
    for local_path, remote_path in SPACE_FILES.items():
        destination = stage_dir / remote_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / local_path, destination)
    return sorted(SPACE_FILES.values())


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage and upload only the files listed in SPACE_FILES."
    )
    parser.add_argument(
        "space_id", nargs="?", default=os.environ.get("HF_SPACE_ID", DEFAULT_SPACE_ID),
        help=f"Space ID. Defaults to {DEFAULT_SPACE_ID} or HF_SPACE_ID.",
    )
    parser.add_argument("--commit-message", default="Deploy Coaching Practice Studio")
    parser.add_argument("--dry-run", action="store_true", help="List staged files without uploading.")
    parser.add_argument("--stage-dir", type=Path, help="Keep the staged files in this empty directory.")
    return parser.parse_args()


def _deploy(args: argparse.Namespace, stage_dir: Path) -> None:
    staged_files = stage_space(ROOT, stage_dir)
    print(f"Staged {len(staged_files)} files for {args.space_id} in {stage_dir}")
    if args.dry_run:
        for path in staged_files:
            print(path.as_posix())
        return

    from huggingface_hub import HfApi

    HfApi().upload_folder(repo_id=args.space_id, repo_type="space", folder_path=str(stage_dir),
                          commit_message=args.commit_message)


def main() -> int:
    args = _parse_args()
    if args.stage_dir:
        _deploy(args, args.stage_dir)
    else:
        with tempfile.TemporaryDirectory(prefix="studio-hf-space-") as stage_dir:
            _deploy(args, Path(stage_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
