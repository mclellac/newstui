from __future__ import annotations

import html
import json
import logging
import time
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..config import (
    DOMAIN_BASE,
    HOME_PAGE_URL,
    HTTP_TIMEOUT,
    INITIAL_RETRY_DELAY,
    MIN_ARTICLE_WORDS,
    PLACEHOLDER_PATTERN,
    REQUEST_HEADERS,
    RETRY_ATTEMPTS,
    SECTIONS_PAGE_URL,
    load_read_articles,
    load_bookmarks,
)
from ..datamodels import Section, Story
from .base import BaseSource

logger = logging.getLogger("news")


class CBCSource(BaseSource):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        s = requests.Session()
        s.headers.update(REQUEST_HEADERS)
        retries = Retry(
            total=5, backoff_factor=0.3, status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retries)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        return s

    def _retryable_fetch(
        self, url: str, timeout: int = HTTP_TIMEOUT, attempts: int = RETRY_ATTEMPTS
    ) -> Optional[bytes]:
        delay = INITIAL_RETRY_DELAY
        for attempt in range(1, attempts + 1):
            try:
                logger.debug("Fetching %s (attempt %d/%d)", url, attempt, attempts)
                resp = self.session.get(url, timeout=timeout)
                resp.raise_for_status()
                logger.debug("Fetched %s OK", url)
                return resp.content
            except requests.RequestException as e:
                logger.debug("Fetch attempt %d failed for %s: %s", attempt, url, e)
                if attempt == attempts:
                    logger.warning("All fetch attempts failed for %s", url)
                    return None
                time.sleep(delay)
                delay *= 2
        return None

    def get_sections(self) -> List[Section]:
        allowed_sections = self.config.get("sections")
        sections_map: Dict[str, Section] = {}
        for url in (HOME_PAGE_URL, SECTIONS_PAGE_URL):
            content = self._retryable_fetch(url)
            if not content:
                continue
            try:
                soup = BeautifulSoup(content, "lxml")
                for a in soup.select("nav a[href], a[href^='/lite']"):
                    href = _abs_url(a.get("href", ""))
                    if "/lite" in href and "/lite/story/" not in href:
                        title = a.get_text(strip=True)
                        if (
                            title
                            and title.lower() not in {"menu", "search"}
                            and title not in sections_map
                        ):
                            if not allowed_sections or title in allowed_sections:
                                sections_map[title] = Section(title=title, url=href)
            except Exception as e:
                logger.debug("Failed parsing sections from %s: %s", url, e)
        return [Section("Home", HOME_PAGE_URL)] + list(sections_map.values())

    def get_stories(
        self, section: Section, read_articles: set[str], bookmarks: list[dict]
    ) -> List[Story]:
        bookmarked_urls = {b["url"] for b in bookmarks}
        content = self._retryable_fetch(section.url)
        if not content:
            return []
        try:
            soup = BeautifulSoup(content, "lxml")
            stories: List[Story] = []
            for a in soup.select("a[href*='/lite/story/']"):
                href = _abs_url(a.get("href", ""))
                span = a.find("span")
                flag = span.get_text(strip=True) if span else None
                title = a.get_text(" ", strip=True).replace(flag or "", "").strip()
                summary = None
                if p := a.find_next_sibling("p"):
                    summary = p.get_text(strip=True)
                if title and href:
                    stories.append(
                        Story(
                            title=title,
                            url=href,
                            flag=flag,
                            summary=summary,
                            read=href in read_articles,
                            bookmarked=href in bookmarked_urls,
                        )
                    )
            return _unique_ordered_stories(stories)
        except Exception as e:
            logger.error("Failed to parse stories from %s: %s", section.url, e)
            return []

    def get_story_content(self, story: Story, section: Section) -> Dict[str, Any]:
        content_bytes = self._retryable_fetch(story.url)
        if not content_bytes:
            return {"ok": False, "content": "Failed to fetch article."}
        try:
            soup = BeautifulSoup(content_bytes, "lxml")
            json_script = soup.find("script", id="__NEXT_DATA__")
            if json_script and getattr(json_script, "string", None):
                try:
                    data = json.loads(json_script.string)
                    article = (
                        data.get("props", {})
                        .get("pageProps", {})
                        .get("articleData", {})
                    )
                    parts = [f"# {article.get('title', 'No Title')}\n\n"]
                    for node in article.get("body", {}).get("parsed", []):
                        parts.append(_parse_json_node_to_markdown(node))
                    if more := article.get("moreStories", []):
                        parts.append("\n\n---\n\n## More Stories\n\n")
                        parts.extend(
                            f"- [{s.get('title')}]({_abs_url(s.get('url'))})\n"
                            for s in more
                        )
                    full = html.unescape("".join(parts)).strip()
                    if len(full.split()) > MIN_ARTICLE_WORDS:
                        return {"ok": True, "content": full}
                except Exception:
                    logger.debug(
                        "JSON parse failed for %s; falling back to paragraphs",
                        story.url,
                    )
            main = soup.find("main") or soup
            paras = [p.get_text(" ", strip=True) for p in main.find_all("p")]
            candidate = "\n\n".join([p for p in paras if p]).strip()
            if candidate and not _is_placeholder_text(candidate):
                return {"ok": True, "content": candidate}
        except Exception as e:
            logger.error("Failed to parse story content from %s: %s", story.url, e)
        return {"ok": False, "content": "Could not extract valid article content."}


def _abs_url(href: str) -> str:
    if not href:
        return ""
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return urljoin(DOMAIN_BASE, href)


def _unique_ordered_stories(items: Iterable[Story]) -> List[Story]:
    seen = set()
    out: List[Story] = []
    for s in items:
        if s.url and s.url not in seen:
            seen.add(s.url)
            out.append(s)
    return out


def _is_placeholder_text(text: str) -> bool:
    if not text:
        return True
    if len(text.split()) < MIN_ARTICLE_WORDS:
        return True
    if PLACEHOLDER_PATTERN.search(text):
        return True
    return False


def _parse_json_node_to_markdown(node: Dict[str, Any]) -> str:
    if not isinstance(node, dict):
        return ""
    node_type = node.get("type")
    tag = node.get("tag")
    content = node.get("content", [])
    if node_type == "text":
        return node.get("content", "")
    child_content = "".join(_parse_json_node_to_markdown(c) for c in content)
    tag_map = {
        "p": f"{child_content.strip()}\n\n",
        "h2": f"## {child_content.strip()}\n\n",
        "h3": f"### {child_content.strip()}\n\n",
        "a": f"[{child_content}]({_abs_url(node.get('attrs', {}).get('href', ''))})",
        "ul": f"{child_content}\n",
        "li": f"- {child_content.strip()}\n",
        "blockquote": "".join(
            f"> {line}\n" for line in child_content.strip().split("\n")
        )
        + "\n",
        "strong": f"**{child_content}**",
        "b": f"**{child_content}**",
        "em": f"*{child_content}*",
        "i": f"*{child_content}*",
    }
    return tag_map.get(tag, child_content)
