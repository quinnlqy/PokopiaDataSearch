import argparse
import html
import json
import os
import re
import time
import urllib.parse
import urllib.request


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def fetch(url: str, timeout: int = 30, retries: int = 2) -> str:
    last_err = None
    for _ in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:
            last_err = e
            time.sleep(0.5)
    raise last_err


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def write_jsonl(path: str, rows) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


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


def slugify_name(name: str) -> str:
    s = name.lower().strip()
    s = s.replace("♀", "f").replace("♂", "m")
    s = s.replace("’", "'")
    s = s.replace(".", "")
    s = s.replace(":", "")
    s = s.replace("'", "")
    s = s.replace(" ", "-")
    s = s.replace("--", "-")
    # Known exceptions for PokeAPI
    special = {
        "mr-mime": "mr-mime",
        "mime-jr": "mime-jr",
        "mr-rime": "mr-rime",
        "farfetchd": "farfetchd",
        "sirfetchd": "sirfetchd",
        "nidoran-f": "nidoran-f",
        "nidoran-m": "nidoran-m",
        "type-null": "type-null",
        "jangmo-o": "jangmo-o",
        "hakamo-o": "hakamo-o",
        "kommo-o": "kommo-o",
        "tapu-koko": "tapu-koko",
        "tapu-lele": "tapu-lele",
        "tapu-bulu": "tapu-bulu",
        "tapu-fini": "tapu-fini",
        "ho-oh": "ho-oh",
        "porygon-z": "porygon-z",
        "flabebe": "flabebe",
    }
    return special.get(s, s)


def download_image(url: str, out_path: str) -> None:
    if not url:
        return
    ensure_dir(os.path.dirname(out_path))
    if os.path.exists(out_path):
        return
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        with open(out_path, "wb") as f:
            f.write(data)
    except Exception:
        return


def extract_links(html_text: str, pattern: str) -> list[str]:
    return sorted(set(re.findall(pattern, html_text)))


def parse_habitats(base_url: str, sleep_s: float, limit: int | None):
    index_url = f"{base_url}/database/habitats"
    index_html = fetch(index_url)
    slugs = extract_links(index_html, r'href="(/database/habitats/[^"]+)"')
    slugs = [s for s in slugs if s != "/database/habitats" and "tbc" not in s]
    if limit:
        slugs = slugs[:limit]

    habitats = []
    for path in slugs:
        url = f"{base_url}{urllib.parse.quote(path, safe='/')}"
        try:
            html_text = fetch(url)
        except Exception:
            continue

        name = None
        req = None
        code = None
        img = None

        m = re.search(r"No<!-- -->:</span><span>(HAB-\d+)</span>", html_text)
        if m:
            code = m.group(1)
        m = re.search(r"Name<!-- -->:</span><span>([^<]+)</span>", html_text)
        if m:
            name = html.unescape(m.group(1)).strip()
        m = re.search(r"Required<!-- -->:</span><span>([^<]+)</span>", html_text)
        if m:
            req = html.unescape(m.group(1)).strip()
        m = re.search(r'src="(https://assets\.pokopiadb\.com/habitats/\d+\.png)"', html_text)
        if m:
            img = m.group(1)

        attracts = []
        for m in re.finditer(r'href="(/database/pokemondex/[^"]+)".*?<img alt="([^"]+)"', html_text, re.S):
            attracts.append({"name": html.unescape(m.group(2)).strip(), "url": f"{base_url}{m.group(1)}"})

        habitats.append(
            {
                "id": code,
                "slug": path.split("/")[-1],
                "name": name,
                "required": req,
                "attracts": attracts,
                "image_url": img,
                "source_url": url,
                "source": "pokopiadb",
            }
        )
        if sleep_s:
            time.sleep(sleep_s)
    return habitats


