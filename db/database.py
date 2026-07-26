import sqlite3
import json
import asyncio
from pathlib import Path
import config

DB_PATH = config.BASE_DIR / "stories.db"

class Database:
    def __init__(self):
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT,
                prompt TEXT,
                slides_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def save_story(self, user_id: int, title: str, prompt: str, slides: list) -> int:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO stories (user_id, title, prompt, slides_json) VALUES (?, ?, ?, ?)",
            (user_id, title, prompt, json.dumps(slides, ensure_ascii=False))
        )
        conn.commit()
        story_id = cursor.lastrowid
        conn.close()
        return story_id

    def get_story(self, story_id: int) -> dict | None:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, user_id, title, prompt, slides_json FROM stories WHERE id = ?", (story_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0],
                "user_id": row[1],
                "title": row[2],
                "prompt": row[3],
                "slides": json.loads(row[4])
            }
        return None
