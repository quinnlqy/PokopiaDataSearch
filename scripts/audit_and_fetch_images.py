"""
audit_and_fetch_images.py
=========================
功能：
  1. 扫描 miniprogram/data/items.js 和 habitats.js，找出 image_path 为 null 的条目
  2. 尝试用名称 slug 在本地图片库中模糊匹配已有图片
  3. 输出缺失图片报告到 missing_images_report.md
  4. 对仍然缺失的条目，从远程 URL 下载图片到本地
     并将 image_path 写回 data 文件（替换 null）

用法：
  python scripts/audit_and_fetch_images.py [--dry-run] [--category items|habitats|all]

选项：
  --dry-run     只报告，不下载，不修改数据文件
  --category    指定处理类别，默认 all
"""

import argparse
import json
import os
import random
import re
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

# ─────────────────────────────────────────────
# 路径配置
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
MINI_DIR = BASE_DIR / "miniprogram"
DATA_DIR = MINI_DIR / "data"
IMG_DIR = MINI_DIR / "images"
REPORT_PATH = BASE_DIR / "missing_images_report.md"

ITEMS_JS = DATA_DIR / "items.js"
HABITATS_JS = DATA_DIR / "habitats.js"

ITEMS_IMG_DIR = IMG_DIR / "items"
HABITATS_IMG_DIR = IMG_DIR / "habitats"

# processed data 目录（含中英文名称映射）
PROCESSED_DIR = BASE_DIR / "data" / "processed"

# ─────────────────────────────────────────────
# 伪装请求头池（模拟真实浏览器）
# ─────────────────────────────────────────────
UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
]

REFERER_MAP = {
    "pokopiaguide.com": "https://pokopiaguide.com/zh-Hans/items",
    "pokopiadb.com": "https://pokopiadb.com/database/habitats",
    "assets.pokopiadb.com": "https://pokopiadb.com/",
    "serebii.net": "https://www.serebii.net/pokemonpokopia/",
}


def get_headers(url: str) -> dict:
    ua = random.choice(UA_POOL)
    referer = None
    for domain, ref in REFERER_MAP.items():
        if domain in url:
            referer = ref
            break
    headers = {
        "User-Agent": ua,
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
    }
    if referer:
        headers["Referer"] = referer
    return headers


