"""Publish one stable release for the commits included in a push to main."""

import json
import os
from pathlib import Path
import re
import subprocess


VERSION_TAG = re.compile(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
COMMIT_PREFIX = re.compile(r"^([a-z][a-z0-9-]*)(?:\([^()\n]+\))?(!)?:[ \t]+", re.IGNORECASE)
BREAKING = re.compile(r"^BREAKING(?: CHANGE|-CHANGE):[ \t]+\S", re.MULTILINE)
NOTES_PATH = ".github/release-notes.json"


def release_notes(raw: str) -> dict[str, str]:
    """Require reviewed text and a documentation decision in each language."""
    notes = json.loads(raw)
    for key in ("zh", "en", "documentation_zh", "documentation_en"):
        value = notes.get(key) if isinstance(notes, dict) else None
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Release notes require non-empty {key}.")
        if re.search(r"\b(?:TODO|TBD)\b|待填写|待补充", value, re.IGNORECASE):
            raise ValueError(f"Replace placeholders in {key} before publishing.")
        language = r"[\u4e00-\u9fff]" if key.endswith("zh") else r"[A-Za-z]"
        if not re.search(language, value):
            raise ValueError(f"Release notes require actual {key} text.")
    return notes


def format_notes(notes: dict[str, str], repo: str, previous: str, tag: str, subjects: str) -> str:
    return (
        f"## 中文\n\n{notes['zh'].strip()}\n\n"
        f"### 文档核对\n\n{notes['documentation_zh'].strip()}\n\n"
        f"## English\n\n{notes['en'].strip()}\n\n"
        f"### Documentation review\n\n{notes['documentation_en'].strip()}\n\n"
        f"[完整改动 / Full changes](https://github.com/{repo}/compare/{previous}...{tag})\n\n"
        f"<details>\n<summary>提交记录 / Commit log</summary>\n\n{subjects}\n\n</details>\n"
    )


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
    if not git("diff", "--name-only", previous, head, "--", NOTES_PATH):
        raise SystemExit(f"Update {NOTES_PATH} with bilingual notes and a documentation review for this release.")
    notes = release_notes(Path(NOTES_PATH).read_text(encoding="utf-8"))
    if git("ls-tree", "--name-only", previous, "--", NOTES_PATH):
        prior_notes = release_notes(git("show", f"{previous}:{NOTES_PATH}"))
        for language in ("zh", "en"):
            if notes[language].strip() == prior_notes[language].strip():
                raise SystemExit(f"Write new {language} release notes instead of reusing the previous release.")
    messages = git("log", "--format=%B", "-z", revisions).split("\0")
    tag = next_version(version, messages)
    subjects = git("log", "--format=- %s", "--reverse", revisions)
    body = format_notes(notes, repo, previous, tag, subjects)
    subprocess.run(
        ["gh", "release", "create", tag, "--repo", repo, "--target", head, "--latest",
         "--title", f"{tag} · 教练练习室 / Coaching Practice Studio", "--notes-file", "-"],
        input=body,
        text=True,
        check=True,
    )


if __name__ == "__main__":
    main()
