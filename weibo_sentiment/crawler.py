"""Weibo crawler using public mobile APIs with visitor cookie handshake."""

from __future__ import annotations

import html
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterator, List, Optional, Tuple, Set

import requests
from bs4 import BeautifulSoup

LOGGER = logging.getLogger(__name__)

GEN_VISITOR = "https://passport.weibo.com/visitor/genvisitor"
VISITOR = "https://passport.weibo.com/visitor/visitor"
CONFIG = "https://m.weibo.cn/api/config"
STATUS_SHOW = "https://m.weibo.cn/statuses/show"
COMMENTS_URL = "https://m.weibo.cn/comments/hotflow"
COMMENTS_SHOW_URL = "https://m.weibo.cn/api/comments/show"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

URL_PATTERNS = [
    re.compile(r"m\.weibo\.cn/(?:status|detail)/(?P<bid>[A-Za-z0-9]+)"),
    re.compile(r"weibo\.com/\d+/(?P<bid>[A-Za-z0-9]+)"),
    re.compile(r"weibo\.cn/detail/(?P<bid>[A-Za-z0-9]+)"),
]


@dataclass
class Comment:
    """Normalized representation of a Weibo comment."""

    user: str
    text: str
    ts: str
    likes: int

    def to_dict(self) -> Dict[str, object]:
        return {"user": self.user, "text": self.text, "ts": self.ts, "likes": self.likes}