# ─────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────
def slugify(text: str) -> str:
    """把中文/英文名称转成 slug，用于本地图片文件名匹配"""
    s = text.lower().strip()
    # 去掉 Unicode 变音符号
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[♀♂]", "", s)
    s = re.sub(r"[^a-z0-9\s\-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def load_js_array(path: Path) -> list[dict]:
    """读取 module.exports = [...] 格式的 JS 文件"""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^module\.exports\s*=\s*", text)
    if m:
        text = text[m.end():]
    text = text.rstrip().rstrip(";")
    return json.loads(text)


def save_js_array(path: Path, data: list[dict]) -> None:
    """把数组写回 module.exports = [...] 格式"""
    content = "module.exports = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n"
    path.write_text(content, encoding="utf-8")


def build_local_file_index(directory: Path) -> dict[str, Path]:
    """建立本地图片文件名（不带扩展名）-> 路径 的索引"""
    index = {}
    if not directory.exists():
        return index
    for f in directory.iterdir():
        if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
            index[f.stem.lower()] = f
    return index


def build_zh_to_en_map() -> dict[str, str]:
    """
    从 data/processed/items.jsonl 建立 中文名 -> 英文slug 的映射
    items.jsonl 中含有英文 name 和英文 image_url（serebii），
    items_zh.jsonl 中含有 name_zh。
    两者共享 image_url 中的 item-XXX id。
    策略：以 pokopiaguide image_url 中的 item id 为桥接键。
    """
    zh_map: dict[str, str] = {}  # zh_name -> en_slug

    # 先从 items.jsonl 建立 en_slug 索引（英文名 -> slug）
    en_file = PROCESSED_DIR / "items.jsonl"
    en_entries: list[dict] = []
    if en_file.exists():
        with en_file.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    en_entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    # 建立 en_name_lower -> slug 映射
    en_name_to_slug: dict[str, str] = {}
    for e in en_entries:
        name = e.get("name") or ""
        if name:
            en_name_to_slug[name.lower()] = slugify(name)

    # 从 items_zh.jsonl 取中文名，用 pokopiaguide image id 匹配英文条目
    # 策略：pokopiaguide image_url 格式 .../item-XXX.png，id 唯一
    # items.jsonl 的 serebii image_url 格式不含 id，所以改用：
    # 直接将中文 name_zh 通过 slugify 尝试匹配本地文件

    # 另一种策略：读取 miniprogram/data/items.js 中有 name_en 字段的条目
    # 但目前该字段大多为 null，改用 build_mini_item_en_map

    return zh_map


def build_mini_item_slug_map() -> dict[str, str]:
    """
    从 miniprogram/data/items.js 中读取 name_en 字段（如果存在）
    建立 name_zh -> name_en_slug 的映射
    """
    items = load_js_array(ITEMS_JS)
    mapping: dict[str, str] = {}
    for it in items:
        name_en = it.get("name_en") or ""
        name_zh = it.get("name_zh") or it.get("name") or ""
        if name_en and name_zh:
            mapping[name_zh] = slugify(name_en)
    return mapping


def build_pokopiadb_url_to_slug_map() -> dict[str, str]:
    """
    从 data/processed/items.jsonl 建立 pokopiadb URL -> en_slug 映射
    这样可通过 serebii URL 文件名反推 slug
    """
    url_map: dict[str, str] = {}
    en_file = PROCESSED_DIR / "items.jsonl"
    if not en_file.exists():
        return url_map
    with en_file.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            name = e.get("name") or ""
            img_url = e.get("image_url") or ""
            if name and img_url:
                url_map[img_url] = slugify(name)
    return url_map


def find_local_match(name: str, slug_index: dict[str, Path]) -> Path | None:
    """尝试多种 slug 变体在本地索引中找匹配"""
    candidates = set()
    candidates.add(slugify(name))
    # 直接小写
    candidates.add(name.lower().strip().replace(" ", "-").replace("_", "-"))
    # 去掉特殊符号
    clean = re.sub(r"[^a-zA-Z0-9\s\-]", "", name)
    candidates.add(slugify(clean))

    for c in candidates:
        if c and c in slug_index:
            return slug_index[c]
    return None


def download_image(url: str, out_path: Path, dry_run: bool = False) -> bool:
    """下载单张图片，模拟人类请求行为"""
    if not url or not url.startswith("http"):
        return False
    if out_path.exists():
        return True  # 已存在，跳过
    if dry_run:
        return False

    out_path.parent.mkdir(parents=True, exist_ok=True)
    headers = get_headers(url)

    # 随机延迟 0.5~2.5 秒
    delay = 0.5 + random.random() * 2.0
    time.sleep(delay)

    try:
        import requests as req_lib
        import warnings as _w
        _w.filterwarnings("ignore")
        r = req_lib.get(url, headers=headers, timeout=30, verify=False)
        if r.status_code != 200 or len(r.content) < 500:
            return False
        out_path.write_bytes(r.content)
        return True
    except Exception as e:
        print(f"  [WARN] download failed {url}: {e}", file=sys.stderr)
        return False


def habitat_id_to_path(hab_id: str, img_dir: Path) -> Path:
    """栖息地图片路径，按照 HAB-XXX.png 命名"""
    num = re.sub(r"\D", "", hab_id)
    filename = f"HAB-{int(num):03d}.png"
    return img_dir / filename


def item_name_to_path(name_en: str, img_dir: Path) -> Path:
    """道具图片路径，按照英文 slug 命名"""
    slug = slugify(name_en) if name_en else ""
    return img_dir / f"{slug}.png"


# ─────────────────────────────────────────────
# 核心审计逻辑
# ─────────────────────────────────────────────
def audit_items(dry_run: bool) -> tuple[list[dict], list[dict], list[dict]]:
    """
    返回 (matched, downloaded, still_missing)
    matched    = 本地已有文件、通过名称匹配补齐 image_path 的条目
    downloaded = 从网络下载成功的条目
    still_missing = 下载失败/无 URL 的条目
    """
    items = load_js_array(ITEMS_JS)
    slug_index = build_local_file_index(ITEMS_IMG_DIR)

    # 建立辅助映射
    mini_slug_map = build_mini_item_slug_map()           # name_zh -> en_slug (from items.js name_en)
    url_to_slug = build_pokopiadb_url_to_slug_map()      # serebii URL -> en_slug

    matched = []
    downloaded = []
    still_missing = []
    modified = False

    for entry in items:
        # 已有 image_path 且文件存在，直接跳过
        if entry.get("image_path"):
            ip = MINI_DIR / entry["image_path"].lstrip("/")
            if ip.exists():
                continue

        name_zh = entry.get("name_zh") or entry.get("name") or ""
        name_en = entry.get("name_en") or ""
        image_url = entry.get("image_url") or ""

        local_file = None

        # ① 如果有英文名，先用英文 slug 在本地找
        if name_en:
            local_file = find_local_match(name_en, slug_index)

        # ② 用 items.js 中的 name_en 预建映射
        if not local_file and name_zh and name_zh in mini_slug_map:
            en_slug = mini_slug_map[name_zh]
            if en_slug and en_slug in slug_index:
                local_file = slug_index[en_slug]

        # ③ 用 image_url 的 serebii 文件名反推 slug
        if not local_file and image_url:
            en_slug = url_to_slug.get(image_url)
            if en_slug and en_slug in slug_index:
                local_file = slug_index[en_slug]
            else:
                # 从 serebii URL 直接提取文件名，去掉空格并 slugify
                url_basename = os.path.splitext(os.path.basename(image_url))[0]
                url_slug = slugify(url_basename)
                if url_slug in slug_index:
                    local_file = slug_index[url_slug]

        # ④ 用中文名 slugify 后匹配（有时中文会被转为拼音或英文）
        if not local_file:
            local_file = find_local_match(name_zh, slug_index)

        if local_file:
            rel = "/images/items/" + local_file.name
            entry["image_path"] = rel
            modified = True
            matched.append({
                "key": entry.get("key"),
                "name": name_zh,
                "matched_file": local_file.name,
                "image_url": image_url,
            })
            continue

        # ⑤ 尝试从 image_url 下载（使用英文名作为文件名）
        if image_url and image_url.startswith("http"):
            # 优先使用英文 slug 命名
            if name_en:
                out_name = slugify(name_en) + ".png"
            else:
                # 从 URL 取原始文件名
                out_name = os.path.basename(image_url)
                if not out_name.endswith(".png"):
                    out_name = slugify(name_zh or out_name) + ".png"

            out_path = ITEMS_IMG_DIR / out_name

            ok = download_image(image_url, out_path, dry_run=dry_run)
            if ok or out_path.exists():
                rel = "/images/items/" + out_name
                entry["image_path"] = rel
                modified = True
                downloaded.append({
                    "key": entry.get("key"),
                    "name": name_zh,
                    "image_url": image_url,
                    "saved_as": out_name,
                })
                continue

        # ⑥ 仍然缺失
        still_missing.append({
            "key": entry.get("key"),
            "name": name_zh,
            "image_url": image_url or "(no url)",
        })

    if modified and not dry_run:
        save_js_array(ITEMS_JS, items)

    return matched, downloaded, still_missing


def audit_habitats(dry_run: bool) -> tuple[list[dict], list[dict], list[dict]]:
    habitats = load_js_array(HABITATS_JS)
    slug_index = build_local_file_index(HABITATS_IMG_DIR)

    matched = []
    downloaded = []
    still_missing = []
    modified = False

    for entry in habitats:
        if entry.get("image_path"):
            ip = MINI_DIR / entry["image_path"].lstrip("/")
            if ip.exists():
                continue

        hab_id = entry.get("id") or ""
        name_en = entry.get("name_en") or entry.get("name") or ""
        image_url = entry.get("image_url") or ""

        # ① 检查标准 HAB-XXX.png 是否存在
        if hab_id:
            std_path = habitat_id_to_path(hab_id, HABITATS_IMG_DIR)
            if std_path.exists():
                rel = "/images/habitats/" + std_path.name
                entry["image_path"] = rel
                modified = True
                matched.append({
                    "key": entry.get("key"),
                    "name": name_en,
                    "matched_file": std_path.name,
                    "image_url": image_url,
                })
                continue

        # ② 模糊名称匹配
        local_file = find_local_match(name_en, slug_index)
        if local_file:
            rel = "/images/habitats/" + local_file.name
            entry["image_path"] = rel
            modified = True
            matched.append({
                "key": entry.get("key"),
                "name": name_en,
                "matched_file": local_file.name,
                "image_url": image_url,
            })
            continue

        # ③ 从 image_url 下载（优先用 HAB-XXX 命名）
        if image_url and image_url.startswith("http"):
            # 修正已失效的 assets.pokopiadb.com URL → pokopiadb.com/imgs/habitats/
            # 并统一使用三位数前导零格式（如 082.png）
            if "assets.pokopiadb.com/habitats/" in image_url or "pokopiadb.com/imgs/habitats/" in image_url:
                num_str = re.sub(r"[^0-9]", "", os.path.splitext(os.path.basename(image_url))[0])
                if num_str:
                    image_url = f"https://pokopiadb.com/imgs/habitats/{int(num_str):03d}.png"

            if hab_id:
                out_path = habitat_id_to_path(hab_id, HABITATS_IMG_DIR)
            else:
                ext = os.path.splitext(image_url)[-1] or ".png"
                out_path = HABITATS_IMG_DIR / (slugify(name_en) + ext)

            ok = download_image(image_url, out_path, dry_run=dry_run)
            if ok or out_path.exists():
                rel = "/images/habitats/" + out_path.name
                entry["image_path"] = rel
                modified = True
                downloaded.append({
                    "key": entry.get("key"),
                    "name": name_en,
                    "image_url": image_url,
                    "saved_as": out_path.name,
                })
                continue

        # ④ 检查 image_url 是否是本地相对路径（如 /images/habitats/HAB-080.png）
        if image_url and image_url.startswith("/images/"):
            local_path = MINI_DIR / image_url.lstrip("/")
            if local_path.exists():
                entry["image_path"] = image_url
                modified = True
                matched.append({
                    "key": entry.get("key"),
                    "name": name_en,
                    "matched_file": local_path.name,
                    "image_url": image_url,
                })
                continue

        still_missing.append({
            "key": entry.get("key"),
            "name": name_en,
            "image_url": image_url or "(no url)",
        })

    if modified and not dry_run:
        save_js_array(HABITATS_JS, habitats)

    return matched, downloaded, still_missing


# ─────────────────────────────────────────────
# 报告生成
# ─────────────────────────────────────────────
def write_report(
    items_matched, items_downloaded, items_missing,
    hab_matched, hab_downloaded, hab_missing,
    dry_run: bool,
) -> None:
    lines = [
        "# 图片缺失审计报告",
        "",
        f"> 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"> 模式：{'DRY-RUN（仅审计，未修改）' if dry_run else '实际执行（已更新数据文件）'}",
        "",
        "---",
        "",
        "## 道具（items）",
        "",
        f"- 本地匹配补齐：{len(items_matched)} 条",
        f"- 从网络下载成功：{len(items_downloaded)} 条",
        f"- 仍然缺失：{len(items_missing)} 条",
        "",
    ]

    if items_matched:
        lines += ["### 本地匹配成功", "| 键 | 名称 | 匹配文件 |", "|---|---|---|"]
        for r in items_matched:
            lines.append(f"| `{r['key']}` | {r['name']} | `{r['matched_file']}` |")
        lines.append("")

    if items_downloaded:
        lines += ["### 网络下载成功", "| 键 | 名称 | 原始URL | 保存为 |", "|---|---|---|---|"]
        for r in items_downloaded:
            lines.append(f"| `{r['key']}` | {r['name']} | {r['image_url']} | `{r['saved_as']}` |")
        lines.append("")

    if items_missing:
        lines += ["### 仍然缺失（需手动处理）", "| 键 | 名称 | 已知URL |", "|---|---|---|"]
        for r in items_missing:
            lines.append(f"| `{r['key']}` | {r['name']} | {r['image_url']} |")
        lines.append("")

    lines += [
        "---",
        "",
        "## 栖息地（habitats）",
        "",
        f"- 本地匹配补齐：{len(hab_matched)} 条",
        f"- 从网络下载成功：{len(hab_downloaded)} 条",
        f"- 仍然缺失：{len(hab_missing)} 条",
        "",
    ]

    if hab_matched:
        lines += ["### 本地匹配成功", "| 键 | 名称 | 匹配文件 |", "|---|---|---|"]
        for r in hab_matched:
            lines.append(f"| `{r['key']}` | {r['name']} | `{r['matched_file']}` |")
        lines.append("")

    if hab_downloaded:
        lines += ["### 网络下载成功", "| 键 | 名称 | 原始URL | 保存为 |", "|---|---|---|---|"]
        for r in hab_downloaded:
            lines.append(f"| `{r['key']}` | {r['name']} | {r['image_url']} | `{r['saved_as']}` |")
        lines.append("")

    if hab_missing:
        lines += ["### 仍然缺失（需手动处理）", "| 键 | 名称 | 已知URL |", "|---|---|---|"]
        for r in hab_missing:
            lines.append(f"| `{r['key']}` | {r['name']} | {r['image_url']} |")
        lines.append("")

    lines += [
        "---",
        "",
        "## 汇总",
        "",
        f"| 类别 | 本地匹配 | 网络下载 | 仍缺失 |",
        f"|---|---|---|---|",
        f"| 道具 | {len(items_matched)} | {len(items_downloaded)} | {len(items_missing)} |",
        f"| 栖息地 | {len(hab_matched)} | {len(hab_downloaded)} | {len(hab_missing)} |",
        f"| **合计** | **{len(items_matched)+len(hab_matched)}** | "
        f"**{len(items_downloaded)+len(hab_downloaded)}** | "
        f"**{len(items_missing)+len(hab_missing)}** |",
        "",
    ]

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n报告已写入：{REPORT_PATH}")


# ─────────────────────────────────────────────
# 主程序
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="审计并补齐 Pokopia 图片")
    parser.add_argument("--dry-run", action="store_true", help="只报告，不下载也不修改数据文件")
    parser.add_argument("--category", choices=["items", "habitats", "all"], default="all")
    args = parser.parse_args()

    dry_run = args.dry_run
    category = args.category

    print("=== Pokopia Image Audit Tool ===")
    print(f"Mode: {'DRY-RUN' if dry_run else 'EXECUTE'} | Category: {category}")
    print()

    items_matched, items_downloaded, items_missing = [], [], []
    hab_matched, hab_downloaded, hab_missing = [], [], []

    if category in ("items", "all"):
        print("[items] scanning...")
        items_matched, items_downloaded, items_missing = audit_items(dry_run)
        print(f"  local_match={len(items_matched)}  downloaded={len(items_downloaded)}  missing={len(items_missing)}")

    if category in ("habitats", "all"):
        print("[habitats] scanning...")
        hab_matched, hab_downloaded, hab_missing = audit_habitats(dry_run)
        print(f"  local_match={len(hab_matched)}  downloaded={len(hab_downloaded)}  missing={len(hab_missing)}")

    write_report(
        items_matched, items_downloaded, items_missing,
        hab_matched, hab_downloaded, hab_missing,
        dry_run,
    )

    total_missing = len(items_missing) + len(hab_missing)
    if total_missing > 0:
        print(f"\nWARN: {total_missing} entries still missing images. See report.")
    else:
        print("\nOK: all images resolved!")


if __name__ == "__main__":
    main()
