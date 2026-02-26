import sqlite3
import json
from typing import Dict, Any, List

# Import your new parser functions
from theme_parser import (
    parse_line,
    parse_text,
)  # assuming you saved your parser in theme_parser.py


# ==========================
# Database Initialization
# ==========================


def init_db(db_path="anime.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS anime (
            id INTEGER PRIMARY KEY,
            title TEXT,
            picture_large TEXT,
            picture_medium TEXT
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS themes (
            id INTEGER PRIMARY KEY,
            anime_id INTEGER,
            type TEXT,
            marker TEXT,
            theme_number INTEGER,
            title TEXT,
            artist TEXT,
            episode_tokens TEXT,
            episode_ranges TEXT,
            notes TEXT,
            parent_title TEXT,
            raw_text TEXT,
            FOREIGN KEY (anime_id) REFERENCES anime(id)
        )
    """
    )

    conn.commit()
    return conn


# ==========================
# Insert Logic
# ==========================


def insert_themes(
    cursor, anime_id: int, theme_list: List[Dict[str, Any]], theme_type: str
):
    """
    Inserts parsed themes into DB. Each theme in theme_list is a dict with key 'text' (raw line).
    """
    for theme in theme_list:
        parsed = parse_line(theme["text"])
        cursor.execute(
            """
            INSERT OR REPLACE INTO themes
            (id, anime_id, type, marker, theme_number, title, artist,
             episode_tokens, episode_ranges, notes, parent_title, raw_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                theme.get("id"),
                anime_id,
                theme_type,
                parsed.get("marker"),
                (
                    int(parsed["marker"][1:])
                    if parsed.get("marker") and parsed["marker"][1:].isdigit()
                    else None
                ),
                parsed.get("title"),
                parsed.get("artist"),
                # JSON strings with Unicode preserved, None if empty
                (
                    json.dumps(parsed["episode_tokens"], ensure_ascii=False)
                    if parsed.get("episode_tokens")
                    else None
                ),
                (
                    json.dumps(parsed["episode_ranges"], ensure_ascii=False)
                    if parsed.get("episode_ranges")
                    else None
                ),
                (
                    json.dumps(parsed["notes"], ensure_ascii=False)
                    if parsed.get("notes")
                    else None
                ),
                parsed.get("parent_title"),
                parsed.get("raw"),
            ),
        )


def insert_anime(conn, anime_data: Dict[str, Any]):
    cursor = conn.cursor()

    # Insert anime
    cursor.execute(
        """
        INSERT OR REPLACE INTO anime (id, title, picture_large, picture_medium)
        VALUES (?, ?, ?, ?)
    """,
        (
            anime_data["id"],
            anime_data.get("title"),
            anime_data.get("main_picture", {}).get("large"),
            anime_data.get("main_picture", {}).get("medium"),
        ),
    )

    # Insert openings and endings
    insert_themes(
        cursor, anime_data["id"], anime_data.get("opening_themes", []), "opening"
    )
    insert_themes(
        cursor, anime_data["id"], anime_data.get("ending_themes", []), "ending"
    )

    conn.commit()
