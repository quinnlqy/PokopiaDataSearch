"""
match_item_images.py
====================
将 miniprogram/data/items.js 里的中文道具名，通过以下流程
匹配到本地图片库（英文 slug 命名）并写入 image_path 字段：

  中文名
    → Google Translate (zh-CN → en)
    → rapidfuzz 模糊匹配 serebii 英文名列表
    → serebii 图片文件名 (alarmclock.png)
    → 与本地文件 (alarm-clock.png) 对应
    → 写入 items.js 的 image_path

用法：
  python scripts/match_item_images.py [--dry-run] [--skip-translate]

选项：
  --dry-run         不修改 items.js，只输出报告
  --skip-translate  跳过翻译步骤，直接使用缓存（若无缓存则出错）
  --threshold N     模糊匹配最低分 (0-100)，默认 72
"""

import argparse
import json
import os
import re
import sys
import time
import random
import unicodedata
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# 路径
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
MINI_DIR = BASE_DIR / "miniprogram"
ITEMS_JS = MINI_DIR / "data" / "items.js"
ITEMS_IMG_DIR = MINI_DIR / "images" / "items"
CACHE_FILE = BASE_DIR / "data" / "processed" / "item_translate_cache.json"
REPORT_PATH = BASE_DIR / "match_review.md"

# ─────────────────────────────────────────────
# 工具函数
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


def slugify_en(text: str) -> str:
    """英文名 → slug，与本地文件命名一致"""
    s = text.lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def strip_nohyphen(filename: str) -> str:
    """serebii 文件名（无连字符，如 alarmclock）→ 标准化用于比较"""
    return re.sub(r"[^a-z0-9]", "", filename.lower())


# ─────────────────────────────────────────────
# 1. 爬 serebii 获取英文名列表
# ─────────────────────────────────────────────
def fetch_serebii_items() -> list[dict]:
    """
    返回 [{"name": "Alarm Clock", "filename": "alarmclock.png", "slug": "alarm-clock"}, ...]
    """
    import requests
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36"
    headers = {"User-Agent": UA, "Referer": "https://www.serebii.net/"}
    url = "https://www.serebii.net/pokemonpokopia/items.shtml"
    r = requests.get(url, headers=headers, timeout=30, verify=False)
    r.raise_for_status()

    # 从 <tr> 行提取：图片文件名 + 英文名
    # 格式：<img src="items/alarmclock.png" ... alt="Alarm Clock" /><td ...>Alarm Clock</td>
    pattern = re.compile(
        r'<img\s+src="items/([^"]+\.png)"[^>]*alt="([^"]+)"',
        re.I,
    )
    seen = set()
    results = []
    for m in pattern.finditer(r.text):
        filename = m.group(1)   # alarmclock.png
        name = m.group(2).strip()  # Alarm Clock
        key = filename.lower()
        if key in seen:
            continue
        seen.add(key)
        results.append({
            "name": name,
            "filename": filename,
            "slug": slugify_en(name),
            "nohyphen": strip_nohyphen(os.path.splitext(filename)[0]),
        })
    return results


# ─────────────────────────────────────────────
# 2. 翻译 + 缓存
# ─────────────────────────────────────────────
def load_cache() -> dict:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def translate_batch(names: list[str], cache: dict, skip: bool = False) -> dict:
    """
    返回 {zh_name: en_translated} 字典，结果写入 cache
    使用 GoogleTranslator，失败则回退到原名
    """
    from deep_translator import GoogleTranslator

    translator = GoogleTranslator(source="zh-CN", target="en")
    to_translate = [n for n in names if n not in cache]

    if skip and to_translate:
        print(f"  [WARN] --skip-translate 但有 {len(to_translate)} 条未缓存，将使用原名")

    total = len(to_translate)
    print(f"  需要翻译 {total} 条（缓存命中 {len(names)-total} 条）")

    BATCH = 50  # Google Translate 每次最多 50 条
    for i in range(0, total, BATCH):
        batch = to_translate[i:i + BATCH]
        pct = int((i + len(batch)) / total * 100) if total else 100
        print(f"  翻译进度: {i+len(batch)}/{total} ({pct}%)...")

        if skip:
            for n in batch:
                cache[n] = n  # 直接用原名
            continue

        # 单条翻译（更稳定）
        for name in batch:
            try:
                translated = translator.translate(name)
                cache[name] = translated or name
            except Exception as e:
                print(f"    [WARN] 翻译失败 {name!r}: {e}，使用原名")
                cache[name] = name
            # 随机延迟，避免频率限制
            time.sleep(0.3 + random.random() * 0.4)

        save_cache(cache)

    return cache


