import asyncio
from contextlib import contextmanager
import os
import sqlite3
import threading
from datetime import datetime


class RecordingRepository:
    """SQLite persistence for recording rooms and recording history."""

    ROOM_BOOL_FIELDS = {
        "segment_record",
        "monitor_status",
        "scheduled_recording",
        "enabled_message_push",
        "only_notify_no_record",
        "flv_use_direct_download",
    }

    ROOM_COLUMNS = [
        "rec_id",
        "url",
        "streamer_name",
        "record_format",
        "quality",
        "segment_record",
        "segment_time",
        "monitor_status",
        "scheduled_recording",
        "scheduled_start_time",
        "monitor_hours",
        "recording_dir",
        "enabled_message_push",
        "platform",
        "platform_key",
        "only_notify_no_record",
        "flv_use_direct_download",
        "created_at",
        "updated_at",
        "pinned_at",
        "pin_order",
        "last_recorded_at",
        "last_record_file",
        "last_live_title",
    ]

    HISTORY_COLUMNS = [
        "rec_id",
        "streamer_name",
        "platform",
        "platform_key",
        "live_title",
        "started_at",
        "ended_at",
        "duration_seconds",
        "output_dir",
        "file_path",
        "file_format",
        "file_size",
        "stop_reason",
        "status",
        "error_message",
        "created_at",
    ]

    def __init__(self, config_manager):
        self.db_path = os.path.join(config_manager.config_path, "recordings.db")
        self._lock = threading.Lock()

    @staticmethod
    def now_iso() -> str:
        return datetime.now().isoformat(timespec="seconds")

    @staticmethod
    def _to_db_bool(value):
        if value is None:
            return None
        return int(bool(value))

    @staticmethod
    def _from_db_bool(value):
        if value is None:
            return None
        return bool(value)

    def initialize(self):
        with self._connect() as conn:
            self._ensure_schema(conn)

    def load_recordings(self) -> list[dict]:
        with self._lock, self._connect() as conn:
            self._ensure_schema(conn)
            rows = conn.execute(
                """
                SELECT *
                FROM recording_rooms
                ORDER BY
                    CASE WHEN pinned_at IS NULL THEN 0 ELSE 1 END DESC,
                    pin_order DESC,
                    COALESCE(last_recorded_at, created_at, '') DESC
                """
            ).fetchall()
        return [self._row_to_room_dict(row) for row in rows]

    def count_recordings(self) -> int:
        with self._lock, self._connect() as conn:
            self._ensure_schema(conn)
            row = conn.execute("SELECT COUNT(*) AS count FROM recording_rooms").fetchone()
        return int(row["count"])

    async def save_recordings(self, recordings: list[dict]):
        await asyncio.to_thread(self.save_recordings_sync, recordings)

    def save_recordings_sync(self, recordings: list[dict]):
        with self._lock, self._connect() as conn:
            self._ensure_schema(conn)
            normalized = [self._normalize_room_dict(item) for item in recordings if item.get("rec_id")]
            rec_ids = [item["rec_id"] for item in normalized]
            with conn:
                for item in normalized:
                    self._upsert_room(conn, item)

                if rec_ids:
                    placeholders = ",".join("?" for _ in rec_ids)
                    conn.execute(f"DELETE FROM recording_rooms WHERE rec_id NOT IN ({placeholders})", rec_ids)
                else:
                    conn.execute("DELETE FROM recording_rooms")

    async def add_recording_history(self, history: dict):
        await asyncio.to_thread(self.add_recording_history_sync, history)

    def add_recording_history_sync(self, history: dict):
        with self._lock, self._connect() as conn:
            self._ensure_schema(conn)
            item = self._normalize_history_dict(history)
            columns = ", ".join(self.HISTORY_COLUMNS)
            placeholders = ", ".join("?" for _ in self.HISTORY_COLUMNS)
            values = [item.get(column) for column in self.HISTORY_COLUMNS]
            with conn:
                conn.execute(
                    f"INSERT INTO recording_history ({columns}) VALUES ({placeholders})",
                    values,
                )
                conn.execute(
                    """
                    UPDATE recording_rooms
                    SET
                        last_recorded_at = ?,
                        last_record_file = COALESCE(?, last_record_file),
                        last_live_title = COALESCE(?, last_live_title),
                        updated_at = ?
                    WHERE rec_id = ?
                    """,
                    (
                        item.get("ended_at") or item.get("started_at") or item.get("created_at"),
                        item.get("file_path"),
                        item.get("live_title"),
                        self.now_iso(),
                        item.get("rec_id"),
                    ),
                )

    def list_recording_history(self, rec_id: str | None = None, limit: int = 20) -> list[dict]:
        limit = max(1, min(int(limit or 20), 100))
        with self._lock, self._connect() as conn:
            self._ensure_schema(conn)
            if rec_id:
                rows = conn.execute(
                    """
                    SELECT id, rec_id, streamer_name, platform, platform_key, live_title,
                           started_at, ended_at, duration_seconds, output_dir, file_path,
                           file_format, file_size, stop_reason, status, error_message, created_at
                    FROM recording_history
                    WHERE rec_id = ?
                    ORDER BY COALESCE(ended_at, created_at, '') DESC, id DESC
                    LIMIT ?
                    """,
                    (rec_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, rec_id, streamer_name, platform, platform_key, live_title,
                           started_at, ended_at, duration_seconds, output_dir, file_path,
                           file_format, file_size, stop_reason, status, error_message, created_at
                    FROM recording_history
                    ORDER BY COALESCE(ended_at, created_at, '') DESC, id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [dict(row) for row in rows]

    async def clear_recording_history(self) -> int:
        return await asyncio.to_thread(self.clear_recording_history_sync)

    def clear_recording_history_sync(self) -> int:
        with self._lock, self._connect() as conn:
            self._ensure_schema(conn)
            row = conn.execute("SELECT COUNT(*) AS count FROM recording_history").fetchone()
            removed_count = int(row["count"] or 0)
            with conn:
                conn.execute("DELETE FROM recording_history")
                conn.execute(
                    """
                    UPDATE recording_rooms
                    SET
                        last_recorded_at = NULL,
                        last_record_file = NULL,
                        last_live_title = NULL,
                        updated_at = ?
                    """,
                    (self.now_iso(),),
                )
        return removed_count

    @contextmanager
    def _connect(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_schema(self, conn):
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recording_rooms (
                rec_id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                streamer_name TEXT,
                record_format TEXT,
                quality TEXT,
                segment_record INTEGER DEFAULT 0,
                segment_time TEXT,
                monitor_status INTEGER DEFAULT 0,
                scheduled_recording INTEGER DEFAULT 0,
                scheduled_start_time TEXT,
                monitor_hours TEXT,
                recording_dir TEXT,
                enabled_message_push INTEGER DEFAULT 0,
                platform TEXT,
                platform_key TEXT,
                only_notify_no_record INTEGER DEFAULT 0,
                flv_use_direct_download INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                pinned_at TEXT,
                pin_order INTEGER DEFAULT 0,
                last_recorded_at TEXT,
                last_record_file TEXT,
                last_live_title TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recording_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rec_id TEXT NOT NULL,
                streamer_name TEXT,
                platform TEXT,
                platform_key TEXT,
                live_title TEXT,
                started_at TEXT,
                ended_at TEXT,
                duration_seconds INTEGER,
                output_dir TEXT,
                file_path TEXT,
                file_format TEXT,
                file_size INTEGER,
                stop_reason TEXT,
                status TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recording_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT OR REPLACE INTO recording_meta (key, value) VALUES ('schema_version', '1')"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_recording_history_rec_id ON recording_history(rec_id)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_recording_history_ended_at ON recording_history(ended_at)"
        )

    def _normalize_room_dict(self, data: dict) -> dict:
        now = self.now_iso()
        item = {column: data.get(column) for column in self.ROOM_COLUMNS}
        item["created_at"] = item.get("created_at") or now
        item["updated_at"] = now
        item["pin_order"] = int(item.get("pin_order") or 0)
        for field in self.ROOM_BOOL_FIELDS:
            item[field] = self._to_db_bool(item.get(field))
        return item

    def _normalize_history_dict(self, data: dict) -> dict:
        now = self.now_iso()
        item = {column: data.get(column) for column in self.HISTORY_COLUMNS}
        item["created_at"] = item.get("created_at") or now
        if item.get("status") != "started":
            item["ended_at"] = item.get("ended_at") or now
        return item

    def _upsert_room(self, conn, item: dict):
        columns = ", ".join(self.ROOM_COLUMNS)
        placeholders = ", ".join("?" for _ in self.ROOM_COLUMNS)
        update_columns = [column for column in self.ROOM_COLUMNS if column not in {"rec_id", "created_at"}]
        update_sql = ", ".join(f"{column} = excluded.{column}" for column in update_columns)
        values = [item.get(column) for column in self.ROOM_COLUMNS]
        conn.execute(
            f"""
            INSERT INTO recording_rooms ({columns}) VALUES ({placeholders})
            ON CONFLICT(rec_id) DO UPDATE SET {update_sql}
            """,
            values,
        )

    def _row_to_room_dict(self, row: sqlite3.Row) -> dict:
        item = {column: row[column] for column in self.ROOM_COLUMNS}
        for field in self.ROOM_BOOL_FIELDS:
            item[field] = self._from_db_bool(item.get(field))
        item["pin_order"] = int(item.get("pin_order") or 0)
        return item
