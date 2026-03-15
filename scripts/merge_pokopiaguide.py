import json
import os


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")


def read_jsonl(path: str) -> list[dict]:
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: str, rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def join_required(items: list[dict]) -> str | None:
    if not items:
        return None
    parts = []
    for it in items:
        name = it.get("name_zh") or it.get("name")
        qty = it.get("qty") or it.get("count")
        if name and qty:
            parts.append(f"{name} x{qty}")
        elif name:
            parts.append(name)
    return ", ".join(parts) if parts else None


def merge_habitats() -> None:
    habitats = read_jsonl(os.path.join(PROCESSED_DIR, "habitats.jsonl"))
    pg_habitats = read_jsonl(os.path.join(RAW_DIR, "pokopiaguide_habitats_zh.jsonl"))
    pg_map = {h.get("slug"): h for h in pg_habitats if h.get("slug")}

    out = []
    for h in habitats:
        slug = h.get("slug")
        pg = pg_map.get(slug)
        if pg:
            if pg.get("name_zh"):
                h["name_zh"] = pg.get("name_zh")
                h["name_zh_source"] = "pokopiaguide"
                h["name_zh_source_url"] = pg.get("source_url")
            if pg.get("image_url"):
                h["image_url_pg"] = pg.get("image_url")
            if pg.get("required"):
                h["required_items_pg"] = pg.get("required")
                req_zh = join_required(pg.get("required"))
                if req_zh:
                    h["required_zh"] = req_zh
            if pg.get("attracts"):
                h["attracts_zh"] = [a.get("name_zh") for a in pg.get("attracts") if a.get("name_zh")]
                h["attracts_zh_source"] = "pokopiaguide"
        out.append(h)

    write_jsonl(os.path.join(PROCESSED_DIR, "habitats.jsonl"), out)


def merge_items() -> None:
    items = read_jsonl(os.path.join(RAW_DIR, "pokopiaguide_items_zh.jsonl"))
    out = []
    for it in items:
        out.append(
            {
                "name_zh": it.get("name_zh"),
                "image_url": it.get("image_url"),
                "category_key": it.get("category_key"),
                "desc_zh": it.get("desc_zh"),
                "obtain": it.get("obtain") or [],
                "recipe": it.get("recipe") or [],
                "materials": it.get("materials") or [],
                "source": "pokopiaguide",
                "source_url": it.get("source_url"),
            }
        )
    write_jsonl(os.path.join(PROCESSED_DIR, "items_zh.jsonl"), out)


def merge_crafting() -> None:
    recipes = read_jsonl(os.path.join(RAW_DIR, "pokopiaguide_crafting_zh.jsonl"))
    out = []
    for r in recipes:
        out.append(
            {
                "name_zh": r.get("name_zh"),
                "category_key": r.get("category_key"),
                "obtain_method": r.get("obtain_method"),
                "materials": r.get("materials") or [],
                "source": "pokopiaguide",
                "source_url": r.get("source_url"),
            }
        )
    write_jsonl(os.path.join(PROCESSED_DIR, "crafting_zh.jsonl"), out)


def merge_materials() -> None:
    materials = read_jsonl(os.path.join(RAW_DIR, "pokopiaguide_materials_zh.jsonl"))
    out = []
    for m in materials:
        out.append(
            {
                "name_zh": m.get("name_zh"),
                "image_url": m.get("image_url"),
                "how_to_get": m.get("how_to_get"),
                "used_in": m.get("used_in") or [],
                "source": "pokopiaguide",
                "source_url": m.get("source_url"),
            }
        )
    write_jsonl(os.path.join(PROCESSED_DIR, "materials_zh.jsonl"), out)


def merge_cooking() -> None:
    rows = read_jsonl(os.path.join(RAW_DIR, "pokopiaguide_cooking_zh.jsonl"))
    out = []
    for r in rows:
        out.append(
            {
                "id": r.get("id"),
                "name_zh": r.get("name_zh"),
                "category_key": r.get("category_key"),
                "category_zh": r.get("category_zh"),
                "price": r.get("price"),
                "ingredients": r.get("ingredients") or [],
                "tools": r.get("tools") or [],
                "power_up_moves": r.get("power_up_moves") or [],
                "image_url": r.get("image_url"),
                "source": "pokopiaguide",
                "source_url": r.get("source_url"),
            }
        )
    write_jsonl(os.path.join(PROCESSED_DIR, "cooking_zh.jsonl"), out)


def merge_pokedex_list() -> None:
    rows = read_jsonl(os.path.join(RAW_DIR, "pokopiaguide_pokedex_list_zh.jsonl"))
    out = []
    for r in rows:
        out.append(
            {
                "id": r.get("id"),
                "slug": r.get("slug"),
                "name_zh": r.get("name_zh"),
                "types": r.get("types") or [],
                "specialties": r.get("specialties") or [],
                "favorites": r.get("favorites") or [],
                "time": r.get("time") or [],
                "weather": r.get("weather") or [],
                "obtain_method": r.get("obtain_method"),
                "evolves_from": r.get("evolves_from"),
                "evolves_to": r.get("evolves_to") or [],
                "habitats": r.get("habitats") or [],
                "image_url": r.get("image_url"),
                "source": "pokopiaguide",
                "source_url": r.get("source_url"),
            }
        )
    write_jsonl(os.path.join(PROCESSED_DIR, "pokedex_list_zh.jsonl"), out)


def main():
    merge_habitats()
    merge_items()
    merge_crafting()
    merge_materials()
    merge_cooking()
    merge_pokedex_list()


if __name__ == "__main__":
    main()
