"""
build_db.py
===========
将 miniprogram/data/items.js 和 habitats.js 导入 SQLite 数据库，
并提供工具函数供其他脚本调用。

用法：
  python scripts/build_db.py          # 构建/重建数据库
  python scripts/build_db.py --sync   # 从 JS 文件同步到 DB（增量更新）
  python scripts/build_db.py --export # 从 DB 导出回 JS 文件

数据库位置：data/pokopia.db
"""

import argparse
import json
import re
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
MINI_DIR = BASE_DIR / "miniprogram"
DB_PATH = BASE_DIR / "data" / "pokopia.db"


# ─────────────────────────────────────────────
# JS 文件读写（复用已有逻辑）
# ─────────────────────────────────────────────

def load_js_array(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^module\.exports\s*=\s*", text)
    if m:
        text = text[m.end():]
    return json.loads(text.rstrip().rstrip(";"))


def save_js_array(path: Path, data: list[dict]) -> None:
    content = "module.exports = " + json.dumps(
        data, ensure_ascii=False, separators=(",", ":")
    ) + ";\n"
    path.write_text(content, encoding="utf-8")


# ─────────────────────────────────────────────
# 数据库连接
# ─────────────────────────────────────────────

def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─────────────────────────────────────────────
# 建表
# ─────────────────────────────────────────────

def create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS items (
        key          TEXT PRIMARY KEY,
        category     TEXT,
        category_zh  TEXT,
        category_key TEXT,
        name         TEXT,
        name_zh      TEXT,
        location     TEXT,
        image_url    TEXT,
        image_path   TEXT,
        source_url   TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_items_name_zh  ON items(name_zh);
    CREATE INDEX IF NOT EXISTS idx_items_name     ON items(name);
    CREATE INDEX IF NOT EXISTS idx_items_category_key ON items(category_key);

    CREATE TABLE IF NOT EXISTS habitats (
        key           TEXT PRIMARY KEY,
        category      TEXT,
        category_zh   TEXT,
        id            TEXT,
        name          TEXT,
        name_zh       TEXT,
        name_en       TEXT,
        required      TEXT,
        required_zh   TEXT,
        required_items TEXT,
        attracts      TEXT,
        attracts_zh   TEXT,
        attract_refs  TEXT,
        image_url     TEXT,
        image_path    TEXT,
        source_url    TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_habitats_name_zh ON habitats(name_zh);
    CREATE INDEX IF NOT EXISTS idx_habitats_name_en ON habitats(name_en);
    """)
    conn.commit()


# ─────────────────────────────────────────────
# 导入 JS → DB
# ─────────────────────────────────────────────

def import_items(conn: sqlite3.Connection, items: list[dict]) -> int:
    upserted = 0
    for it in items:
        conn.execute("""
            INSERT INTO items
                (key, category, category_zh, category_key, name, name_zh,
                 location, image_url, image_path, source_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                category     = excluded.category,
                category_zh  = excluded.category_zh,
                category_key = excluded.category_key,
                name         = excluded.name,
                name_zh      = excluded.name_zh,
                location     = excluded.location,
                image_url    = excluded.image_url,
                image_path   = excluded.image_path,
                source_url   = excluded.source_url
        """, (
            it.get("key"),
            it.get("category"),
            it.get("category_zh"),
            it.get("category_key"),
            it.get("name"),
            it.get("name_zh"),
            it.get("location"),
            it.get("image_url"),
            it.get("image_path"),
            it.get("source_url"),
        ))
        upserted += 1
    conn.commit()
    return upserted


def import_habitats(conn: sqlite3.Connection, habitats: list[dict]) -> int:
    upserted = 0
    for h in habitats:
        def _json(v):
            return json.dumps(v, ensure_ascii=False) if v is not None else None

        conn.execute("""
            INSERT INTO habitats
                (key, category, category_zh, id, name, name_zh, name_en,
                 required, required_zh, required_items,
                 attracts, attracts_zh, attract_refs,
                 image_url, image_path, source_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                category      = excluded.category,
                category_zh   = excluded.category_zh,
                id            = excluded.id,
                name          = excluded.name,
                name_zh       = excluded.name_zh,
                name_en       = excluded.name_en,
                required      = excluded.required,
                required_zh   = excluded.required_zh,
                required_items= excluded.required_items,
                attracts      = excluded.attracts,
                attracts_zh   = excluded.attracts_zh,
                attract_refs  = excluded.attract_refs,
                image_url     = excluded.image_url,
                image_path    = excluded.image_path,
                source_url    = excluded.source_url
        """, (
            h.get("key"),
            h.get("category"),
            h.get("category_zh"),
            h.get("id"),
            h.get("name"),
            h.get("name_zh"),
            h.get("name_en"),
            _json(h.get("required")),
            _json(h.get("required_zh")),
            _json(h.get("required_items")),
            _json(h.get("attracts")),
            _json(h.get("attracts_zh")),
            _json(h.get("attract_refs")),
            h.get("image_url"),
            h.get("image_path"),
            h.get("source_url"),
        ))
        upserted += 1
    conn.commit()
    return upserted


# ─────────────────────────────────────────────
# 导出 DB → JS
# ─────────────────────────────────────────────

def export_items(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM items").fetchall()
    result = []
    for row in rows:
        result.append({
            "key": row["key"],
            "category": row["category"],
            "category_zh": row["category_zh"],
            "category_key": row["category_key"],
            "name": row["name"],
            "name_zh": row["name_zh"],
            "location": row["location"],
            "image_url": row["image_url"],
            "image_path": row["image_path"],
            "source_url": row["source_url"],
        })
    return result


def export_habitats(conn: sqlite3.Connection) -> list[dict]:
    def _parse(v):
        if v is None:
            return None
        try:
            return json.loads(v)
        except Exception:
            return v

    rows = conn.execute("SELECT * FROM habitats").fetchall()
    result = []
    for row in rows:
        result.append({
            "key": row["key"],
            "category": row["category"],
            "category_zh": row["category_zh"],
            "id": row["id"],
            "name": row["name"],
            "name_zh": row["name_zh"],
            "name_en": row["name_en"],
            "required": _parse(row["required"]),
            "required_zh": _parse(row["required_zh"]),
            "required_items": _parse(row["required_items"]),
            "attracts": _parse(row["attracts"]),
            "attracts_zh": _parse(row["attracts_zh"]),
            "attract_refs": _parse(row["attract_refs"]),
            "image_url": row["image_url"],
            "image_path": row["image_path"],
            "source_url": row["source_url"],
        })
    return result


# ─────────────────────────────────────────────
# 查询工具函数（供其他脚本 import 使用）
# ─────────────────────────────────────────────

def search_items(conn: sqlite3.Connection, keyword: str) -> list[sqlite3.Row]:
    """按中文名或英文名模糊搜索道具"""
    pattern = f"%{keyword}%"
    return conn.execute(
        "SELECT * FROM items WHERE name_zh LIKE ? OR name LIKE ?",
        (pattern, pattern)
    ).fetchall()


def get_item_by_key(conn: sqlite3.Connection, key: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM items WHERE key = ?", (key,)).fetchone()


def get_items_missing_image(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM items WHERE image_path IS NULL OR image_path = ''"
    ).fetchall()


def get_habitats_missing_image(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM habitats WHERE image_path IS NULL OR image_path = ''"
    ).fetchall()


def update_item_image_path(conn: sqlite3.Connection, key: str, image_path: str) -> None:
    conn.execute("UPDATE items SET image_path = ? WHERE key = ?", (image_path, key))
    conn.commit()


def update_habitat_image_path(conn: sqlite3.Connection, key: str, image_path: str) -> None:
    conn.execute("UPDATE habitats SET image_path = ? WHERE key = ?", (image_path, key))
    conn.commit()


# ─────────────────────────────────────────────
# 主程序
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Build/sync/export Pokopia SQLite DB")
    parser.add_argument("--sync", action="store_true", help="Sync JS files -> DB (default if DB missing)")
    parser.add_argument("--export", action="store_true", help="Export DB -> JS files")
    args = parser.parse_args()

    conn = get_conn()
    create_tables(conn)

    if args.export:
        print("[Export] DB -> JS files...")
        items = export_items(conn)
        save_js_array(MINI_DIR / "data" / "items.js", items)
        print(f"  items.js: {len(items)} records written")

        habitats = export_habitats(conn)
        save_js_array(MINI_DIR / "data" / "habitats.js", habitats)
        print(f"  habitats.js: {len(habitats)} records written")
        conn.close()
        return

    # Default: sync (import JS -> DB)
    print("[Sync] JS files -> DB...")

    items_js = MINI_DIR / "data" / "items.js"
    items = load_js_array(items_js)
    n = import_items(conn, items)
    print(f"  items: {n} records upserted")

    habitats_js = MINI_DIR / "data" / "habitats.js"
    habitats = load_js_array(habitats_js)
    n = import_habitats(conn, habitats)
    print(f"  habitats: {n} records upserted")

    # Stats
    item_count = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    item_missing = conn.execute("SELECT COUNT(*) FROM items WHERE image_path IS NULL OR image_path = ''").fetchone()[0]
    hab_count = conn.execute("SELECT COUNT(*) FROM habitats").fetchone()[0]
    hab_missing = conn.execute("SELECT COUNT(*) FROM habitats WHERE image_path IS NULL OR image_path = ''").fetchone()[0]

    print()
    print(f"Database: {DB_PATH}")
    print(f"  items:    {item_count} total, {item_missing} missing image_path")
    print(f"  habitats: {hab_count} total, {hab_missing} missing image_path")
    conn.close()


if __name__ == "__main__":
    main()
