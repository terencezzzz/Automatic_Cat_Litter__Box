"""SQLite persistence. Connections are short lived and safe across worker threads."""
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / 'media').mkdir(exist_ok=True)
        self.path = self.directory / 'app.sqlite3'
        with self.connect() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS config(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS owner(id INTEGER PRIMARY KEY CHECK(id=1), name TEXT, password TEXT);
                CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, csrf TEXT, expires REAL);
                CREATE TABLE IF NOT EXISTS login_attempts(at REAL);
                CREATE TABLE IF NOT EXISTS cats(id TEXT PRIMARY KEY, name TEXT, age TEXT, photo TEXT);
                CREATE TABLE IF NOT EXISTS events(
                    id TEXT PRIMARY KEY, source_key TEXT UNIQUE, kind TEXT, captured_at REAL,
                    cat_id TEXT REFERENCES cats(id), original TEXT, detection TEXT,
                    report TEXT, analysis TEXT, analysis_status TEXT DEFAULT 'pending', error TEXT);
                CREATE TABLE IF NOT EXISTS jobs(
                    id TEXT PRIMARY KEY, kind TEXT, event_id TEXT, status TEXT, error TEXT,
                    created_at REAL, request_key TEXT UNIQUE);
                CREATE TABLE IF NOT EXISTS commands(
                    id TEXT PRIMARY KEY, request_key TEXT UNIQUE, action TEXT, mode TEXT,
                    status TEXT, reason TEXT, created_at REAL, expires_at REAL, updated_at REAL);
                CREATE TABLE IF NOT EXISTS notifications(
                    id INTEGER PRIMARY KEY, key TEXT UNIQUE, text TEXT, event_id TEXT,
                    created_at REAL, read INTEGER DEFAULT 0);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def rows(self, sql, params=()):
        with self.connect() as db:
            return [dict(row) for row in db.execute(sql, params).fetchall()]

    def one(self, sql, params=()):
        rows = self.rows(sql, params)
        return rows[0] if rows else None

    def execute(self, sql, params=()):
        with self.connect() as db:
            return db.execute(sql, params).rowcount

    def settings(self):
        result = dict(camera_url='', monitor=False, cloud_analysis=False,
                      ai_model='gpt-4.1-mini', serial_port='', notifications=True)
        result.update({r['key']: json.loads(r['value']) for r in self.rows('SELECT * FROM config')})
        return result

    def configure(self, values):
        with self.connect() as db:
            for key, value in values.items():
                db.execute('INSERT OR REPLACE INTO config VALUES(?,?)', (key, json.dumps(value)))

    def notify(self, key, text, event_id=None):
        if self.settings()['notifications']:
            self.execute('INSERT OR IGNORE INTO notifications(key,text,event_id,created_at) VALUES(?,?,?,?)',
                         (key, text, event_id, time.time()))
