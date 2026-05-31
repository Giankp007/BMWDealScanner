"""SQLite store of seen listings — so we only alert on genuinely new ones."""
from __future__ import annotations
import sqlite3, json, time, os
from core import Listing

DB_PATH = os.path.join(os.path.dirname(__file__), "seen.db")


class Store:
    def __init__(self, path: str = DB_PATH):
        self.con = sqlite3.connect(path)
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS listings (
                uid        TEXT PRIMARY KEY,
                source     TEXT,
                profile    TEXT,
                price      INTEGER,
                url        TEXT,
                title      TEXT,
                first_seen REAL,
                last_seen  REAL,
                alerted    INTEGER DEFAULT 0,
                data       TEXT
            )
        """)
        self.con.commit()

    def is_seen(self, uid: str) -> bool:
        cur = self.con.execute("SELECT 1 FROM listings WHERE uid=?", (uid,))
        return cur.fetchone() is not None

    def profile_count(self, profile: str) -> int:
        cur = self.con.execute("SELECT COUNT(*) FROM listings WHERE profile=?", (profile,))
        return cur.fetchone()[0]

    def upsert(self, listing: Listing, profile: str, alerted: bool = False) -> bool:
        """Insert or refresh. Returns True if this was a NEW listing."""
        now = time.time()
        new = not self.is_seen(listing.uid)
        if new:
            self.con.execute(
                "INSERT INTO listings (uid,source,profile,price,url,title,first_seen,last_seen,alerted,data)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (listing.uid, listing.source, profile, listing.price, listing.url,
                 listing.title, now, now, int(alerted), json.dumps(listing.to_row(), ensure_ascii=False)),
            )
        else:
            self.con.execute(
                "UPDATE listings SET last_seen=?, price=? WHERE uid=?",
                (now, listing.price, listing.uid),
            )
        self.con.commit()
        return new

    def mark_alerted(self, uid: str):
        self.con.execute("UPDATE listings SET alerted=1 WHERE uid=?", (uid,))
        self.con.commit()

    def close(self):
        self.con.close()
