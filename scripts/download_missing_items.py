"""
download_missing_items.py
=========================
从 pokopiaguide.com 批量下载 items.js 中缺失本地图片的道具图片。
下载完成后自动更新 image_path 字段并写回 items.js。

特点：
  - 随机 User-Agent 轮换
  - 每次请求随机延迟 3~8 秒
  - 每下载 10 张额外休息 20~40 秒
  - 随机打乱下载顺序
  - 失败自动重试（最多 3 次，间隔递增）
  - 实时保存进度，中途中断可重跑

用法：
  python scripts/download_missing_items.py [--dry-run]
"""

import argparse
import io
import json
import os
import random
import re
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import requests
import urllib3
urllib3.disable_warnings()

BASE_DIR = Path(__file__).parent.parent
MINI_DIR = BASE_DIR / "miniprogram"
ITEMS_JS  = MINI_DIR / "data" / "items.js"
ITEMS_IMG_DIR = MINI_DIR / "images" / "items"

# ── User-Agent 池 ──────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

def make_headers(referer: str = "https://pokopiaguide.com/zh-Hans/items") -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": referer,
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "image",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "same-origin",
    }

# ── JS 读写 ────────────────────────────────────────────────
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

# ── 下载单张图片 ───────────────────────────────────────────
def download_image(session: requests.Session, url: str, out_path: Path,
                   max_retry: int = 3) -> bool:
    for attempt in range(1, max_retry + 1):
        try:
            headers = make_headers()
            # 每次重试前先随机小睡，模拟人类犹豫
            if attempt > 1:
                wait = attempt * random.uniform(4, 8)
                print(f"    retry {attempt}/{max_retry}, waiting {wait:.1f}s...")
                time.sleep(wait)

            r = session.get(url, headers=headers, timeout=20, verify=False)

            if r.status_code == 200 and len(r.content) > 500:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(r.content)
                return True
            elif r.status_code == 429:
                wait = 60 + random.uniform(30, 60)
                print(f"    [429 Rate Limited] sleeping {wait:.0f}s...")
                time.sleep(wait)
            elif r.status_code == 403:
                print(f"    [403 Forbidden] {url}")
                return False
            else:
                print(f"    [{r.status_code}] {url}")

        except requests.exceptions.ConnectionError as e:
            print(f"    [ConnectionError] {e}")
        except requests.exceptions.Timeout:
            print(f"    [Timeout] {url}")
        except Exception as e:
            print(f"    [Error] {e}")

    return False

# ── 主流程 ─────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只列出任务，不实际下载")
    args = parser.parse_args()

    items = load_js(ITEMS_JS)

    # 找出缺失本地图片的条目
    tasks = []
    for it in items:
        img_path = it.get("image_path") or ""
        if img_path:
            local = MINI_DIR / img_path.lstrip("/")
            if local.exists():
                continue  # 已有本地图，跳过
        img_url = it.get("image_url") or ""
        if img_url.startswith("https://pokopiaguide.com/images/items/"):
            fname = img_url.split("/")[-1]          # item-2.png
            slug  = fname.replace(".png", "")        # item-2
            out   = ITEMS_IMG_DIR / fname
            tasks.append({
                "_item": it,
                "name": it.get("name_zh") or it.get("name", ""),
                "url": img_url,
                "out": out,
                "image_path": f"/images/items/{fname}",
            })

    print(f"=== Download Missing Item Images ===")
    print(f"Total tasks: {len(tasks)}")
    print(f"Dry-run: {args.dry_run}")
    print()

    if args.dry_run:
        for t in tasks:
            print(f"  {t['name']} <- {t['url']}")
        return

    # 随机打乱顺序，避免顺序规律被识别
    random.shuffle(tasks)

    session = requests.Session()
    # 先访问一次首页，拿 cookie，模拟正常浏览
    print("[0] Warming up session (visiting homepage)...")
    try:
        session.get(
            "https://pokopiaguide.com/zh-Hans/items",
            headers={
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
            timeout=15,
            verify=False
        )
        print("    Homepage OK")
    except Exception as e:
        print(f"    Homepage warn: {e}")
    time.sleep(random.uniform(2, 5))

    ok_count = 0
    fail_count = 0
    fail_list = []

    for i, task in enumerate(tasks, 1):
        name = task["name"]
        url  = task["url"]
        out  = task["out"]

        # 如果已经下载过了，直接跳过
        if out.exists() and out.stat().st_size > 500:
            task["_item"]["image_path"] = task["image_path"]
            ok_count += 1
            print(f"[{i:3}/{len(tasks)}] SKIP (exists) {name}")
            continue

        print(f"[{i:3}/{len(tasks)}] {name}  {url.split('/')[-1]}", end="  ", flush=True)

        ok = download_image(session, url, out)
        if ok:
            task["_item"]["image_path"] = task["image_path"]
            ok_count += 1
            print(f"OK ({out.stat().st_size} bytes)")
        else:
            fail_count += 1
            fail_list.append(name)
            print("FAIL")

        # 每张之间随机延迟 3~8 秒
        delay = random.uniform(3, 8)
        # 偶尔模拟"看了一会儿"的较长停顿（约10%概率）
        if random.random() < 0.10:
            delay += random.uniform(8, 20)
            print(f"    (taking a longer break: {delay:.1f}s)")
        time.sleep(delay)

        # 每 10 张额外休息
        if i % 10 == 0:
            rest = random.uniform(20, 40)
            print(f"\n--- Downloaded {i}/{len(tasks)}, resting {rest:.0f}s ---\n")
            # 保存中间进度，防止中断丢失
            save_js(ITEMS_JS, items)
            time.sleep(rest)

    # 最终写回
    save_js(ITEMS_JS, items)

    print()
    print(f"=== Done ===")
    print(f"  Success : {ok_count}")
    print(f"  Failed  : {fail_count}")
    if fail_list:
        print("  Failed items:")
        for name in fail_list:
            print(f"    - {name}")
    print(f"  items.js updated.")


if __name__ == "__main__":
    main()
