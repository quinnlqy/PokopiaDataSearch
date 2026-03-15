import html
import json
import os
import re
import sys
import time
import urllib.request


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")


def fetch(url: str, timeout: int = 30, retries: int = 3) -> str:
    last_err = None
    for _ in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as err:
            last_err = err
            time.sleep(0.8)
            continue
    raise last_err


def write_jsonl(path: str, rows) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def dedupe_keep_order(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def parse_article_blocks(text: str) -> list[str]:
    blocks = []
    start = 0
    while True:
        idx = text.find("<article", start)
        if idx == -1:
            break
        end = text.find("</article>", idx)
        if end == -1:
            break
        blocks.append(text[idx:end + len("</article>")])
        start = end + len("</article>")
    return blocks


def extract_img_tags(block: str) -> list[dict]:
    tags = []
    for m in re.finditer(r"<img[^>]+>", block):
        tag = m.group(0)
        alt = None
        src = None
        width = None
        m_alt = re.search(r'alt="([^"]+)"', tag)
        if m_alt:
            alt = m_alt.group(1)
        m_src = re.search(r'src="([^"]+)"', tag)
        if m_src:
            src = m_src.group(1)
        m_width = re.search(r'width="(\\d+)"', tag)
        if m_width:
            width = int(m_width.group(1))
        tags.append({"alt": alt, "src": src, "width": width, "tag": tag})
    return tags


def extract_main_image(block: str, name: str | None) -> str | None:
    tags = extract_img_tags(block)
    for t in tags:
        if t["alt"] == name and t["width"] and t["width"] >= 48 and t["src"]:
            return t["src"]
    for t in tags:
        if t["width"] and t["width"] >= 48 and t["src"]:
            return t["src"]
    return None


def extract_ingredients(block: str, item_name: str | None) -> list[dict]:
    ingredients = []
    for m in re.finditer(
        r'<img[^>]*alt="([^"]+)"[^>]*width="(\\d+)"[^>]*src="([^"]+)"[^>]*>',
        block,
    ):
        name = m.group(1)
        width = int(m.group(2))
        if width > 30:
            continue
        if item_name and name == item_name:
            continue
        tail = block[m.end(): m.end() + 260]
        qty = None
        m_qty = re.search(r"(?:x|×|X)\\s*(?:<!-- ?-->)?\\s*(\\d+)", tail)
        if not m_qty:
            m_qty = re.search(r"<text[^>]*>[^0-9]*(\\d+)</text>", tail)
        if m_qty:
            qty = m_qty.group(1)
        ingredients.append({"name_zh": name, "qty": qty})
    seen = set()
    out = []
    for item in ingredients:
        key = (item.get("name_zh"), item.get("qty"))
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def parse_card_block(block: str) -> dict | None:
    name = None
    m_name = re.search(r"<h3[^>]*>([^<]+)</h3>", block)
    if not m_name:
        m_name = re.search(r"<h4[^>]*>([^<]+)</h4>", block)
    if m_name:
        name = html.unescape(m_name.group(1)).strip()
    if not name:
        return None

    image_url = extract_main_image(block, name)
    category = None
    m_cat = re.search(r"<span[^>]*rounded-full[^>]*>([^<]+)</span>", block)
    if m_cat:
        category = html.unescape(m_cat.group(1)).strip()
    desc = None
    m_desc = re.search(r"<p[^>]*>([^<]+)</p>", block)
    if m_desc:
        desc = html.unescape(m_desc.group(1)).strip()
    ingredients = extract_ingredients(block, name)
    return {
        "name_zh": name,
        "image_url": image_url,
        "category_zh": category,
        "desc_zh": desc,
        "ingredients": ingredients,
    }


def get_pokedex_slugs() -> list[str]:
    url = "https://pokopiaguide.com/zh-Hans/pokedex"
    text = fetch(url)
    slugs = set()
    for m in re.findall(
        r"https://assets\\.pokopiaguide\\.com/pokemon/([a-z0-9\\-]+)\\.png", text
    ):
        slugs.add(m)
    return sorted(slugs)


def parse_pokemon_page(slug: str, locale: str) -> dict:
    url = f"https://pokopiaguide.com/{locale}/pokedex/{slug}"
    text = fetch(url)
    data = {
        "slug": slug,
        "locale": locale,
        "source_url": url,
        "name": None,
        "no": None,
        "types": [],
        "specialty": [],
        "teach_move": None,
        "time": [],
        "weather": [],
        "favorites": [],
        "method": None,
        "habitat": [],
        "image_url": None,
    }

    m = re.search(r"https://assets\\.pokopiaguide\\.com/pokemon/[^\"']+\\.png", text)
    if m:
        data["image_url"] = m.group(0)

    m_name = re.search(r"<h1[^>]*>([^<]+)</h1>", text)
    if m_name:
        data["name"] = html.unescape(m_name.group(1)).strip()
    m_no = re.search(r"No\\.(\\d+)", text)
    if m_no:
        data["no"] = m_no.group(1)

    data["types"] = dedupe_keep_order(
        re.findall(r'<img[^>]*alt="([^"]+)"[^>]*src="/images/types/[^"]+"', text)
    )
    data["specialty"] = dedupe_keep_order(
        re.findall(r'<img[^>]*alt="([^"]+)"[^>]*src="/images/specialties/[^"]+"', text)
    )
    data["time"] = dedupe_keep_order(
        re.findall(r'<img[^>]*alt="([^"]+)"[^>]*src="/images/time/[^"]+"', text)
    )
    data["weather"] = dedupe_keep_order(
        re.findall(r'<img[^>]*alt="([^"]+)"[^>]*src="/images/weather/[^"]+"', text)
    )
    data["habitat"] = dedupe_keep_order(
        re.findall(r'<img[^>]*alt="([^"]+)"[^>]*src="/images/habitats/[^"]+"', text)
    )
    return data


def get_habitat_slugs_from_local() -> list[str]:
    path = os.path.join(BASE_DIR, "data", "processed", "habitats.jsonl")
    if not os.path.exists(path):
        return []
    slugs = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            slug = row.get("slug")
            if slug:
                slugs.append(slug)
    return sorted(set(slugs))


def parse_habitat_page(slug: str) -> dict | None:
    url = f"https://pokopiaguide.com/zh-Hans/habitat/{slug}"
    try:
        text = fetch(url)
    except Exception:
        return None
    data = {
        "slug": slug,
        "source_url": url,
        "name_zh": None,
        "no": None,
        "required": [],
        "attracts": [],
        "image_url": None,
    }
    m = re.search(r"/images/habitats/[^\"']+\\.png", text)
    if m:
        data["image_url"] = "https://pokopiaguide.com" + m.group(0)

    m_name = re.search(r"<h1[^>]*>([^<]+)</h1>", text)
    if m_name:
        data["name_zh"] = html.unescape(m_name.group(1)).strip()
    m_no = re.search(r"No\\.(\\d+)", text)
    if m_no:
        data["no"] = m_no.group(1)

    data["required"] = extract_ingredients(text, None)
    data["attracts"] = [
        {"name_zh": n}
        for n in dedupe_keep_order(
            re.findall(
                r'<img[^>]*alt="([^"]+)"[^>]*src="https://assets\\.pokopiaguide\\.com/pokemon/[^"]+"',
                text,
            )
        )
    ]
    return data


def get_material_slugs() -> list[str]:
    url = "https://pokopiaguide.com/zh-Hans/habitat"
    text = fetch(url)
    links = re.findall(r'href=\"(/zh-Hans/habitat/materials/[^\"#]+)\"', text)
    slugs = [l.split("/")[-1] for l in links]
    return sorted(set(slugs))


def parse_material_page(slug: str) -> dict | None:
    url = f"https://pokopiaguide.com/zh-Hans/habitat/materials/{slug}"
    try:
        text = fetch(url)
    except Exception:
        return None
    data = {
        "slug": slug,
        "source_url": url,
        "name_zh": None,
        "how_to_get": None,
        "image_url": None,
        "used_in": [],
    }
    m_name = re.search(r"<h1[^>]*>([^<]+)</h1>", text)
    if m_name:
        data["name_zh"] = html.unescape(m_name.group(1)).strip()

    m = re.search(r"/images/items/[^\"']+\\.png", text)
    if m:
        data["image_url"] = "https://pokopiaguide.com" + m.group(0)

    m_get = re.search(r"获取方式</h2>\\s*<p[^>]*>([^<]+)</p>", text)
    if m_get:
        data["how_to_get"] = html.unescape(m_get.group(1)).strip()

    used = []
    for m in re.finditer(
        r'href="/zh-Hans/habitat/[^"]+"[^>]*>([^<]+)</a>[^<]*需要[^0-9]*(\\d+)',
        text,
    ):
        used.append({"habitat_zh": html.unescape(m.group(1)).strip(), "qty": m.group(2)})
    if used:
        data["used_in"] = used
    return data


def parse_items_page(url: str) -> list[dict]:
    text = fetch(url)
    rows = []
    structured = None
    chunks = re.findall(r'self.__next_f.push\\(\\[1,\"(.*?)\"\\]\\)', text, flags=re.S)
    for c in chunks:
        if "/images/items/" not in c or "items" not in c:
            continue
        unescaped = c.replace("\\\"", "\"").replace("\\n", "\n").replace("\\\\", "\\")
        idx = unescaped.find("\"items\"")
        if idx == -1:
            continue
        start = unescaped.find("[", idx)
        if start == -1:
            continue
        level = 0
        end = None
        in_string = False
        escape = False
        for i in range(start, len(unescaped)):
            ch = unescaped[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == "\"":
                    in_string = False
                continue
            if ch == "\"":
                in_string = True
                continue
            if ch == "[":
                level += 1
            elif ch == "]":
                level -= 1
                if level == 0:
                    end = i + 1
                    break
        if end is None:
            continue
        try:
            structured = json.loads(unescaped[start:end])
            break
        except json.JSONDecodeError:
            continue
    if structured is not None:
        for item in structured:
            rows.append(
                {
                    "id": item.get("id"),
                    "name_zh": item.get("name"),
                    "category_key": item.get("categoryKey"),
                    "image_url": normalize_image_url(item.get("imageUrl")),
                    "desc_zh": item.get("description"),
                    "obtain": item.get("obtain") or [],
                    "recipe": item.get("recipe") or [],
                    "materials": [
                        {
                            "id": m.get("id"),
                            "name_zh": m.get("name"),
                            "qty": m.get("count"),
                            "image_url": normalize_image_url(m.get("imageUrl")),
                        }
                        for m in (item.get("materials") or [])
                    ],
                    "source_url": url,
                }
            )
        return rows

    for block in parse_article_blocks(text):
        card = parse_card_block(block)
        if not card:
            continue
        if card["image_url"] and card["image_url"].startswith("/"):
            card["image_url"] = "https://pokopiaguide.com" + card["image_url"]
        card["source_url"] = url
        rows.append(card)
    return rows


def parse_crafting_page(url: str) -> list[dict]:
    text = fetch(url)
    rows = []
    structured = None
    chunks = re.findall(r'self.__next_f.push\\(\\[1,\"(.*?)\"\\]\\)', text, flags=re.S)
    for c in chunks:
        if "materials" not in c or "recipes" not in c:
            continue
        unescaped = c.replace("\\\"", "\"").replace("\\n", "\n").replace("\\\\", "\\")
        idx = unescaped.find("\"recipes\"")
        if idx == -1:
            continue
        start = unescaped.find("[", idx)
        if start == -1:
            continue
        level = 0
        end = None
        in_string = False
        escape = False
        for i in range(start, len(unescaped)):
            ch = unescaped[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == "\"":
                    in_string = False
                continue
            if ch == "\"":
                in_string = True
                continue
            if ch == "[":
                level += 1
            elif ch == "]":
                level -= 1
                if level == 0:
                    end = i + 1
                    break
        if end is None:
            continue
        try:
            structured = json.loads(unescaped[start:end])
            break
        except json.JSONDecodeError:
            continue
    if structured is not None:
        for item in structured:
            rows.append(
                {
                    "id": item.get("id"),
                    "name_zh": item.get("name"),
                    "category_key": item.get("category"),
                    "obtain_method": item.get("obtainMethod"),
                    "materials": [
                        {
                            "name_zh": m.get("name"),
                            "qty": m.get("quantity"),
                            "image_url": normalize_image_url(m.get("imageUrl")),
                        }
                        for m in (item.get("materials") or [])
                    ],
                    "source_url": url,
                }
            )
        return rows

    for block in parse_article_blocks(text):
        card = parse_card_block(block)
        if not card:
            continue
        if card["image_url"] and card["image_url"].startswith("/"):
            card["image_url"] = "https://pokopiaguide.com" + card["image_url"]
        card["source_url"] = url
        rows.append(card)
    return rows


def parse_cooking_page(url: str) -> list[dict]:
    text = fetch(url)
    rows = []
    for block in parse_article_blocks(text):
        if "/images/cooking/recipes/" not in block:
            continue
        name = None
        m_name = re.search(r"<h4[^>]*>([^<]+)</h4>", block)
        if m_name:
            name = html.unescape(m_name.group(1)).strip()
        if not name:
            continue
        img = None
        m_img = re.search(r'src="(/images/cooking/recipes/[^"]+)"', block)
        if m_img:
            img = "https://pokopiaguide.com" + m_img.group(1)
        recipe_id = None
        if m_img:
            recipe_id = os.path.splitext(os.path.basename(m_img.group(1)))[0]
        price = None
        m_price = re.search(r'Life Coin\"[^>]*?/>\s*(?:<!-- ?-->)?\s*(\d+)', block)
        if m_price:
            price = int(m_price.group(1))
        ingredients = []
        for m in re.finditer(r'<img[^>]*alt="([^"]+)"[^>]*src="/images/cooking/ingredients/[^"]+"', block):
            ing = html.unescape(m.group(1)).strip()
            if ing:
                ingredients.append(ing)
        # count ingredients
        ing_counts = []
        seen = {}
        for ing in ingredients:
            seen[ing] = seen.get(ing, 0) + 1
        for ing, qty in seen.items():
            ing_counts.append({"name_zh": ing, "qty": qty})

        tools = []
        for m in re.finditer(r'<img[^>]*alt="([^"]+)"[^>]*src="/images/cooking/tools/[^"]+"', block):
            tool = html.unescape(m.group(1)).strip()
            if tool:
                tools.append(tool)
        tools = dedupe_keep_order(tools)

        moves = []
        for m in re.finditer(r'<img[^>]*alt="([^"]+)"[^>]*src="/images/cooking/moves/[^"]+"', block):
            mv = html.unescape(m.group(1)).strip()
            if mv:
                moves.append(mv)
        moves = dedupe_keep_order(moves)

        category_key = None
        if recipe_id:
            if "salad" in recipe_id:
                category_key = "salad"
            elif "soup" in recipe_id:
                category_key = "soup"
            elif "bread" in recipe_id:
                category_key = "bread"
            elif "hamburger" in recipe_id:
                category_key = "hamburger-steak"

        category_zh = None
        if category_key == "salad":
            category_zh = "沙拉"
        elif category_key == "soup":
            category_zh = "汤"
        elif category_key == "bread":
            category_zh = "面包"
        elif category_key == "hamburger-steak":
            category_zh = "汉堡排"

        rows.append(
            {
                "id": recipe_id,
                "name_zh": name,
                "image_url": img,
                "category_key": category_key,
                "category_zh": category_zh,
                "price": price,
                "ingredients": ing_counts,
                "tools": tools,
                "power_up_moves": moves,
                "source_url": url,
            }
        )
    return rows


def normalize_image_url(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("http"):
        return url
    return "https://pokopiaguide.com" + url


def extract_items_from_next_f(text: str) -> list | None:
    return extract_next_f_array(text, key="items", hint="/images/items/")


def extract_recipes_from_next_f(text: str) -> list | None:
    return extract_next_f_array(text, key="recipes", hint="materials")


def parse_pokedex_list_page(url: str) -> list[dict]:
    text = fetch(url)
    rows = []
    # try to parse full list from Next.js flight payload
    chunks = re.findall(r'self.__next_f.push\\(\\[1,\"(.*?)\"\\]\\)', text, flags=re.S)
    for c in chunks:
        unescaped = c.replace("\\\"", "\"").replace("\\n", "\n").replace("\\\\", "\\")
        idx = unescaped.find('[{"id":')
        if idx == -1 or "assets.pokopiaguide.com/pokemon" not in unescaped:
            continue
        start = idx
        level = 0
        end = None
        in_string = False
        escape = False
        for i in range(start, len(unescaped)):
            ch = unescaped[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == "\"":
                    in_string = False
                continue
            if ch == "\"":
                in_string = True
                continue
            if ch == "[":
                level += 1
            elif ch == "]":
                level -= 1
                if level == 0:
                    end = i + 1
                    break
        if end is None:
            continue
        try:
            data = json.loads(unescaped[start:end])
        except json.JSONDecodeError:
            continue
        if not isinstance(data, list) or len(data) < 50:
            continue
        for p in data:
            pokopia = p.get("pokopia") or {}
            rows.append(
                {
                    "id": p.get("id"),
                    "slug": p.get("slug"),
                    "name_zh": p.get("name"),
                    "types": p.get("types") or [],
                    "image_url": p.get("image"),
                    "specialties": pokopia.get("specialties") or [],
                    "favorites": pokopia.get("favorites") or [],
                    "time": pokopia.get("timeOfDay") or [],
                    "weather": pokopia.get("weather") or [],
                    "obtain_method": pokopia.get("obtainMethod"),
                    "evolves_from": pokopia.get("evolvesFrom"),
                    "evolves_to": pokopia.get("evolvesTo") or [],
                    "habitats": pokopia.get("habitats") or [],
                    "source_url": f"https://pokopiaguide.com/zh-Hans/pokedex/{p.get('slug')}",
                }
            )
        return rows

    # fallback: scan raw text for escaped array
    raw_idx = text.find('[{\\\"id\\\":')
    if raw_idx != -1:
        raw_chunk = text[raw_idx:]
        unescaped = raw_chunk.replace("\\\"", "\"").replace("\\n", "\n").replace("\\\\", "\\")
        start = 0
        level = 0
        end = None
        in_string = False
        escape = False
        for i in range(start, len(unescaped)):
            ch = unescaped[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == "\"":
                    in_string = False
                continue
            if ch == "\"":
                in_string = True
                continue
            if ch == "[":
                level += 1
            elif ch == "]":
                level -= 1
                if level == 0:
                    end = i + 1
                    break
        if end is not None:
            try:
                data = json.loads(unescaped[start:end])
                if isinstance(data, list) and len(data) >= 50:
                    for p in data:
                        pokopia = p.get("pokopia") or {}
                        rows.append(
                            {
                                "id": p.get("id"),
                                "slug": p.get("slug"),
                                "name_zh": p.get("name"),
                                "types": p.get("types") or [],
                                "image_url": p.get("image"),
                                "specialties": pokopia.get("specialties") or [],
                                "favorites": pokopia.get("favorites") or [],
                                "time": pokopia.get("timeOfDay") or [],
                                "weather": pokopia.get("weather") or [],
                                "obtain_method": pokopia.get("obtainMethod"),
                                "evolves_from": pokopia.get("evolvesFrom"),
                                "evolves_to": pokopia.get("evolvesTo") or [],
                                "habitats": pokopia.get("habitats") or [],
                                "source_url": f"https://pokopiaguide.com/zh-Hans/pokedex/{p.get('slug')}",
                            }
                        )
                    return rows
            except json.JSONDecodeError:
                pass

    # fallback: SSR cards only
    for block in parse_article_blocks(text):
        if "assets.pokopiaguide.com/pokemon" not in block:
            continue
        dex_no = None
        m_no = re.search(r"#(\\d{3})", block)
        if m_no:
            dex_no = m_no.group(1)
        name_zh = None
        m_name = re.search(r"<h3[^>]*>([^<]+)</h3>", block)
        if m_name:
            name_zh = html.unescape(m_name.group(1)).strip()
        m_img = re.search(r'src="(https://assets\\.pokopiaguide\\.com/pokemon/[^"]+)"', block)
        image_url = m_img.group(1) if m_img else None
        slug = None
        if m_img:
            slug = os.path.splitext(os.path.basename(m_img.group(1)))[0]
        rows.append(
            {
                "dex_no": dex_no,
                "slug": slug,
                "name_zh": name_zh,
                "image_url": image_url,
                "source_url": f"https://pokopiaguide.com/zh-Hans/pokedex/{slug}" if slug else url,
            }
        )
    return rows


def extract_translations_from_pokedex_page(url: str) -> dict:
    text = fetch(url)

    def extract_map(key: str) -> dict:
        pattern = key + r'\\\":\{(.*?)\}'
        m = re.search(pattern, text, flags=re.S)
        if not m:
            return {}
        body = m.group(1)
        body = body.replace("\\\"", "\"").replace("\\\\", "\\")
        pairs = re.findall(r'"([^"]+)":"([^"]+)"', body)
        return {k: v for k, v in pairs}

    translations = {
        "types": extract_map("types"),
        "specialties": extract_map("specialties"),
        "favorites": extract_map("favorites"),
        "weather": extract_map("weather"),
        "rarity": extract_map("rarity"),
        "obtainMethods": extract_map("obtainMethods"),
        "timeOfDay": {
            "dawn": "黎明",
            "day": "白天",
            "dusk": "黄昏",
            "night": "夜晚",
        },
    }
    return translations


def extract_next_f_array(text: str, key: str, hint: str | None = None) -> list | None:
    chunks = re.findall(r'self.__next_f.push\\(\\[1,\"(.*?)\"\\]\\)', text, flags=re.S)
    for c in chunks:
        if hint and hint not in c:
            continue
        if key not in c:
            continue
        unescaped = (
            c.replace("\\\"", "\"")
            .replace("\\n", "\n")
            .replace("\\\\", "\\")
        )
        idx = unescaped.find(f"\"{key}\"")
        if idx == -1:
            continue
        start = unescaped.find("[", idx)
        if start == -1:
            continue
        level = 0
        end = None
        in_string = False
        escape = False
        for i in range(start, len(unescaped)):
            ch = unescaped[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == "\"":
                    in_string = False
                continue
            if ch == "\"":
                in_string = True
                continue
            if ch == "[":
                level += 1
            elif ch == "]":
                level -= 1
                if level == 0:
                    end = i + 1
                    break
        if end is None:
            continue
        try:
            return json.loads(unescaped[start:end])
        except json.JSONDecodeError:
            continue
    return None


def probe_internal_interface(url: str) -> dict:
    text = fetch(url)
    return {
        "url": url,
        "has_next_data": "__NEXT_DATA__" in text or "/_next/data" in text,
        "has_next_f": "self.__next_f" in text,
        "script_count": len(re.findall(r"<script[^>]+src=", text)),
    }


def main():
    sections = None
    if len(sys.argv) > 1:
        for i, arg in enumerate(sys.argv[1:], 1):
            if arg in ("--sections", "-s") and i < len(sys.argv) - 1:
                sections = {s.strip() for s in sys.argv[i + 1].split(",") if s.strip()}
                break

    def enabled(name: str) -> bool:
        return sections is None or name in sections

    if enabled("probe"):
        probe = {
            "items": probe_internal_interface("https://pokopiaguide.com/zh-Hans/items"),
            "pokedex": probe_internal_interface("https://pokopiaguide.com/zh-Hans/pokedex"),
            "habitat": probe_internal_interface("https://pokopiaguide.com/zh-Hans/habitat"),
        }
        write_jsonl(os.path.join(RAW_DIR, "pokopiaguide_probe.jsonl"), [probe])

    if enabled("pokedex"):
        pokedex_slugs = get_pokedex_slugs()
        pokemon_rows = []
        for i, slug in enumerate(pokedex_slugs, 1):
            pokemon_rows.append(parse_pokemon_page(slug, "zh-Hans"))
            if i % 50 == 0:
                time.sleep(0.3)
        write_jsonl(os.path.join(RAW_DIR, "pokopiaguide_pokedex_zh.jsonl"), pokemon_rows)

        pokemon_en_rows = []
        for i, slug in enumerate(pokedex_slugs, 1):
            pokemon_en_rows.append(parse_pokemon_page(slug, "pokedex"))
            if i % 50 == 0:
                time.sleep(0.3)
        write_jsonl(os.path.join(RAW_DIR, "pokopiaguide_pokedex_en.jsonl"), pokemon_en_rows)

    if enabled("habitats"):
        habitat_slugs = get_habitat_slugs_from_local()
        habitat_rows = []
        for i, slug in enumerate(habitat_slugs, 1):
            row = parse_habitat_page(slug)
            if row:
                habitat_rows.append(row)
            if i % 50 == 0:
                time.sleep(0.2)
        write_jsonl(os.path.join(RAW_DIR, "pokopiaguide_habitats_zh.jsonl"), habitat_rows)

    if enabled("materials"):
        material_slugs = get_material_slugs()
        material_rows = []
        for i, slug in enumerate(material_slugs, 1):
            row = parse_material_page(slug)
            if row:
                material_rows.append(row)
            if i % 80 == 0:
                time.sleep(0.2)
        write_jsonl(os.path.join(RAW_DIR, "pokopiaguide_materials_zh.jsonl"), material_rows)

    if enabled("items"):
        items_rows = parse_items_page("https://pokopiaguide.com/zh-Hans/items")
        write_jsonl(os.path.join(RAW_DIR, "pokopiaguide_items_zh.jsonl"), items_rows)

    if enabled("crafting"):
        crafting_rows = parse_crafting_page("https://pokopiaguide.com/zh-Hans/crafting")
        write_jsonl(os.path.join(RAW_DIR, "pokopiaguide_crafting_zh.jsonl"), crafting_rows)

    if enabled("cooking"):
        cooking_rows = parse_cooking_page("https://pokopiaguide.com/zh-Hans/cooking")
        write_jsonl(os.path.join(RAW_DIR, "pokopiaguide_cooking_zh.jsonl"), cooking_rows)

    if enabled("pokedex_list"):
        pokedex_rows = parse_pokedex_list_page("https://pokopiaguide.com/zh-Hans/pokedex")
        write_jsonl(os.path.join(RAW_DIR, "pokopiaguide_pokedex_list_zh.jsonl"), pokedex_rows)

    if enabled("translations"):
        translations = extract_translations_from_pokedex_page("https://pokopiaguide.com/zh-Hans/pokedex")
        os.makedirs(RAW_DIR, exist_ok=True)
        with open(os.path.join(RAW_DIR, "pokopiaguide_translations_zh.json"), "w", encoding="utf-8") as f:
            json.dump(translations, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
