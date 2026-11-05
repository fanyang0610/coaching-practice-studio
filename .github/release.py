"""Publish one stable release for the commits included in a push to main."""

import os
import re
import subprocess


VERSION_TAG = re.compile(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
COMMIT_PREFIX = re.compile(r"^([a-z][a-z0-9-]*)(?:\([^()\n]+\))?(!)?:[ \t]+", re.IGNORECASE)
BREAKING = re.compile(r"^BREAKING(?: CHANGE|-CHANGE):[ \t]+\S", re.MULTILINE)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def next_version(version: tuple[int, int, int], messages: list[str]) -> str:
    major, minor, patch = version
    has_feature = False
    for message in messages:
        prefix = COMMIT_PREFIX.match(message)
        if (prefix and prefix[2]) or BREAKING.search(message.partition("\n")[2]):
            return f"v{major + 1}.0.0"
        if prefix and prefix[1].lower() == "feat":
            has_feature = True
    if has_feature:
        return f"v{major}.{minor + 1}.0"
    return f"v{major}.{minor}.{patch + 1}"


def main() -> None:
    repo = os.environ["GITHUB_REPOSITORY"]
    head = git("rev-parse", "HEAD")
    versions = []
    for tag in git("tag", "--list", "v*").splitlines():
        if match := VERSION_TAG.fullmatch(tag):
            versions.append((tuple(map(int, match.groups())), tag))
    if not versions:
        raise SystemExit("A stable version tag is required before automatic releases.")

    version, previous = max(versions)
    published = git("rev-parse", f"{previous}^{{commit}}")
    common = git("merge-base", published, head)
    if common == head:
        print(f"{head[:7]} is already included in {previous}.")
        return
    if common != published:
        raise SystemExit(f"{previous} is outside the history of this main push.")

    revisions = f"{previous}..{head}"
    messages = git("log", "--format=%B", "-z", revisions).split("\0")
    tag = next_version(version, messages)
    subjects = git("log", "--format=- %s", "--reverse", revisions)
    notes = f"## 本次改动\n\n{subjects}\n\n[查看完整改动](https://github.com/{repo}/compare/{previous}...{tag})\n"
    subprocess.run(
        ["gh", "release", "create", tag, "--repo", repo, "--target", head, "--latest",
         "--title", f"{tag} · 教练练习室", "--notes-file", "-"],
        input=notes,
        text=True,
        check=True,
    )


if __name__ == "__main__":
    main()
