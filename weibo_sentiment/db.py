"""SQLite persistence layer for the Weibo sentiment project."""

from __future__ import annotations

import contextlib
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

DB_PATH = Path(__file__).resolve().with_name("sentiment.db")


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Create a SQLite connection with sensible defaults."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    """Create database tables when they do not already exist."""
    with contextlib.closing(get_connection(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                title TEXT,
                topic TEXT,
                like_cnt INTEGER DEFAULT 0,
                repost_cnt INTEGER DEFAULT 0,
                comment_cnt INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER,
                user TEXT,
                text TEXT,
                ts TEXT,
                FOREIGN KEY (post_id) REFERENCES posts (id)
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS emotions (
                comment_id INTEGER PRIMARY KEY,
                anger REAL,
                disgust REAL,
                fear REAL,
                joy REAL,
                sadness REAL,
                surprise REAL,
                top_labels TEXT,
                FOREIGN KEY (comment_id) REFERENCES comments (id)
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                comment_id INTEGER,
                level TEXT,
                region TEXT,
                type TEXT,
                FOREIGN KEY (comment_id) REFERENCES comments (id)
            );
            """
        )
        conn.commit()


def insert_post(meta: Dict[str, Optional[str]]) -> int:
    """Insert metadata for a Weibo post and return its primary key."""
    with contextlib.closing(get_connection()) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO posts (url, title, topic, like_cnt, repost_cnt, comment_cnt)
            VALUES (:url, :title, :topic, :like_cnt, :repost_cnt, :comment_cnt);
            """,
            meta,
        )
        if cursor.lastrowid:
            post_id = cursor.lastrowid
        else:
            cursor.execute("SELECT id FROM posts WHERE url = ?", (meta.get("url"),))
            row = cursor.fetchone()
            post_id = row["id"] if row else -1
        conn.commit()
    return post_id


def insert_comments(post_id: int, comments: Iterable[Dict[str, Optional[str]]]) -> List[int]:
    """Persist comments and return the generated comment IDs."""
    comment_ids: List[int] = []
    with contextlib.closing(get_connection()) as conn:
        cursor = conn.cursor()
        for payload in comments:
            cursor.execute(
                """
                INSERT INTO comments (post_id, user, text, ts)
                VALUES (?, ?, ?, ?);
                """,
                (
                    post_id,
                    payload.get("user"),
                    payload.get("text"),
                    payload.get("ts"),
                ),
            )
            comment_ids.append(cursor.lastrowid)
        conn.commit()
    return comment_ids


def insert_emotions(
    prob_list: Sequence[Sequence[float]],
    label_list: Sequence[Sequence[str]],
    comment_ids: Sequence[int],
) -> None:
    """Persist emotion probabilities and top labels associated with comments."""
    if not (len(prob_list) == len(label_list) == len(comment_ids)):
        raise ValueError("prob_list, label_list, and comment_ids must have the same length")

    with contextlib.closing(get_connection()) as conn:
        cursor = conn.cursor()
        for probs, labels, comment_id in zip(prob_list, label_list, comment_ids):
            payload = dict(zip(["anger", "disgust", "fear", "joy", "sadness", "surprise"], probs))
            cursor.execute(
                """
                INSERT OR REPLACE INTO emotions (
                    comment_id, anger, disgust, fear, joy, sadness, surprise, top_labels
                )
                VALUES (:comment_id, :anger, :disgust, :fear, :joy, :sadness, :surprise, :top_labels);
                """,
                {
                    "comment_id": comment_id,
                    **payload,
                    "top_labels": ",".join(labels),
                },
            )
        conn.commit()


def get_emotion_dist(post_id: int) -> Dict[str, float]:
    """Return aggregate emotion distribution for a given post."""
    with contextlib.closing(get_connection()) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                AVG(anger) AS anger,
                AVG(disgust) AS disgust,
                AVG(fear) AS fear,
                AVG(joy) AS joy,
                AVG(sadness) AS sadness,
                AVG(surprise) AS surprise
            FROM emotions
            JOIN comments ON emotions.comment_id = comments.id
            WHERE comments.post_id = ?;
            """,
            (post_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return {}
        return {key: row[key] for key in row.keys() if row[key] is not None}


def get_recent_posts(limit: int = 10):
    """Fetch recent posts for history view."""
    with contextlib.closing(get_connection()) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, title, url, topic, created_at, comment_cnt
            FROM posts
            ORDER BY created_at DESC
            LIMIT ?;
            """,
            (limit,),
        )
        return cursor.fetchall()


def get_comments_with_emotions(post_id: int):
    """Return comments and attached emotion scores for a given post."""
    with contextlib.closing(get_connection()) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT comments.id,
                   comments.user,
                   comments.text,
                   comments.ts,
                   emotions.anger,
                   emotions.disgust,
                   emotions.fear,
                   emotions.joy,
                   emotions.sadness,
                   emotions.surprise,
                   emotions.top_labels
            FROM comments
            LEFT JOIN emotions ON emotions.comment_id = comments.id
            WHERE comments.post_id = ?
            ORDER BY comments.id ASC;
            """,
            (post_id,),
        )
        return cursor.fetchall()
