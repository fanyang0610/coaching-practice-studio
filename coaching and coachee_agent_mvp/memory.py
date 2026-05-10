import json
import os
import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional

@dataclass
class UserProfile:
    coaching_style_insights: str = ""
    learning_patterns: str = ""
    strengths: list[str] = field(default_factory=list)
    growth_areas: list[str] = field(default_factory=list)
    last_updated: str = ""
    session_count: int = 0

class MemoryManager:
    def __init__(
        self,
        api_key: Optional[str] = None,
        remote_sync_enabled: bool = False,
        local_path: Optional[str] = "user_profile.json",
    ):
        self.local_path = local_path
        self.profile = UserProfile()
        self.api_key = api_key
        self.remote_sync_enabled = remote_sync_enabled
        self.load_local()

    def load_local(self):
        if not self.local_path:
            return
        if os.path.exists(self.local_path):
            try:
                with open(self.local_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Filter keys to match UserProfile dataclass
                    valid_keys = UserProfile.__dataclass_fields__.keys()
                    filtered_data = {k: v for k, v in data.items() if k in valid_keys}
                    self.profile = UserProfile(**filtered_data)
            except Exception:
                self.profile = UserProfile()

    def save_local(self):
        if not self.local_path:
            return
        with open(self.local_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self.profile), f, ensure_ascii=False, indent=2)

    def sync_pull(self) -> bool:
        """Remote profile sync is intentionally disabled for this MVP."""
        return False

    def sync_push(self) -> bool:
        """Remote profile sync is intentionally disabled for this MVP."""
        return False

    def update_from_analysis(self, analysis_json: dict):
        """Update the profile with new insights from an LLM analysis."""
        self.profile.coaching_style_insights = analysis_json.get("coaching_style", self.profile.coaching_style_insights)
        self.profile.learning_patterns = analysis_json.get("learning_patterns", self.profile.learning_patterns)
        
        new_strengths = analysis_json.get("strengths", [])
        self.profile.strengths = list(set(self.profile.strengths + new_strengths))
        
        new_growth = analysis_json.get("growth_areas", [])
        self.profile.growth_areas = list(set(self.profile.growth_areas + new_growth))
        
        self.profile.session_count += 1
        self.profile.last_updated = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        self.save_local()
        self.sync_push()
