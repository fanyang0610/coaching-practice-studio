"""Studio settings and compatibility with existing installations."""

from pathlib import Path


LEGACY_NAME = "erickson"
LANG_COOKIE = "studio_lang"
LEGACY_LANG_COOKIE = f"{LEGACY_NAME}_lang"


def studio_env(env: dict[str, str], name: str) -> str:
    """Read the Studio variable first, even when explicitly set to an empty value."""
    return env.get(f"STUDIO_{name}", env.get(f"{LEGACY_NAME.upper()}_{name}", ""))


def local_path(path: Path, legacy_filename: str) -> Path:
    """Use existing local state in place so upgrading does not create a second copy."""
    if path.exists():
        return path
    legacy = path.with_name(legacy_filename)
    return legacy if legacy.exists() else path
