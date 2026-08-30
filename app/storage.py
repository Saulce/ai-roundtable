"""SQLite 持久化（Storage）。

决议来源：Wayfinder Map #1 决策票 #2（MVP 边界 —— 持久化只管本次转写 + 摘要/总结）。
"""

import json
import sqlite3
from typing import Optional


class Storage:
    """一次讨论（消息 / 摘要 / 状态）的 SQLite 持久化存储。

    - discussions: 讨论元数据（topic / personas / max_turns / status）
    - messages: 转写消息，按 (discussion_id, seq) 排序
    - summaries: 摘要/总结产物（mode = summary | final）
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS discussions (
                    id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    personas TEXT NOT NULL,
                    max_turns INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'running',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discussion_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    speaker TEXT,
                    content TEXT NOT NULL,
                    UNIQUE (discussion_id, seq)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discussion_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def create_discussion(self, discussion_id, topic, personas, max_turns) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO discussions (id, topic, personas, max_turns) VALUES (?, ?, ?, ?)",
                (discussion_id, topic, json.dumps(personas, ensure_ascii=False), max_turns),
            )

    def append_message(self, discussion_id, msg: dict) -> None:
        seq = self._next_seq(discussion_id)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages (discussion_id, seq, kind, speaker, content) VALUES (?, ?, ?, ?, ?)",
                (discussion_id, seq, msg["kind"], msg["speaker"], msg["content"]),
            )

    def save_summary(self, discussion_id, mode, content) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO summaries (discussion_id, mode, content) VALUES (?, ?, ?)",
                (discussion_id, mode, content),
            )

    def update_status(self, discussion_id, status) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE discussions SET status = ? WHERE id = ?",
                (status, discussion_id),
            )

    def get_discussion(self, discussion_id) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT topic, personas, max_turns, status FROM discussions WHERE id = ?",
                (discussion_id,),
            ).fetchone()
            if row is None:
                return None

            messages = [
                dict(m)
                for m in conn.execute(
                    "SELECT seq, kind, speaker, content FROM messages "
                    "WHERE discussion_id = ? ORDER BY seq",
                    (discussion_id,),
                ).fetchall()
            ]
            summaries = [
                dict(s)
                for s in conn.execute(
                    "SELECT mode, content FROM summaries "
                    "WHERE discussion_id = ? ORDER BY id",
                    (discussion_id,),
                ).fetchall()
            ]

        return {
            "topic": row["topic"],
            "personas": json.loads(row["personas"]),
            "max_turns": row["max_turns"],
            "status": row["status"],
            "messages": messages,
            "summaries": summaries,
        }

    def list_discussions(self) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, topic, personas, max_turns, status, created_at "
                "FROM discussions ORDER BY created_at DESC, id DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def _next_seq(self, discussion_id) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 AS next_seq "
                "FROM messages WHERE discussion_id = ?",
                (discussion_id,),
            ).fetchone()
            return row["next_seq"]