# ─────────────────────────────────────────────
# 3. 模糊匹配
# ─────────────────────────────────────────────
def match_translated_to_serebii(
    zh_name: str,
    en_translated: str,
    serebii_items: list[dict],
    threshold: int = 72,
) -> dict | None:
    """
    用翻译后的英文名与 serebii 英文名列表做模糊匹配
    返回 {"name", "filename", "slug", "score", "method"} 或 None
    """
    from rapidfuzz import process, fuzz

    candidates = [s["name"] for s in serebii_items]

    # ① 精确匹配（忽略大小写）
    en_lower = en_translated.lower().strip()
    for item in serebii_items:
        if item["name"].lower() == en_lower:
            return {
                "matched_name": item["name"],
                "filename": item["filename"],
                "slug": item["slug"],
                "score": 100.0,
                "method": "exact",
            }

    # ② 防止短词误匹配：如果翻译结果很短（<=10字符），提高阈值并要求
    #    匹配结果长度不超过翻译结果的 2.5 倍
    effective_threshold = threshold
    max_len_ratio = None
    if len(en_lower) <= 10:
        effective_threshold = max(threshold, 85)
        max_len_ratio = 2.5

    # ③ token_sort_ratio（词序无关）
    match1 = process.extractOne(en_translated, candidates, scorer=fuzz.token_sort_ratio)
    # ④ WRatio（综合）
    match2 = process.extractOne(en_translated, candidates, scorer=fuzz.WRatio)

    # 取较高分的
    best = None
    if match1 and match2:
        best = match1 if match1[1] >= match2[1] else match2
    elif match1:
        best = match1
    elif match2:
        best = match2

    if not best or best[1] < effective_threshold:
        return None

    matched_name = best[0]
    score = best[1]

    # 检查长度比例（防止短词匹配到超长名称）
    if max_len_ratio is not None:
        if len(matched_name) > len(en_translated) * max_len_ratio:
            return None

    item = next((s for s in serebii_items if s["name"] == matched_name), None)
    if not item:
        return None

    return {
        "matched_name": matched_name,
        "filename": item["filename"],
        "slug": item["slug"],
        "score": score,
        "method": "token_sort" if best is match1 else "WRatio",
    }


# ─────────────────────────────────────────────
# 4. 本地文件验证
# ─────────────────────────────────────────────
def build_local_index() -> dict[str, str]:
    """slug → 实际文件名（可能大小写、连字符略有不同）"""
    index = {}
    if not ITEMS_IMG_DIR.exists():
        return index
    for f in ITEMS_IMG_DIR.iterdir():
        if f.suffix.lower() == ".png":
            index[f.stem.lower()] = f.name
    return index


def find_local_file(slug: str, local_index: dict) -> str | None:
    """尝试几种变体在本地找文件"""
    variants = [slug]
    # serebii 文件名去掉连字符版
    nohyphen = slug.replace("-", "")
    variants.append(nohyphen)
    for v in variants:
        if v in local_index:
            return local_index[v]
    return None


def download_from_serebii(filename: str, slug: str, dry_run: bool = False) -> bool:
    """从 serebii 下载单张道具图片，保存为 slug.png"""
    import requests
    if dry_run:
        return False  # dry-run 时不下载，只报告
    url = f"https://www.serebii.net/pokemonpokopia/items/{filename}"
    out_path = ITEMS_IMG_DIR / f"{slug}.png"
    if out_path.exists():
        return True
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36"
    headers = {"User-Agent": UA, "Referer": "https://www.serebii.net/pokemonpokopia/"}
    # 随机延迟
    time.sleep(0.5 + random.random() * 1.5)
    try:
        r = requests.get(url, headers=headers, timeout=20, verify=False)
        if r.status_code == 200 and len(r.content) > 500:
            ITEMS_IMG_DIR.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(r.content)
            return True
    except Exception as e:
        print(f"    [WARN] serebii download failed {filename}: {e}", file=sys.stderr)
    return False


