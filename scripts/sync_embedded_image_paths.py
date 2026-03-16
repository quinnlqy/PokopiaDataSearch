"""
sync_embedded_image_paths.py
============================
将 habitats.js 和 items.js 里已有的 image_path
同步写入其他 JS 文件里的内嵌快照对象：

  pokemon.js   → habitat_refs[].image_path
  habitats.js  → required_items[].image_path

用法：
  python scripts/sync_embedded_image_paths.py [--dry-run]
"""

import argparse
import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
MINI_DIR = BASE_DIR / "miniprogram" / "data"


def load_js(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^module\.exports\s*=\s*", text)
    if m:
        text = text[m.end():]
    return json.loads(text.rstrip().rstrip(";"))


def save_js(path: Path, data: list[dict]) -> None:
    content = "module.exports = " + json.dumps(
        data, ensure_ascii=False, separators=(",", ":")
    ) + ";\n"
    path.write_text(content, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # ── 建索引 ──
    habitats = load_js(MINI_DIR / "habitats.js")
    items = load_js(MINI_DIR / "items.js")

    hab_index = {h["key"]: h.get("image_path") for h in habitats}
    item_index = {it["key"]: it.get("image_path") for it in items}

    print(f"habitat index: {len(hab_index)} entries")
    print(f"item index:    {len(item_index)} entries")

    # ── 1. pokemon.js → habitat_refs[].image_path ──
    pokemon = load_js(MINI_DIR / "pokemon.js")
    p_updated = 0
    for p in pokemon:
        for ref in p.get("habitat_refs") or []:
            key = ref.get("key")
            path = hab_index.get(key)
            if path and ref.get("image_path") != path:
                ref["image_path"] = path
                p_updated += 1
    print(f"\npokemon habitat_refs updated: {p_updated}")
    if not args.dry_run and p_updated:
        save_js(MINI_DIR / "pokemon.js", pokemon)
        print("  -> pokemon.js saved")

    # ── 2. habitats.js → required_items[].image_path ──
    # required_items 里存的是道具名（name），需要按名字反查
    # 先建 name_zh -> image_path 索引
    item_by_name: dict[str, str] = {}
    for it in items:
        name = it.get("name_zh") or it.get("name") or ""
        path = it.get("image_path")
        if name and path:
            item_by_name[name] = path

    h_updated = 0
    for h in habitats:
        for ri in h.get("required_items") or []:
            name = ri.get("name_zh") or ri.get("name") or ""
            path = item_by_name.get(name)
            if path and ri.get("image_path") != path:
                ri["image_path"] = path
                h_updated += 1
    print(f"habitats required_items updated: {h_updated}")
    if not args.dry_run and h_updated:
        save_js(MINI_DIR / "habitats.js", habitats)
        print("  -> habitats.js saved")

    if args.dry_run:
        print("\n[DRY-RUN] no files written")


if __name__ == "__main__":
    main()
