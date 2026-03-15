import html
import json
import os
import re
import urllib.request


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")


def fetch(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


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
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def extract_lines(url: str) -> list[str]:
    text = fetch(url)
    text = re.sub(r"<script.*?</script>", "", text, flags=re.S)
    text = re.sub(r"<style.*?</style>", "", text, flags=re.S)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = html.unescape(text)
    return [l.strip() for l in text.split("\n") if l.strip()]


def parse_habitat_guide(lines: list[str]) -> dict[str, dict]:
    result = {}
    i = 0
    while i < len(lines):
        if lines[i].startswith("No."):
            no = lines[i].replace("No.", "").strip()
            if i + 3 < len(lines):
                name_zh = lines[i + 1]
                required_item = lines[i + 2]
                required_qty = lines[i + 3]
                attracts = []
                j = i + 4
                while j < len(lines) and not lines[j].startswith("No."):
                    attracts.append(lines[j])
                    j += 1
                result[no] = {
                    "name_zh": name_zh,
                    "required_item_zh": required_item,
                    "required_qty": required_qty,
                    "attracts_zh": attracts,
                }
                i = j
                continue
        i += 1
    return result


def parse_pokedex(lines: list[str]) -> dict[int, dict]:
    result = {}
    i = 0
    while i < len(lines):
        if lines[i].startswith("No."):
            no = lines[i].replace("No.", "").strip()
            if i + 5 < len(lines):
                name_zh = lines[i + 1]
                teach_move = lines[i + 2]
                specialty = lines[i + 3]
                habitat_zh = lines[i + 4]
                condition = lines[i + 5]
                try:
                    no_int = int(no)
                except Exception:
                    no_int = None
                if no_int:
                    result[no_int] = {
                        "name_zh_hubs": name_zh,
                        "teach_move": teach_move,
                        "specialty": specialty,
                        "habitat_zh": habitat_zh,
                        "spawn_condition": condition,
                    }
                i += 6
                continue
        i += 1
    return result


def main():
    habitats_path = os.path.join(PROCESSED_DIR, "habitats.jsonl")
    pokemon_path = os.path.join(PROCESSED_DIR, "pokemon.jsonl")
    habitats = read_jsonl(habitats_path)
    pokemon = read_jsonl(pokemon_path)

    habitat_lines = extract_lines("https://pokemonhubs.com/pokopia/habitat-guide/")
    habitat_map = parse_habitat_guide(habitat_lines)

    for h in habitats:
        code = h.get("id", "")
        if code.startswith("HAB-"):
            no = code.replace("HAB-", "")
            if no in habitat_map:
                h["name_zh"] = habitat_map[no]["name_zh"]
                h["required_zh"] = f"{habitat_map[no]['required_item_zh']} {habitat_map[no]['required_qty']}"
                h["attracts_zh"] = habitat_map[no]["attracts_zh"]

    pokedex_lines = extract_lines("https://pokemonhubs.com/pokopia/pokedex/")
    pokedex_map = parse_pokedex(pokedex_lines)

    for p in pokemon:
        natdex = p.get("natdex_no")
        try:
            natdex_int = int(natdex) if natdex is not None else None
        except Exception:
            natdex_int = None
        if natdex_int and natdex_int in pokedex_map:
            p.update(pokedex_map[natdex_int])

    write_jsonl(habitats_path, habitats)
    write_jsonl(pokemon_path, pokemon)


if __name__ == "__main__":
    main()
