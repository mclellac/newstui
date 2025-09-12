from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

# --- Data models ---
@dataclass
class Story:
    title: str
    url: str
    flag: Optional[str] = None
    summary: Optional[str] = None
    read: bool = False
    bookmarked: bool = False


@dataclass
class Section:
    title: str
    url: str
