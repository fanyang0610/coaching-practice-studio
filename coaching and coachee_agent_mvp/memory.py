"""The insight profile the AI builds about each user, one per user and module (stored by db.Store)."""

import datetime
import hashlib
import json
from dataclasses import asdict, dataclass, field


# Profiles are injected into prompts, so keep them short.
MAX_PROFILE_ITEMS = 8
MAX_INSIGHT_CHARS = 2000
MAX_PRACTICE_GOAL_CHARS = 300
PROFILE_FIELDS = {
    "coach": ("coaching_style_insights", "strengths", "growth_areas"),
    "coachee": ("learning_patterns", "strengths", "growth_areas"),
}
LIST_FIELDS = ("strengths", "growth_areas")


def profile_version(data: dict | None) -> str:
    """Content version for forms and conditional writes; legacy JSON needs no migration."""
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


@dataclass
class UserProfile:
    coaching_style_insights: str = ""
    learning_patterns: str = ""
    strengths: list[str] = field(default_factory=list)
    growth_areas: list[str] = field(default_factory=list)
    last_updated: str = ""
    session_count: int = 0
    # Owner replacements and removed wording, scoped to each field.
    # Only exact, case-insensitive repeats are suppressed; no semantic matching.
    corrections: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    # One owner-controlled coaching skill goal, used only by the coachee module.
    next_practice_goal: str = ""

    @classmethod
    def from_dict(cls, data: dict | None) -> "UserProfile":
        if not data:
            return cls()
        valid_keys = cls.__dataclass_fields__.keys()
        return cls(**{key: value for key, value in data.items() if key in valid_keys})

    def to_dict(self) -> dict:
        return asdict(self)


def profile_items(profile: UserProfile, name: str) -> list[str]:
    value = getattr(profile, name)
    return list(value) if name in LIST_FIELDS else ([value] if value else [])


def change_insight(profile: UserProfile, name: str, index: int, value: str) -> UserProfile:
    """Change one current item, preserving all other content and owner corrections."""
    updated = UserProfile.from_dict(profile.to_dict())
    items = profile_items(updated, name)
    original = items[index]
    value = value.strip()
    if value == original:
        return updated
    changes = updated.corrections.setdefault(name, {"kept": [], "removed": []})
    changes["kept"] = [item for item in changes["kept"] if item.casefold() != original.casefold()]
    if value and value.casefold() not in {item.casefold() for item in changes["kept"]}:
        changes["kept"].append(value)
    changes["removed"] = list(dict.fromkeys(changes["removed"] + [original]))
    # An explicit owner edit can also restore wording they removed earlier.
    if value:
        changes["removed"] = [item for item in changes["removed"] if item.casefold() != value.casefold()]
    if value:
        items[index] = value
    else:
        items.pop(index)
    setattr(updated, name, items if name in LIST_FIELDS else (items[0] if items else ""))
    updated.last_updated = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return updated


def _merge_items(new_items, old_items) -> list[str]:
    """Newest first, without case-insensitive duplicates, capped at MAX_PROFILE_ITEMS."""
    merged, seen = [], set()
    for item in list(new_items) + list(old_items):
        text = str(item).strip()
        if text and text.lower() not in seen:
            seen.add(text.lower())
            merged.append(text)
    return merged[:MAX_PROFILE_ITEMS]


def merge_analysis(profile: UserProfile, analysis: dict, now: datetime.datetime | None = None) -> UserProfile:
    """Fold one session's LLM analysis into the profile."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    def merge_list(name):
        changes = profile.corrections.get(name, {})
        omitted = {text.casefold() for text in changes.get("removed", [])}
        generated = [str(item).strip() for item in analysis.get(name) or []]
        remaining = [item for item in generated + getattr(profile, name) if item.casefold() not in omitted]
        # Keep owner replacements before applying the existing eight-item cap.
        return _merge_items(changes.get("kept", []), remaining)

    return UserProfile(
        coaching_style_insights=(profile.coaching_style_insights if profile.corrections.get("coaching_style_insights")
                                 else analysis.get("coaching_style") or profile.coaching_style_insights),
        learning_patterns=(profile.learning_patterns if profile.corrections.get("learning_patterns")
                           else analysis.get("learning_patterns") or profile.learning_patterns),
        strengths=merge_list("strengths"),
        growth_areas=merge_list("growth_areas"),
        last_updated=now.strftime("%Y-%m-%d %H:%M UTC"),
        session_count=profile.session_count + 1,
        corrections=profile.to_dict()["corrections"],
        next_practice_goal=profile.next_practice_goal,
    )
