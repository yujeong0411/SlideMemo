"""SQLite 기반 메모 저장소."""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


APP_DIR = Path.home() / ".memo_slide"
DB_PATH = APP_DIR / "memos.db"
IMAGES_DIR = APP_DIR / "images"

COLOR_SEQUENCE = [
    "sunrise", "blossom",
    "ivory", "blush", "peach", "cream", "olive", "lavender", "mint",
]
VALID_COLORS = set(COLOR_SEQUENCE)
DEFAULT_COLOR = "sunrise"

# 사용자 지정 색상: #RGB 또는 #RRGGBB hex 코드
_HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def normalize_color(color: str | None) -> str:
    """프리셋 이름이거나 유효한 hex 코드면 그대로, 그 외에는 기본색으로."""
    if color in VALID_COLORS:
        return color
    if isinstance(color, str) and _HEX_COLOR_RE.match(color.strip()):
        return color.strip()
    return DEFAULT_COLOR

# 정렬 모드별 ORDER BY 절 (is_pinned DESC가 항상 앞에 붙음)
SORT_CLAUSES = {
    "updated_desc": "updated_at DESC, id DESC",
    "updated_asc": "updated_at ASC, id ASC",
    "title_az": "title COLLATE NOCASE ASC, id ASC",
    "created_desc": "created_at DESC, id DESC",
}


