import argparse
import json
import os
import re
from typing import Iterable


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data", "processed")


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


def tokenize(q: str) -> list[str]:
    q = q.strip()
    if not q:
        return []
    tokens = re.split(r"\s+", q)
    return [t.lower() for t in tokens if t]


def match_score(text: str, tokens: Iterable[str]) -> int:
    t = text.lower()
    score = 0
    for tok in tokens:
        if tok in t:
            score += 1
    return score


def search_rows(rows: list[dict], fields: list[str], tokens: list[str], limit: int) -> list[dict]:
    scored = []
    for row in rows:
        parts = []
        for f in fields:
            v = row.get(f)
            if isinstance(v, list):
                parts.append(" ".join(str(x) for x in v))
            elif v is not None:
                parts.append(str(v))
        text = " | ".join(parts)
        score = match_score(text, tokens)
        if score > 0:
            scored.append((score, row))
    scored.sort(key=lambda x: (-x[0], str(x[1].get("name_en") or x[1].get("name") or "")))
    return [r for _, r in scored[:limit]]


def print_rows(title: str, rows: list[dict], fields: list[str]) -> None:
    if not rows:
        return
    print(f"\n== {title} ==")
    for row in rows:
        display = []
        for f in fields:
            v = row.get(f)
            if v is None:
                continue
            if isinstance(v, list):
                v = ", ".join(str(x) for x in v)
            display.append(f"{f}={v}")
        print("- " + "; ".join(display))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?", default="", help="search keywords")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    q = args.query.strip()
    if not q:
        print("Usage: python scripts/search_demo.py \"keyword\"")
        return
    tokens = tokenize(q)

    pokemon = read_jsonl(os.path.join(DATA_DIR, "pokemon.jsonl"))
    habitats = read_jsonl(os.path.join(DATA_DIR, "habitats.jsonl"))
    items = read_jsonl(os.path.join(DATA_DIR, "items.jsonl"))
    furniture = read_jsonl(os.path.join(DATA_DIR, "furniture.jsonl"))
    cosmetics = read_jsonl(os.path.join(DATA_DIR, "cosmetics.jsonl"))

    pokemon_hits = search_rows(
        pokemon,
        ["dex_no", "name_en", "name_zh", "types", "favorites", "rarity", "time", "weather", "slug"],
        tokens,
        args.limit,
    )
    habitat_hits = search_rows(
        habitats,
        ["id", "name", "required", "slug"],
        tokens,
        args.limit,
    )
    item_hits = search_rows(
        items,
        ["name"],
        tokens,
        args.limit,
    )
    furniture_hits = search_rows(
        furniture,
        ["name"],
        tokens,
        args.limit,
    )
    cosmetic_hits = search_rows(
        cosmetics,
        ["name", "location"],
        tokens,
        args.limit,
    )

    print_rows("Pokemon", pokemon_hits, ["dex_no", "name_en", "name_zh", "types", "favorites"])
    print_rows("Habitats", habitat_hits, ["id", "name", "required"])
    print_rows("Items", item_hits, ["name"])
    print_rows("Furniture", furniture_hits, ["name"])
    print_rows("Cosmetics", cosmetic_hits, ["name", "location"])


if __name__ == "__main__":
    main()
