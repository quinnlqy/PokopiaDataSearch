import json
import os
import re
import urllib.request


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
OUT_DIR = os.path.join(BASE_DIR, "miniprogram", "data")
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")


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


def write_json(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


def write_js(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("module.exports = ")
        json.dump(obj, f, ensure_ascii=False)
        f.write(";")


def load_translations() -> dict:
    path = os.path.join(RAW_DIR, "pokopiaguide_translations_zh.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_key(value) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def normalize_slug(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip().lower()
    value = re.sub(r"^(?:\d+|e-\d+)-", "", value)
    return value


def slug_from_name(name: str | None) -> str | None:
    if not name:
        return None
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


def clean_value(value: str | None) -> str | None:
    if value is None:
        return None
    v = str(value).strip()
    if not v:
        return None
    if normalize_key(v) in {"tbd", "unknown", "none", "null", "n/a", "na", "-", "—", "–"}:
        return None
    return v


def translate_value(value, mapping: dict, fallback: str | None = None) -> str | None:
    value = clean_value(value)
    if value is None:
        return fallback
    key = normalize_key(value)
    return mapping.get(key, value)


def translate_list(values, mapping: dict) -> list:
    if not values:
        return []
    out = []
    for v in values:
        mapped = translate_value(v, mapping)
        if mapped:
            out.append(mapped)
    return out


def fix_favorite_keys(values: list) -> list:
    if not values:
        return []
    fixes = {
        "prety flowers": "pretty flowers",
        "gatherings": "gatherings",
    }
    out = []
    for v in values:
        key = normalize_key(v)
        out.append(fixes.get(key, v))
    return out


def translate_list_keys(values, mapping: dict) -> list:
    if not values:
        return []
    out = []
    for v in values:
        key = normalize_key(v)
        mapped = mapping.get(key, v)
        if mapped:
            out.append(mapped)
    return out


def fetch_official_pokedex_map() -> dict[int, str]:
    return {}


def load_pokedex_list() -> list[dict]:
    path = os.path.join(PROCESSED_DIR, "pokedex_list_zh.jsonl")
    return read_jsonl(path)


def build_pokedex_list_map(rows: list[dict]) -> dict:
    by_slug = {}
    by_name = {}
    for r in rows:
        slug = normalize_slug(r.get("slug"))
        if slug:
            by_slug[slug] = r
        name = r.get("name_zh")
        if name:
            by_name[name] = r
    return {"by_slug": by_slug, "by_name": by_name}


def load_category_files(cat):
    d = os.path.join(BASE_DIR, "data", "images", cat)
    if not os.path.isdir(d): return {}
    return {f.lower(): f for f in os.listdir(d)}
    
local_files_cache = {
    "pokemon": load_category_files("pokemon"),
    "habitats": load_category_files("habitats"),
    "items": load_category_files("items"),
    "furniture": load_category_files("furniture"),
    "cosmetics": load_category_files("cosmetics")
}

def find_local_image(category, possible_names):
    files = local_files_cache.get(category, {})
    for nm in possible_names:
        if not nm: continue
        base = re.sub(r'[^a-z0-9_-]+', '-', str(nm).lower()).strip('-')
        candidates = [f"{base}.png", f"{str(nm).lower().replace(' ', '')}.png", f"{str(nm).lower()}.png"]
        for c in candidates:
            if c in files:
                return f"/images/{category}/{files[c]}"
    return None


def build_pokemon(
    official_map: dict[int, str],
    translations: dict,
    pokedex_list: list[dict],
) -> list[dict]:
    rows = read_jsonl(os.path.join(PROCESSED_DIR, "pokemon.jsonl"))
    list_maps = build_pokedex_list_map(pokedex_list)
    by_slug = list_maps["by_slug"]
    types_map = translations.get("types") or {}
    favorites_map = translations.get("favorites") or {}
    time_map = translations.get("timeOfDay") or {}
    weather_map = translations.get("weather") or {}
    rarity_map = translations.get("rarity") or {}
    specialty_map = translations.get("specialties") or {}
    obtain_map = translations.get("obtainMethods") or {}

    out = []
    for r in rows:
        key_base = r.get("natdex_no") or r.get("dex_no") or r.get("slug") or r.get("name_en")
        image_url = r.get("image_url")
        try:
            natdex_no = int(r.get("natdex_no") or 0)
        except Exception:
            natdex_no = 0
        # if natdex_no and natdex_no in official_map:
        #     image_url = "https://tw.portal-pokemon.com/play/resources/pokedex" + official_map[natdex_no]
        if isinstance(image_url, str) and image_url.endswith("/show"):
            image_url = image_url[:-5]

        slug = normalize_slug(r.get("slug"))
        if not slug:
            slug = slug_from_name(r.get("name_en"))
        list_row = by_slug.get(slug) if slug else None

        name_zh = r.get("name_zh")

        local_img = find_local_image("pokemon", [r.get('dex_no'), r.get('slug'), r.get("name_en")])
        if not local_img and list_row:
            local_img = find_local_image("pokemon", [list_row.get('dex_no'), list_row.get('slug')])

        types_src = r.get("types") or []
        favorites_src = fix_favorite_keys(r.get("favorites") or [])
        time_src = r.get("time") or []
        weather_src = r.get("weather") or []
        rarity_src = r.get("rarity")
        specialty_src = r.get("specialty")
        habitats_src = [h.get("name") for h in r.get("habitats") or [] if isinstance(h, dict)]
        obtain_method = None

        if list_row:
            name_zh = list_row.get("name_zh") or name_zh
            types_src = list_row.get("types") or types_src
            favorites_src = fix_favorite_keys(list_row.get("favorites") or favorites_src)
            time_src = list_row.get("time") or time_src
            weather_src = list_row.get("weather") or weather_src
            rarity_src = list_row.get("rarity") or rarity_src
            specialties = list_row.get("specialties") or []
            if specialties:
                specialty_src = ", ".join(translate_list_keys(specialties, specialty_map))
            habitats_src = [h.get("name") for h in list_row.get("habitats") or [] if isinstance(h, dict)] or habitats_src
            obtain_method = list_row.get("obtain_method")

        types = translate_list_keys(types_src, types_map)
        favorites = translate_list_keys(favorites_src, favorites_map)
        time = translate_list_keys(time_src, time_map)
        weather = translate_list_keys(weather_src, weather_map)
        if isinstance(rarity_src, str):
            rarity_src = rarity_src.replace("very rare", "very-rare").replace("Very Rare", "very-rare")
        rarity = translate_value(rarity_src, rarity_map, fallback=translate_value(rarity_src, rarity_map))
        specialty = translate_value(specialty_src, specialty_map)
        obtain_method_zh = translate_value(obtain_method, obtain_map)

        out.append(
            {
                "key": f"pokemon:{key_base}",
                "category": "pokemon",
                "category_zh": "宝可梦",
                "dex_no": r.get("dex_no"),
                "natdex_no": r.get("natdex_no"),
                "name_en": r.get("name_en"),
                "name_zh": name_zh,
                "teach_move": clean_value(r.get("teach_move")),
                "specialty": specialty,
                "habitat_zh": r.get("habitat_zh"),
                "spawn_condition": r.get("spawn_condition"),
                "types": types,
                "favorites": favorites,
                "rarity": rarity,
                "time": time,
                "weather": weather,
                "habitats": habitats_src,
                "obtain_method": obtain_method,
                "obtain_method_zh": obtain_method_zh,
                "image_url": local_img or image_url or (list_row.get("image_url") if list_row else None),
                "image_path": r.get("image_path"),
                "source_url": r.get("source_url"),
            }
        )
    return out


def parse_required_items(required: str) -> list[dict]:
    if not required:
        return []
    parts = [p.strip() for p in required.split(",") if p.strip()]
    items = []
    for p in parts:
        m = re.match(r"^(.*?)\s*(?:x|×|X)\s*(\d+)$", p, flags=re.I)
        if m:
            name = m.group(1).strip()
            qty = int(m.group(2))
        else:
            name = p
            qty = None
        items.append({"name": name, "qty": qty})
    return items


def build_habitats(
    item_image_map: dict[str, str],
    pokemon_name_map: dict[str, dict],
    pokemon_zh_map: dict[str, dict],
) -> list[dict]:
    rows = read_jsonl(os.path.join(PROCESSED_DIR, "habitats.jsonl"))
    out = []
    for r in rows:
        key_base = r.get("id") or r.get("slug") or r.get("name")
        image_url = r.get("image_url_pg") or r.get("image_url")
        if isinstance(image_url, str) and image_url.endswith("/show"):
            image_url = image_url[:-5]
        if r.get("required_items_pg"):
            required_items = [
                {"name": it.get("name_zh") or it.get("name"), "name_zh": it.get("name_zh"), "qty": it.get("qty")}
                for it in r.get("required_items_pg") or []
            ]
        else:
            required_items = parse_required_items(r.get("required") or "")
        for it in required_items:
            img = item_image_map.get(str(it.get("name", "")).lower())
            if not img and it.get("name_zh"):
                img = item_image_map.get(it["name_zh"].lower())
            if img:
                it["image_url"] = img
        attract_refs = []
        for name_en in [a.get("name") for a in r.get("attracts") or [] if isinstance(a, dict)]:
            ref = pokemon_name_map.get(str(name_en).lower())
            if ref:
                attract_refs.append(ref)
        attracts_zh = []
        for name_zh in r.get("attracts_zh") or []:
            if name_zh in pokemon_zh_map:
                attracts_zh.append(name_zh)
        name_zh = r.get("name_zh")
        name_en = r.get("name")
        display_name = name_zh or name_en
        required_display = r.get("required_zh") or r.get("required")

        local_img = find_local_image("habitats", [r.get("id"), r.get("slug")])
        
        out.append(
            {
                "key": f"habitat:{key_base}",
                "category": "habitat",
                "category_zh": "栖息地",
                "id": r.get("id"),
                "name": display_name,
                "name_zh": name_zh,
                "name_en": name_en,
                "required": required_display,
                "required_zh": r.get("required_zh"),
                "required_items": required_items,
                "attracts": [a.get("name") for a in r.get("attracts") or [] if isinstance(a, dict)],
                "attracts_zh": attracts_zh,
                "attract_refs": attract_refs,
                "image_url": local_img or image_url,
                "image_path": r.get("image_path"),
                "source_url": r.get("source_url"),
            }
        )
    return out


def build_items(file_name: str, prefix: str, category_zh: str) -> list[dict]:
    rows = read_jsonl(os.path.join(PROCESSED_DIR, file_name))
    out = []
    for r in rows:
        name_zh = r.get("name_zh")
        name = r.get("name") or name_zh
        if not name:
            continue
        image_url = r.get("image_url")
        if isinstance(image_url, str) and image_url.endswith("/show"):
            image_url = image_url[:-5]
        if isinstance(image_url, str) and "/_next/image" in image_url:
            continue
        if isinstance(name, str) and "Includes category tree" in name:
            continue

        folder = "furniture" if prefix == "furniture" else "cosmetics" if prefix == "cosmetic" else "items"
        local_img = find_local_image(folder, [r.get("name"), r.get("name_en")])

        out.append(
            {
                "key": f"{prefix}:{name}",
                "category": prefix,
                "category_zh": category_zh,
                "category_key": r.get("category_key"),
                "name": name,
                "name_zh": name_zh,
                "location": r.get("location"),
                "image_url": local_img or image_url,
                "image_path": r.get("image_path"),
                "source_url": r.get("source_url"),
            }
        )
    return out


def build_cooking(item_image_map: dict[str, str]) -> list[dict]:
    rows = read_jsonl(os.path.join(PROCESSED_DIR, "cooking_zh.jsonl"))
    out = []
    for r in rows:
        ingredients = []
        for it in r.get("ingredients") or []:
            name = it.get("name_zh") or it.get("name")
            if not name:
                continue
            ing = {"name": name, "qty": it.get("qty")}
            img = item_image_map.get(str(name).lower())
            if img:
                ing["image_url"] = img
            ingredients.append(ing)
        out.append(
            {
                "key": f"cooking:{r.get('id') or r.get('name_zh')}",
                "category": "cooking",
                "category_zh": "料理",
                "id": r.get("id"),
                "name": r.get("name_zh"),
                "name_zh": r.get("name_zh"),
                "category_key": r.get("category_key"),
                "category_zh_recipe": r.get("category_zh"),
                "price": r.get("price"),
                "ingredients": ingredients,
                "tools": r.get("tools") or [],
                "power_up_moves": r.get("power_up_moves") or [],
                "image_url": r.get("image_url"),
                "source_url": r.get("source_url"),
            }
        )
    return out


def main():
    translations = load_translations()
    official_map = fetch_official_pokedex_map()
    pokedex_list = load_pokedex_list()
    pokemon = build_pokemon(official_map, translations, pokedex_list)

    items_file = "items_zh.jsonl" if os.path.exists(os.path.join(PROCESSED_DIR, "items_zh.jsonl")) else "items.jsonl"
    if items_file == "items_zh.jsonl":
        all_items = build_items(items_file, "item", "道具")
        furniture = [i for i in all_items if i.get("category_key") == "furniture"]
        items = [i for i in all_items if i.get("category_key") != "furniture"]
    else:
        items = build_items(items_file, "item", "道具")
        furniture = build_items("furniture.jsonl", "furniture", "家具")
    cosmetics = build_items("cosmetics.jsonl", "cosmetic", "服装")

    item_image_map = {}
    for it in items + furniture:
        name = it.get("name")
        url = it.get("image_url")
        if name and url:
            item_image_map[str(name).lower()] = url
        name_zh = it.get("name_zh")
        if name_zh and url:
            item_image_map[str(name_zh).lower()] = url

    pokemon_name_map = {}
    pokemon_zh_map = {}
    for p in pokemon:
        name_en = p.get("name_en")
        name_zh = p.get("name_zh")
        ref = {
            "key": p.get("key"),
            "name_en": name_en,
            "name_zh": name_zh,
            "image_url": p.get("image_url"),
        }
        if name_en:
            pokemon_name_map[name_en.lower()] = ref
        if name_zh:
            pokemon_zh_map[name_zh] = ref

    habitats = build_habitats(item_image_map, pokemon_name_map, pokemon_zh_map)
    cooking = build_cooking(item_image_map)

    habitat_map = {}
    for h in habitats:
        if h.get("name"):
            habitat_map[h["name"].lower()] = h
        if h.get("name_zh"):
            habitat_map[h["name_zh"].lower()] = h

    pokemon_habitat_map: dict[str, list[dict]] = {}
    for h in habitats:
        for ref in h.get("attract_refs") or []:
            key = ref.get("key")
            if not key:
                continue
            pokemon_habitat_map.setdefault(key, []).append(
                {
                    "key": h.get("key"),
                    "name": h.get("name"),
                    "name_zh": h.get("name_zh"),
                    "required": h.get("required"),
                    "image_url": h.get("image_url"),
                }
            )

    for p in pokemon:
        refs = []
        for name in p.get("habitats") or []:
            h = habitat_map.get(str(name).lower())
            if h:
                refs.append(
                    {
                        "key": h.get("key"),
                        "name": h.get("name"),
                        "name_zh": h.get("name_zh"),
                        "required": h.get("required"),
                        "image_url": h.get("image_url"),
                    }
                )
        key = p.get("key")
        if key in pokemon_habitat_map:
            refs.extend(pokemon_habitat_map[key])
        seen = set()
        deduped = []
        for r in refs:
            k = r.get("key") or r.get("name")
            if k in seen:
                continue
            seen.add(k)
            deduped.append(r)
        p["habitat_refs"] = deduped

    write_json(os.path.join(OUT_DIR, "pokemon.json"), pokemon)
    write_json(os.path.join(OUT_DIR, "habitats.json"), habitats)
    write_json(os.path.join(OUT_DIR, "items.json"), items)
    write_json(os.path.join(OUT_DIR, "furniture.json"), furniture)
    write_json(os.path.join(OUT_DIR, "cosmetics.json"), cosmetics)
    write_json(os.path.join(OUT_DIR, "cooking.json"), cooking)

    write_js(os.path.join(OUT_DIR, "pokemon.js"), pokemon)
    write_js(os.path.join(OUT_DIR, "habitats.js"), habitats)
    write_js(os.path.join(OUT_DIR, "items.js"), items)
    write_js(os.path.join(OUT_DIR, "furniture.js"), furniture)
    write_js(os.path.join(OUT_DIR, "cosmetics.js"), cosmetics)
    write_js(os.path.join(OUT_DIR, "cooking.js"), cooking)


if __name__ == "__main__":
    main()
