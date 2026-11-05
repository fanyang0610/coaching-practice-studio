#!/usr/bin/env python3
"""Report whether the current local diff warrants a Hugging Face Space upload."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import deploy_hf_space


ROOT = Path(__file__).resolve().parents[1]

class ChangeReason(NamedTuple):
    path: Path
    reason: str
    remote_path: Path | None = None


class UploadDecision(NamedTuple):
    needs_upload: bool
    deploy_worthy: list[ChangeReason]
    local_only: list[ChangeReason]


def _relative(path: Path) -> Path:
    return Path(path.as_posix().lstrip("/"))


def _parse_git_status(output: str, prefix: str) -> list[Path]:
    """Return project-relative paths from `git status --porcelain=v1 -z` output.

    Porcelain paths are relative to the repository root, so changes outside the
    project folder are dropped and the folder prefix is stripped from the rest.
    """
    fields = output.split("\0")
    paths: list[Path] = []
    index = 0
    while index < len(fields):
        entry = fields[index]
        index += 1
        if not entry:
            continue
        status, raw_paths = entry[:2], [entry[3:]]
        if "R" in status or "C" in status:
            # With -z the original path follows as its own field; a rename removes it.
            if "R" in status:
                raw_paths.append(fields[index])
            index += 1
        for raw_path in raw_paths:
            if raw_path.startswith(prefix):
                paths.append(_relative(Path(raw_path[len(prefix):])))
    return paths


def _git_changed_paths(root: Path) -> list[Path]:
    prefix = subprocess.run(
        ["git", "rev-parse", "--show-prefix"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.rstrip("\n")
    # -z disables quoting of paths with spaces, e.g. "coaching and coachee_agent_mvp/".
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all", "--", "."],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return _parse_git_status(result.stdout, prefix)


def decide_upload_need(changed_paths: list[Path]) -> UploadDecision:
    deploy_worthy: list[ChangeReason] = []
    local_only: list[ChangeReason] = []

    for path in sorted({_relative(path) for path in changed_paths}, key=lambda item: item.as_posix()):
        remote_path = deploy_hf_space.SPACE_FILES.get(path)
        if remote_path is None:
            local_only.append(ChangeReason(path, "not in the Space release list"))
            continue

        if path == deploy_hf_space.LOCAL_ENTRYPOINT_SOURCE:
            reason = (
                f"hosted Space entrypoint source; deploy_hf_space.py stages it as remote "
                f"{deploy_hf_space.REMOTE_ENTRYPOINT}"
            )
        else:
            reason = f"hosted Space file; deploy_hf_space.py stages it as {remote_path.as_posix()}"
        deploy_worthy.append(ChangeReason(path=path, reason=reason, remote_path=remote_path))

    return UploadDecision(
        needs_upload=bool(deploy_worthy),
        deploy_worthy=deploy_worthy,
        local_only=local_only,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Decide whether the current local diff needs a Hugging Face Space upload."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Optional changed paths to classify instead of reading git status.",
    )
    return parser.parse_args()


def _print_decision(decision: UploadDecision) -> None:
    print(f"HF upload needed: {'yes' if decision.needs_upload else 'no'}")
    if decision.deploy_worthy:
        print("Deploy-worthy changes:")
        for item in decision.deploy_worthy:
            print(f"- {item.path.as_posix()} -> {item.remote_path.as_posix()}: {item.reason}")
    if decision.local_only:
        print("Local-only changes:")
        for item in decision.local_only:
            print(f"- {item.path.as_posix()}: {item.reason}")
    if not decision.deploy_worthy and not decision.local_only:
        print("No local diff detected.")


def main() -> int:
    args = _parse_args()
    changed_paths = args.paths or _git_changed_paths(ROOT)
    decision = decide_upload_need(changed_paths)
    _print_decision(decision)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