def parse_pokemondex(base_url: str, sleep_s: float, limit: int | None):
    index_url = f"{base_url}/database/pokemondex"
    index_html = fetch(index_url)
    links = extract_links(index_html, r'href="(/database/pokemondex/[^"]+)"')
    if limit:
        links = links[:limit]

    list_images = {}
    for m in re.finditer(
        r'href="(/database/pokemondex/[^"]+)".*?<img alt="([^"]+)".*?srcSet="[^"]*url=([^&"]+)',
        index_html,
        re.S,
    ):
        slug = m.group(1).split("/")[-1]
        img_url = urllib.parse.unquote(m.group(3))
        if img_url.startswith("http"):
            list_images[slug] = img_url

    pokedex = []
    for path in links:
        url = f"{base_url}{urllib.parse.quote(path, safe='/')}"
        try:
            html_text = fetch(url)
        except Exception:
            continue

        name = None
        dex_no = None
        rarity = None
        types = []
        times = []
        weathers = []
        favorites = []
        habitats = []

        m = re.search(r"Dex No:</span><span>#<!-- -->(\d+)</span>", html_text)
        if m:
            dex_no = m.group(1)
        m = re.search(r"<h1[^>]*>([^<]+)</h1>", html_text)
        if m:
            name = html.unescape(m.group(1)).strip()

        for label, target in [("Types:", types), ("Time:", times), ("Weather:", weathers)]:
            block_match = re.search(rf"{re.escape(label)}.*?</div>", html_text, re.S)
            if block_match:
                block = block_match.group(0)
                for t in re.findall(r'alt="([^"]+)"', block):
                    target.append(html.unescape(t).strip())

        m = re.search(r"Rarity:</span><span>([^<]+)</span>", html_text)
        if m:
            rarity = html.unescape(m.group(1)).strip()

        m = re.search(r"Favorites:</span><span>([^<]+)</span>", html_text)
        if m:
            favorites = [s.strip() for s in html.unescape(m.group(1)).split(",") if s.strip()]

        for m in re.finditer(r'href="(/database/habitats/[^"]+)".*?<img alt="([^"]+)"', html_text, re.S):
            habitats.append({"name": html.unescape(m.group(2)).strip(), "url": f"{base_url}{m.group(1)}"})

        slug = path.split("/")[-1]
        img = list_images.get(slug)

        pokedex.append(
            {
                "dex_no": dex_no,
                "slug": slug,
                "name_en": name,
                "types": types,
                "rarity": rarity,
                "time": times,
                "weather": weathers,
                "favorites": favorites,
                "habitats": habitats,
                "image_url": img,
                "source_url": url,
                "source": "pokopiadb",
            }
        )
        if sleep_s:
            time.sleep(sleep_s)
    return pokedex


def parse_items(base_url: str):
    url = f"{base_url}/database/items"
    html_text = fetch(url)
    items = []
    for m in re.finditer(r'<img alt="([^"]+)"[^>]+src="([^"]+)"[^>]*>.*?<p[^>]*>([^<]+)</p>', html_text, re.S):
        alt = html.unescape(m.group(1)).strip()
        src = m.group(2).strip()
        name = html.unescape(m.group(3)).strip()
        if not name:
            name = alt
        items.append(
            {
                "name": name,
                "image_url": src,
                "source_url": url,
                "source": "pokopiadb",
            }
        )
    seen = set()
    deduped = []
    for item in items:
        key = item["name"]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def parse_serebii_furniture():
    base = "https://www.serebii.net/"
    url = f"{base}pokemonpokopia/furniture.shtml"
    html_text = fetch(url)
    rows = re.findall(r"<tr>.*?</tr>", html_text, re.S)
    items = []
    for row in rows:
        if "img src" not in row:
            continue
        img = re.search(r'img src="([^"]+)"', row)
        cols = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if not img or not cols:
            continue
        name = html.unescape(re.sub(r"<.*?>", "", cols[1]).strip()) if len(cols) > 1 else None
        if not name:
            continue
        img_url = img.group(1)
        if img_url.startswith("/"):
            img_url = base.rstrip("/") + img_url
        elif not img_url.startswith("http"):
            img_url = base + "pokemonpokopia/" + img_url
        items.append(
            {
                "name": name,
                "image_url": img_url,
                "source_url": url,
                "source": "serebii",
            }
        )
    return items


def parse_serebii_customisation():
    base = "https://www.serebii.net/"
    url = f"{base}pokemonpokopia/customisation.shtml"
    html_text = fetch(url)
    tables = re.findall(r"<table.*?>.*?</table>", html_text, re.S)
    rows = []
    for table in tables:
        if "/pokemonpokopia/custom/th/" in table:
            rows = re.findall(r"<tr>(.*?)</tr>", table, re.S)
            break
    cosmetics = []
    for row in rows[1:]:
        if "/pokemonpokopia/custom/th/" not in row:
            continue
        img = re.search(r'img src="([^"]+)"', row)
        cols = [
            html.unescape(re.sub(r"<.*?>", "", c).replace("&nbsp;", " ").strip())
            for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        ]
        if not img or len(cols) < 4:
            continue
        name = cols[1]
        location = cols[3]
        img_url = img.group(1)
        if img_url.startswith("/"):
            img_url = base.rstrip("/") + img_url
        cosmetics.append(
            {
                "name": name,
                "type": "customisation",
                "location": location,
                "image_url": img_url,
                "source_url": url,
                "source": "serebii",
            }
        )
    return cosmetics