@dataclass
class Memo:
    id: int
    title: str
    content: str
    color: str
    created_at: str
    updated_at: str
    is_pinned: bool = False
    deleted_at: str | None = None
    font_family: str = ""  # 빈 문자열이면 글로벌 default 사용
    font_size: int = 0     # 0이면 글로벌 default 사용

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Memo":
        keys = row.keys()
        return cls(
            id=row["id"],
            title=row["title"],
            content=row["content"],
            color=row["color"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            is_pinned=bool(row["is_pinned"]) if "is_pinned" in keys else False,
            deleted_at=row["deleted_at"] if "deleted_at" in keys else None,
            font_family=(row["font_family"] or "") if "font_family" in keys else "",
            font_size=int(row["font_size"] or 0) if "font_size" in keys else 0,
        )


class MemoDatabase:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._backed_up = False
        self._init_schema()
        self._migrate()

    def _init_schema(self) -> None:
        # 새 DB는 처음부터 최신 스키마. 기존 DB는 _migrate()가 보강.
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS memos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL DEFAULT '',
                color TEXT NOT NULL DEFAULT 'ivory',
                is_pinned INTEGER NOT NULL DEFAULT 0,
                deleted_at TEXT DEFAULT NULL,
                font_family TEXT NOT NULL DEFAULT '',
                font_size INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_memos_updated ON memos(updated_at DESC);
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def _backup_db(self) -> None:
        """마이그레이션 직전 1회만 .bak 백업 생성."""
        if self._backed_up:
            return
        self._backed_up = True
        bak = Path(str(self.db_path) + ".bak")
        try:
            bak_conn = sqlite3.connect(str(bak))
            with bak_conn:
                self.conn.backup(bak_conn)
            bak_conn.close()
            print(f"[migrate] DB 백업 생성: {bak}")
        except sqlite3.Error as e:  # 백업 실패해도 마이그레이션은 진행
            print(f"[migrate] 백업 실패(계속 진행): {e}")

    def _migrate(self) -> None:
        """기존 DB에 누락된 컬럼을 ALTER TABLE로 보강 (데이터 손실 없음)."""
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(memos)").fetchall()}
        added: list[str] = []
        if "is_pinned" not in cols:
            self._backup_db()
            self.conn.execute(
                "ALTER TABLE memos ADD COLUMN is_pinned INTEGER NOT NULL DEFAULT 0"
            )
            added.append("is_pinned")
        if "deleted_at" not in cols:
            self._backup_db()
            self.conn.execute(
                "ALTER TABLE memos ADD COLUMN deleted_at TEXT DEFAULT NULL"
            )
            added.append("deleted_at")
        if "font_family" not in cols:
            self._backup_db()
            self.conn.execute(
                "ALTER TABLE memos ADD COLUMN font_family TEXT NOT NULL DEFAULT ''"
            )
            added.append("font_family")
        if "font_size" not in cols:
            self._backup_db()
            self.conn.execute(
                "ALTER TABLE memos ADD COLUMN font_size INTEGER NOT NULL DEFAULT 0"
            )
            added.append("font_size")
        if added:
            self.conn.commit()
            print(f"[migrate] memos 테이블에 컬럼 추가: {', '.join(added)}")
        self.conn.execute("PRAGMA user_version = 2")
        self.conn.commit()

    # ----- settings -----
    def get_setting_int(self, key: str, default: int) -> int:
        row = self.conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return default
        try:
            return int(row["value"])
        except (ValueError, TypeError):
            return default

    def set_setting_int(self, key: str, value: int) -> None:
        self.conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(int(value))),
        )
        self.conn.commit()

    def get_setting_str(self, key: str, default: str = "") -> str:
        row = self.conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row is not None else default

    def set_setting_str(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )
        self.conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    def create(self, title: str = "", content: str = "", color: str = DEFAULT_COLOR) -> Memo:
        color = normalize_color(color)
        now = self._now()
        cur = self.conn.execute(
            "INSERT INTO memos (title, content, color, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (title, content, color, now, now),
        )
        self.conn.commit()
        return self.get(cur.lastrowid)

    def get(self, memo_id: int) -> Memo:
        row = self.conn.execute(
            "SELECT * FROM memos WHERE id = ?", (memo_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"memo {memo_id} not found")
        return Memo.from_row(row)

    def update(
        self,
        memo_id: int,
        *,
        title: str | None = None,
        content: str | None = None,
        color: str | None = None,
        font_family: str | None = None,
        font_size: int | None = None,
    ) -> Memo:
        fields: list[str] = []
        values: list[object] = []
        if title is not None:
            fields.append("title = ?")
            values.append(title)
        if content is not None:
            fields.append("content = ?")
            values.append(content)
        if color is not None:
            fields.append("color = ?")
            values.append(normalize_color(color))
        if font_family is not None:
            fields.append("font_family = ?")
            values.append(font_family)
        if font_size is not None:
            fields.append("font_size = ?")
            values.append(int(font_size))
        if not fields:
            return self.get(memo_id)
        fields.append("updated_at = ?")
        values.append(self._now())
        values.append(memo_id)
        self.conn.execute(
            f"UPDATE memos SET {', '.join(fields)} WHERE id = ?", values
        )
        self.conn.commit()
        return self.get(memo_id)

    def delete(self, memo_id: int) -> None:
        """완전 삭제 (hard delete). 휴지통 영구 삭제 / 자동 정리에서 사용."""
        self.conn.execute("DELETE FROM memos WHERE id = ?", (memo_id,))
        self.conn.commit()

    def soft_delete(self, memo_id: int) -> None:
        """휴지통으로 이동 (deleted_at 기록)."""
        self.conn.execute(
            "UPDATE memos SET deleted_at = ? WHERE id = ?",
            (self._now(), memo_id),
        )
        self.conn.commit()

    def restore(self, memo_id: int) -> Memo:
        """휴지통에서 복원 (deleted_at 해제)."""
        self.conn.execute(
            "UPDATE memos SET deleted_at = NULL WHERE id = ?", (memo_id,)
        )
        self.conn.commit()
        return self.get(memo_id)

    def set_pinned(self, memo_id: int, pinned: bool) -> Memo:
        # 고정은 메모 수정이 아니므로 updated_at은 건드리지 않음
        self.conn.execute(
            "UPDATE memos SET is_pinned = ? WHERE id = ?",
            (1 if pinned else 0, memo_id),
        )
        self.conn.commit()
        return self.get(memo_id)

    @staticmethod
    def _order_by(sort: str) -> str:
        # 고정 메모는 어떤 정렬에서도 항상 최우선
        clause = SORT_CLAUSES.get(sort, SORT_CLAUSES["updated_desc"])
        return f"is_pinned DESC, {clause}"

    def list_all(self, sort: str = "updated_desc") -> list[Memo]:
        rows = self.conn.execute(
            f"SELECT * FROM memos WHERE deleted_at IS NULL"
            f" ORDER BY {self._order_by(sort)}"
        ).fetchall()
        return [Memo.from_row(r) for r in rows]

    def search(self, keyword: str, sort: str = "updated_desc") -> list[Memo]:
        kw = (keyword or "").strip()
        if not kw:
            return self.list_all(sort)
        like = f"%{kw}%"
        rows = self.conn.execute(
            f"SELECT * FROM memos"
            f" WHERE deleted_at IS NULL AND (title LIKE ? OR content LIKE ?)"
            f" ORDER BY {self._order_by(sort)}",
            (like, like),
        ).fetchall()
        return [Memo.from_row(r) for r in rows]

    # ----- 휴지통 -----
    def list_trashed_memos(self) -> list[Memo]:
        rows = self.conn.execute(
            "SELECT * FROM memos WHERE deleted_at IS NOT NULL"
            " ORDER BY deleted_at DESC, id DESC"
        ).fetchall()
        return [Memo.from_row(r) for r in rows]

    def count_trashed(self) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) FROM memos WHERE deleted_at IS NOT NULL"
        ).fetchone()
        return int(row[0])

    def cleanup_old_trash(self, days: int = 30) -> list[Memo]:
        """days일 이상 지난 휴지통 항목을 완전 삭제. 삭제된 메모 목록 반환."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
        rows = self.conn.execute(
            "SELECT * FROM memos WHERE deleted_at IS NOT NULL AND deleted_at <= ?",
            (cutoff,),
        ).fetchall()
        old = [Memo.from_row(r) for r in rows]
        for m in old:  # 삭제 전에 콘솔 로그
            print(
                f"[trash] {days}일 경과 → 자동 영구삭제: "
                f"id={m.id} '{m.title or '(제목 없음)'}' (삭제일 {m.deleted_at})"
            )
        if old:
            self.conn.execute(
                "DELETE FROM memos WHERE deleted_at IS NOT NULL AND deleted_at <= ?",
                (cutoff,),
            )
            self.conn.commit()
        return old

    def close(self) -> None:
        try:
            self.conn.close()
        except sqlite3.Error:
            pass
