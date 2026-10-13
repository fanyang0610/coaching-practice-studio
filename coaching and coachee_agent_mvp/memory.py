"""The insight profile the AI builds about each user, one per user and module (stored by db.Store)."""

import datetime
from dataclasses import asdict, dataclass, field


# Profiles are injected into prompts, so keep them short.
MAX_PROFILE_ITEMS = 8


@dataclass
class UserProfile:
    coaching_style_insights: str = ""
    learning_patterns: str = ""
    strengths: list[str] = field(default_factory=list)
    growth_areas: list[str] = field(default_factory=list)
    last_updated: str = ""
    session_count: int = 0

    @classmethod
    def from_dict(cls, data: dict | None) -> "UserProfile":
        if not data:
            return cls()
        valid_keys = cls.__dataclass_fields__.keys()
        return cls(**{key: value for key, value in data.items() if key in valid_keys})

    def to_dict(self) -> dict:
        return asdict(self)


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
    now = now or datetime.datetime.now(datetime.UTC)
    return UserProfile(
        coaching_style_insights=analysis.get("coaching_style") or profile.coaching_style_insights,
        learning_patterns=analysis.get("learning_patterns") or profile.learning_patterns,
        strengths=_merge_items(analysis.get("strengths") or [], profile.strengths),
        growth_areas=_merge_items(analysis.get("growth_areas") or [], profile.growth_areas),
        last_updated=now.strftime("%Y-%m-%d %H:%M UTC"),
        session_count=profile.session_count + 1,
    )
