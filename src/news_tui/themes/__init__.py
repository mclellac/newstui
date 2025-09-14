import os
from pathlib import Path
import importlib.resources

def get_themes_dir() -> Path:
    """Return the path to the user's themes directory."""
    return Path(os.path.expanduser("~/.config/news/themes"))

def get_packaged_themes_dir() -> Path:
    """Return the path to the packaged themes directory."""
    # This is a bit of a hack to get a Path object from the Traversable
    with importlib.resources.as_file(importlib.resources.files("news_tui.packaged_themes")) as p:
        return p

def get_theme_names() -> list[str]:
    """Return a list of available theme names."""
    packaged_themes_dir = get_packaged_themes_dir()
    user_themes_dir = get_themes_dir()

    theme_names = set()

    if packaged_themes_dir.is_dir():
        for f in packaged_themes_dir.iterdir():
            if f.is_file() and f.suffix == ".css":
                theme_names.add(f.stem)

    if user_themes_dir.exists():
        for f in user_themes_dir.iterdir():
            if f.is_file() and f.suffix == ".css":
                theme_names.add(f.stem)

    return sorted(list(theme_names))

def get_theme_path(name: str) -> Path:
    """
    Return the path to a theme's CSS file.
    User-defined themes take precedence over packaged themes.
    """
    user_theme_path = get_themes_dir() / f"{name}.css"
    if user_theme_path.exists():
        return user_theme_path

    packaged_theme_path = get_packaged_themes_dir() / f"{name}.css"
    return packaged_theme_path