class WeiboClient:
    """Thin wrapper around requests.Session handling visitor cookies."""

    def __init__(self, timeout: int = 10) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "X-Requested-With": "XMLHttpRequest",
            }
        )
        self._initialized = False

    def ensure_ready(self, referer: str = "https://m.weibo.cn/") -> None:
        if self._initialized:
            return
        LOGGER.debug("Initializing Weibo visitor session.")
        tid = self._generate_tid()
        self._incarnate(tid)

        self.session.headers["Referer"] = referer
        config_resp = self.session.get(CONFIG, timeout=self.timeout)
        config_resp.raise_for_status()
        xsrf = self.session.cookies.get("XSRF-TOKEN")
        if xsrf:
            self.session.headers["X-XSRF-TOKEN"] = xsrf

        self._initialized = True

    def _generate_tid(self) -> str:
        params = {
            "cb": f"visitor_{int(time.time() * 1000)}",
            "_rand": "0.{}".format(int(time.time() * 1000)),
            "from": "weibo",
            "_lang": "zh-CN",
        }
        resp = self.session.get(GEN_VISITOR, params=params, timeout=self.timeout)
        resp.raise_for_status()
        match = re.search(r'"tid":"(?P<tid>[^"]+)"', resp.text)
        if not match:
            raise RuntimeError("Failed to acquire visitor tid.")
        return match.group("tid")

    def _incarnate(self, tid: str) -> None:
        params = {
            "a": "incarnate",
            "t": tid,
            "w": "3",
            "c": "094",
            "gc": "",
            "cb": "",
            "from": "weibo",
            "_rand": int(time.time() * 1000),
        }
        resp = self.session.get(VISITOR, params=params, timeout=self.timeout)
        resp.raise_for_status()

    def fetch_status(self, bid: str) -> Dict[str, object]:
        self.ensure_ready(referer=f"https://m.weibo.cn/status/{bid}")
        response = self.session.get(STATUS_SHOW, params={"id": bid}, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        if payload.get("ok") != 1:
            raise RuntimeError(f"Failed to fetch status info: {payload}")
        return payload["data"]

    def iter_comments(self, status_id: str, max_comments: int) -> Iterator[Comment]:
        """Yield comments up to max_comments using hot and timeline streams."""
        seen_ids: Set[str] = set()
        collected = 0

        for comment_id, comment in self._iter_hot_comments(status_id, max_comments):
            if comment_id in seen_ids:
                continue
            seen_ids.add(comment_id)
            yield comment
            collected += 1
            if collected >= max_comments:
                return

        for comment_id, comment in self._iter_paginated_comments(
            status_id, max_comments, seen_ids
        ):
            if comment_id in seen_ids:
                continue
            seen_ids.add(comment_id)
            yield comment
            collected += 1
            if collected >= max_comments:
                return

    def _iter_hot_comments(
        self, status_id: str, max_comments: int
    ) -> Iterator[Tuple[str, Comment]]:
        params = {"id": status_id, "mid": status_id, "max_id": 0, "max_id_type": 0}
        fetched = 0
        while fetched < max_comments:
            response = self.session.get(COMMENTS_URL, params=params, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
            if payload.get("ok") != 1:
                break

            data = payload.get("data") or {}
            comments = data.get("data") or []
            if not comments:
                break

            for item in comments:
                if fetched >= max_comments:
                    break
                fetched += 1
                yield str(item.get("id") or item.get("mid")), Comment(
                    user=item.get("user", {}).get("screen_name", "匿名用户"),
                    text=strip_tags(item.get("text", "")),
                    ts=parse_timestamp(item.get("created_at", "")),
                    likes=int(item.get("like_count") or 0),
                )

            max_id = data.get("max_id")
            if not max_id:
                break
            params["max_id"] = max_id
            params["max_id_type"] = data.get("max_id_type", 0)

    def _iter_paginated_comments(
        self, status_id: str, max_comments: int, seen_ids: Set[str]
    ) -> Iterator[Tuple[str, Comment]]:
        page = 1
        fetched = 0
        while fetched < max_comments:
            response = self.session.get(
                COMMENTS_SHOW_URL,
                params={"id": status_id, "page": page},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("ok") != 1:
                break
            comments = (payload.get("data") or {}).get("data") or []
            if not comments:
                break

            for item in comments:
                comment_id = item.get("id")
                if comment_id in seen_ids:
                    continue
                fetched += 1
                yield str(comment_id), Comment(
                    user=item.get("user", {}).get("screen_name", "匿名用户"),
                    text=strip_tags(item.get("text", "") or item.get("text_raw", "")),
                    ts=parse_timestamp(item.get("created_at", "")),
                    likes=int(item.get("like_counts") or item.get("like_count") or 0),
                )
                if fetched >= max_comments:
                    break

            page += 1


def strip_tags(text: str) -> str:
    """Remove HTML tags and unescape entities from comment text."""
    if not text:
        return ""
    soup = BeautifulSoup(text, "lxml")
    return soup.get_text(separator="", strip=True)


def parse_timestamp(raw: str) -> str:
    """Normalize Weibo formatted timestamp into ISO8601 string."""
    if not raw:
        return ""
    try:
        parsed = datetime.strptime(raw, "%a %b %d %H:%M:%S %z %Y")
        return parsed.isoformat()
    except ValueError:
        return raw


def extract_bid(url: str) -> Optional[str]:
    """Extract the base62 post identifier from a Weibo URL."""
    for pattern in URL_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group("bid")
    return None


def get_comments(url: str, max_comments: int = 1000) -> List[Dict[str, object]]:
    """Public API returning normalized comments for the given Weibo URL."""
    _, comments = fetch_post_with_comments(url, max_comments=max_comments)
    return comments


def fetch_post_with_comments(
    url: str, max_comments: int = 1000
) -> Tuple[Dict[str, object], List[Dict[str, object]]]:
    """Return post metadata together with associated comments."""
    client = WeiboClient()
    bid = extract_bid(url)
    if not bid:
        raise ValueError(f"Unable to parse Weibo ID from url: {url}")

    status = client.fetch_status(bid)
    status_id = status.get("id")
    if not status_id:
        raise RuntimeError("Status response missing numeric id.")

    comments = [comment.to_dict() for comment in client.iter_comments(status_id, max_comments)]
    LOGGER.info("Fetched %d comments for post %s", len(comments), status_id)
    return build_post_meta(status, url), comments


def get_post_meta(url: str) -> Dict[str, object]:
    """Return metadata for the given Weibo URL."""
    client = WeiboClient()
    bid = extract_bid(url)
    if not bid:
        raise ValueError(f"Unable to parse Weibo ID from url: {url}")

    status = client.fetch_status(bid)
    return build_post_meta(status, url)


def build_post_meta(status: Dict[str, object], url: str) -> Dict[str, object]:
    user = status.get("user", {})
    return {
        "id": status.get("id"),
        "url": url,
        "title": strip_tags(status.get("text", ""))[:120],
        "topic": ", ".join(topic.get("title", "") for topic in status.get("topics", [])),
        "like_cnt": status.get("attitudes_count"),
        "repost_cnt": status.get("reposts_count"),
        "comment_cnt": status.get("comments_count"),
        "author": user.get("screen_name"),
    }


__all__ = ["get_comments", "get_post_meta", "fetch_post_with_comments", "Comment"]
