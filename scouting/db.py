import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Database:
    def __init__(self, conn, postgres):
        self.conn = conn
        self.postgres = postgres

    def run(self, sql, args=()):
        return self.conn.execute(sql.replace("?", "%s") if self.postgres else sql, args)

    def insert(self, table, rows, *, existing=False):
        rows = list(rows)
        if not rows:
            return
        marker = "%s" if self.postgres else "?"
        sql = f"INSERT INTO {table} VALUES ({','.join([marker] * len(rows[0]))})"
        if existing:
            sql += " ON CONFLICT DO NOTHING"
        self.conn.cursor().executemany(sql, rows)


@contextmanager
def database(url=None, *, importing=False):
    url = url or os.getenv("DATABASE_URL", "scouting.sqlite3")
    pg = url.startswith(("postgresql://", "postgres://"))
    if pg:
        import psycopg
        conn = psycopg.connect(url)
    else:
        conn = sqlite3.connect(url, timeout=90)
        conn.execute("PRAGMA foreign_keys=ON")
    try:
        db = Database(conn, pg)
        if importing:
            db.run("SELECT pg_advisory_xact_lock(7946512)" if pg else "BEGIN IMMEDIATE")
            for statement in Path(__file__).with_name("001_initial.sql").read_text().split(";"):
                if statement.strip():
                    db.run(statement)
        else:
            db.run("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ" if pg else "BEGIN")
        yield db
        conn.commit()
    finally:
        conn.close()
