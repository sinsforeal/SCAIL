"""castworld.db: the owner's own save (bench: <run>/castworld.db; live: data/koikano_world.db). Never her save."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path))
        self.db.execute("create table if not exists kv(k text primary key, v text)")
        self.db.execute("create table if not exists lives(date text, who text, line text, primary key(date, who))")
        self.db.commit()

    def get(self, k, default=None):
        r = self.db.execute("select v from kv where k=?", (k,)).fetchone()
        return json.loads(r[0]) if r else default

    def set(self, k, v):
        self.db.execute("insert or replace into kv values(?,?)", (k, json.dumps(v, ensure_ascii=False)))
        self.db.commit()

    def put_life(self, date, who, line):
        self.db.execute("insert or replace into lives values(?,?,?)", (date, who, line))
        self.db.commit()

    def lives(self, date):
        return dict(self.db.execute("select who, line from lives where date=?", (date,)).fetchall())

    def close(self):
        self.db.close()