# ─────────────────────────────────────────────
# 5. 主流程
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-translate", action="store_true")
    parser.add_argument("--threshold", type=int, default=72)
    args = parser.parse_args()

    print("=== Pokopia Item Image Matcher ===")
    print(f"threshold={args.threshold} dry_run={args.dry_run}")
    print()

    # ── 加载 items.js ──
    print("[1] Loading items.js...")
    items = load_js_array(ITEMS_JS)
    # 只处理 image_path 为 null 的条目
    need_match = [
        it for it in items
        if not it.get("image_path") or not (MINI_DIR / it["image_path"].lstrip("/")).exists()
    ]
    print(f"    total={len(items)}, need_image_path={len(need_match)}")

    # ── 爬 serebii ──
    print("[2] Fetching serebii item list...")
    serebii_items = fetch_serebii_items()
    print(f"    serebii items: {len(serebii_items)}")

    # ── 建本地索引 ──
    local_index = build_local_index()
    print(f"    local image files: {len(local_index)}")

    # ── 翻译 ──
    print("[3] Translating zh names...")
    cache = load_cache()
    zh_names = list({it.get("name_zh") or it.get("name") or "" for it in need_match if it.get("name_zh") or it.get("name")})
    cache = translate_batch(zh_names, cache, skip=args.skip_translate)

    # ── 匹配 ──
    print("[4] Fuzzy matching...")
    results_high = []   # score >= 88
    results_mid = []    # threshold <= score < 88
    results_low = []    # score < threshold (需人工)
    results_none = []   # 无 URL 也无匹配

    item_map = {id(it): it for it in items}

    for it in need_match:
        zh = it.get("name_zh") or it.get("name") or ""
        en_trans = cache.get(zh, zh)

        entry = {
            "key": it.get("key"),
            "zh_name": zh,
            "en_translated": en_trans,
            "image_url": it.get("image_url") or "",
            "_item_ref": it,
        }

        # ── 优先：image_url 已经是本地相对路径（如 /images/items/firepit.png）
        img_url = it.get("image_url") or ""
        if img_url.startswith("/images/items/"):
            local_path = MINI_DIR / img_url.lstrip("/")
            if local_path.exists():
                entry["image_path"] = img_url
                entry["matched_name"] = "(local path in image_url)"
                entry["score"] = 100
                entry["local_file"] = local_path.name
                results_high.append(entry)
                continue

        match = match_translated_to_serebii(zh, en_trans, serebii_items, threshold=args.threshold)

        if match:
            local_file = find_local_file(match["slug"], local_index)
            entry["matched_name"] = match["matched_name"]
            entry["matched_slug"] = match["slug"]
            entry["score"] = match["score"]
            entry["local_file"] = local_file

            if local_file:
                entry["image_path"] = f"/images/items/{local_file}"
                if match["score"] >= 88:
                    results_high.append(entry)
                else:
                    results_mid.append(entry)
            else:
                # 本地无此文件，但 serebii 有 → 尝试下载
                dl_ok = download_from_serebii(
                    match["filename"], match["slug"], dry_run=args.dry_run
                )
                if dl_ok:
                    # 重新刷新本地索引
                    local_index[match["slug"]] = match["slug"] + ".png"
                    entry["local_file"] = match["slug"] + ".png"
                    entry["image_path"] = f"/images/items/{match['slug']}.png"
                    entry["downloaded"] = True
                    if match["score"] >= 88:
                        results_high.append(entry)
                    else:
                        results_mid.append(entry)
                else:
                    entry["local_file"] = None
                    results_low.append(entry)
        else:
            results_low.append(entry)

    print(f"    high confidence (>=88): {len(results_high)}")
    print(f"    mid confidence  (>={args.threshold}): {len(results_mid)}")
    print(f"    low / no match: {len(results_low)}")

    # ── 写回 items.js ──
    if not args.dry_run:
        write_count = 0
        for entry in results_high + results_mid:
            if entry.get("image_path"):
                entry["_item_ref"]["image_path"] = entry["image_path"]
                write_count += 1
        if write_count:
            save_js_array(ITEMS_JS, items)
            print(f"\n[5] Wrote {write_count} image_path entries to items.js")
        else:
            print("\n[5] Nothing to write")
    else:
        print("\n[5] DRY-RUN: items.js not modified")

    # ── 写报告 ──
    write_report(results_high, results_mid, results_low, args.dry_run, args.threshold)


# ─────────────────────────────────────────────
# 6. 报告
# ─────────────────────────────────────────────
def write_report(high, mid, low, dry_run, threshold):
    lines = [
        "# 道具图片匹配审查报告",
        "",
        f"> 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"> 阈值：{threshold} | 模式：{'DRY-RUN' if dry_run else '已写入'}",
        "",
        "---",
        "",
        f"## 汇总",
        f"| 类别 | 数量 |",
        f"|---|---|",
        f"| 高置信度匹配（>=88，已自动写入） | {len(high)} |",
        f"| 中置信度匹配（>={threshold}，已自动写入） | {len(mid)} |",
        f"| 低置信度 / 无匹配（需人工审查） | {len(low)} |",
        "",
        "---",
        "",
    ]

    if high:
        lines += [
            "## 高置信度匹配（score >= 88）",
            "| 中文名 | 翻译 | 匹配英文名 | 本地文件 | score |",
            "|---|---|---|---|---|",
        ]
        for e in high:
            lines.append(
                f"| {e['zh_name']} | {e['en_translated']} | {e.get('matched_name','')} "
                f"| `{e.get('local_file','')}` | {e.get('score','')} |"
            )
        lines.append("")

    if mid:
        lines += [
            f"## 中置信度匹配（score {threshold}-87）",
            "| 中文名 | 翻译 | 匹配英文名 | 本地文件 | score |",
            "|---|---|---|---|---|",
        ]
        for e in mid:
            lines.append(
                f"| {e['zh_name']} | {e['en_translated']} | {e.get('matched_name','')} "
                f"| `{e.get('local_file','')}` | {e.get('score','')} |"
            )
        lines.append("")

    if low:
        lines += [
            "## 低置信度 / 无匹配（需人工处理）",
            "| 中文名 | 翻译结果 | 最佳猜测 | score | 现有URL |",
            "|---|---|---|---|---|",
        ]
        for e in low:
            lines.append(
                f"| {e['zh_name']} | {e['en_translated']} "
                f"| {e.get('matched_name','-')} | {e.get('score','-')} "
                f"| {e['image_url'] or '-'} |"
            )
        lines.append("")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