def fetch_official_zh_map() -> dict[int, str]:
    url = "https://tw.portal-pokemon.com/play/pokedex/api/v1"
    data = fetch(url, timeout=30, retries=1)
    obj = json.loads(data)
    mapping: dict[int, str] = {}
    for p in obj.get("pokemons", []):
        try:
            zukan_id = int(p.get("zukan_id"))
        except Exception:
            continue
        name_zh = p.get("pokemon_name")
        if name_zh:
            mapping[zukan_id] = name_zh
    return mapping


def fetch_natdex_no_from_pokeapi(name_en: str) -> int | None:
    slug = slugify_name(name_en)
    url = f"https://pokeapi.co/api/v2/pokemon-species/{slug}"
    try:
        data = fetch(url, timeout=10, retries=0)
        obj = json.loads(data)
        return int(obj.get("id"))
    except Exception:
        return None


def add_pokemon_zh_names(
    pokedex_rows: list[dict],
    zh_map: dict[int, str],
    write_every: int | None = None,
    out_path: str | None = None,
    max_updates: int | None = None,
    force: bool = False,
):
    attempted = 0
    natdex_cache: dict[str, int | None] = {}
    for idx, row in enumerate(pokedex_rows, 1):
        if row.get("name_zh") and not force:
            continue
        name_en = row.get("name_en")
        if not name_en:
            continue
        if name_en in natdex_cache:
            natdex_no = natdex_cache[name_en]
        else:
            natdex_no = fetch_natdex_no_from_pokeapi(name_en)
            natdex_cache[name_en] = natdex_no
        row["natdex_no"] = natdex_no
        if not natdex_no:
            continue
        attempted += 1
        try:
            dex_int = int(natdex_no)
        except Exception:
            dex_int = None
        name_zh = zh_map.get(dex_int) if dex_int is not None else None
        row["name_zh"] = name_zh
        row["name_zh_source"] = "The Pokémon Company (tw.portal-pokemon.com)"
        row["name_zh_source_url"] = "https://tw.portal-pokemon.com/play/pokedex/api/v1"
        if write_every and out_path and idx % write_every == 0:
            write_jsonl(out_path, pokedex_rows)
        if max_updates and attempted >= max_updates:
            break


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data")
    parser.add_argument("--sleep", type=float, default=0.3)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--download-images", action="store_true")
    parser.add_argument("--download-images-only", action="store_true")
    parser.add_argument("--download-section", default="")
    parser.add_argument("--section", default="all")
    parser.add_argument("--no-zh", action="store_true")
    parser.add_argument("--add-zh", action="store_true")
    parser.add_argument("--write-every", type=int, default=50)
    parser.add_argument("--zh-batch", type=int, default=0)
    parser.add_argument("--force-zh", action="store_true")
    args = parser.parse_args()

    base = "https://pokopiadb.com"
    out_raw = os.path.join(args.out, "raw")
    out_processed = os.path.join(args.out, "processed")
    out_images = os.path.join(args.out, "images")

    ensure_dir(out_raw)
    ensure_dir(out_processed)
    ensure_dir(out_images)

    limit = args.limit if args.limit and args.limit > 0 else None

    habitats = []
    pokedex = []
    items = []
    furniture = []
    cosmetics = []

    effective_section = args.section
    if args.add_zh and args.section == "all":
        effective_section = "none"

    if effective_section in ("all", "habitats"):
        habitats = parse_habitats(base, args.sleep, limit)
        write_jsonl(os.path.join(out_raw, "pokopiadb_habitats.jsonl"), habitats)

    if effective_section in ("all", "pokedex"):
        pokedex = parse_pokemondex(base, args.sleep, limit)
        if not args.no_zh:
            zh_map = fetch_official_zh_map()
            add_pokemon_zh_names(
                pokedex,
                zh_map,
                args.write_every,
                os.path.join(out_raw, "pokopiadb_pokemondex.jsonl"),
                args.zh_batch or None,
                args.force_zh,
            )
        write_jsonl(os.path.join(out_raw, "pokopiadb_pokemondex.jsonl"), pokedex)

    if args.add_zh:
        pokedex_path = os.path.join(out_raw, "pokopiadb_pokemondex.jsonl")
        pokedex = read_jsonl(pokedex_path)
        zh_map = fetch_official_zh_map()
        add_pokemon_zh_names(
            pokedex,
            zh_map,
            args.write_every,
            pokedex_path,
            args.zh_batch or None,
            args.force_zh,
        )
        write_jsonl(pokedex_path, pokedex)

    if effective_section in ("all", "items"):
        items = parse_items(base)
        write_jsonl(os.path.join(out_raw, "pokopiadb_items.jsonl"), items)

    if effective_section in ("all", "furniture"):
        furniture = parse_serebii_furniture()
        write_jsonl(os.path.join(out_raw, "serebii_furniture.jsonl"), furniture)

    if effective_section in ("all", "cosmetics"):
        cosmetics = parse_serebii_customisation()
        write_jsonl(os.path.join(out_raw, "serebii_customisation.jsonl"), cosmetics)

    # Build processed views from whatever is available on disk
    if not habitats:
        habitats = read_jsonl(os.path.join(out_raw, "pokopiadb_habitats.jsonl"))
    if not pokedex:
        pokedex = read_jsonl(os.path.join(out_raw, "pokopiadb_pokemondex.jsonl"))
    if not items:
        items = read_jsonl(os.path.join(out_raw, "pokopiadb_items.jsonl"))
    if not furniture:
        furniture = read_jsonl(os.path.join(out_raw, "serebii_furniture.jsonl"))
    if not cosmetics:
        cosmetics = read_jsonl(os.path.join(out_raw, "serebii_customisation.jsonl"))

    write_jsonl(os.path.join(out_processed, "habitats.jsonl"), habitats)
    write_jsonl(os.path.join(out_processed, "pokemon.jsonl"), pokedex)
    write_jsonl(os.path.join(out_processed, "items.jsonl"), items)
    write_jsonl(os.path.join(out_processed, "furniture.jsonl"), furniture)
    write_jsonl(os.path.join(out_processed, "cosmetics.jsonl"), cosmetics)

    if args.download_images or args.download_images_only:
        if args.download_images_only:
            habitats = read_jsonl(os.path.join(out_processed, "habitats.jsonl"))
            pokedex = read_jsonl(os.path.join(out_processed, "pokemon.jsonl"))
            items = read_jsonl(os.path.join(out_processed, "items.jsonl"))
            furniture = read_jsonl(os.path.join(out_processed, "furniture.jsonl"))
            cosmetics = read_jsonl(os.path.join(out_processed, "cosmetics.jsonl"))

        sections = {s.strip().lower() for s in args.download_section.split(",") if s.strip()}
        if not sections:
            sections = {"habitats", "pokemon", "items", "furniture", "cosmetics"}

        if "habitats" in sections:
            for row in habitats:
                if row.get("image_url"):
                    ext = os.path.splitext(urllib.parse.urlparse(row["image_url"]).path)[1] or ".png"
                    out = os.path.join(out_images, "habitats", f"{row.get('id') or row.get('slug')}{ext}")
                    download_image(row["image_url"], out)
                    row["image_path"] = out
        if "pokemon" in sections:
            for row in pokedex:
                if row.get("image_url"):
                    ext = os.path.splitext(urllib.parse.urlparse(row["image_url"]).path)[1] or ".png"
                    out = os.path.join(out_images, "pokemon", f"{row.get('dex_no') or row.get('slug')}{ext}")
                    download_image(row["image_url"], out)
                    row["image_path"] = out
        if "items" in sections:
            for row in items:
                if row.get("image_url"):
                    ext = os.path.splitext(urllib.parse.urlparse(row["image_url"]).path)[1] or ".png"
                    name_slug = re.sub(r"[^a-z0-9_-]+", "-", row.get("name", "item").lower()).strip("-")
                    out = os.path.join(out_images, "items", f"{name_slug}{ext}")
                    download_image(row["image_url"], out)
                    row["image_path"] = out
        if "furniture" in sections:
            for row in furniture:
                if row.get("image_url"):
                    ext = os.path.splitext(urllib.parse.urlparse(row["image_url"]).path)[1] or ".png"
                    name_slug = re.sub(r"[^a-z0-9_-]+", "-", row.get("name", "furniture").lower()).strip("-")
                    out = os.path.join(out_images, "furniture", f"{name_slug}{ext}")
                    download_image(row["image_url"], out)
                    row["image_path"] = out
        if "cosmetics" in sections:
            for row in cosmetics:
                if row.get("image_url"):
                    ext = os.path.splitext(urllib.parse.urlparse(row["image_url"]).path)[1] or ".png"
                    name_slug = re.sub(r"[^a-z0-9_-]+", "-", row.get("name", "cosmetic").lower()).strip("-")
                    out = os.path.join(out_images, "cosmetics", f"{name_slug}{ext}")
                    download_image(row["image_url"], out)
                    row["image_path"] = out

        write_jsonl(os.path.join(out_processed, "habitats.jsonl"), habitats)
        write_jsonl(os.path.join(out_processed, "pokemon.jsonl"), pokedex)
        write_jsonl(os.path.join(out_processed, "items.jsonl"), items)
        write_jsonl(os.path.join(out_processed, "furniture.jsonl"), furniture)
        write_jsonl(os.path.join(out_processed, "cosmetics.jsonl"), cosmetics)


if __name__ == "__main__":
    main()
