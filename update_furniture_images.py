#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Update furniture.js image_path with COS URLs.
Maps Chinese name (name_zh) -> local filename -> COS URL.
"""

import re

COS_BASE = "https://pokopia-images-1251329367.cos.ap-guangzhou.myqcloud.com/furniture/"

# Map from name_zh to COS image filename
NAME_TO_FILE = {
    # 古典 (Antique)
    "古典衣柜": "antique-closet.png",
    "古典床": "antique-bed.png",
    "古典梳妆台": "antique-dresser.png",
    "古典椅": "antique-chair.png",
    "古典沙发": "antique-sofa.png",
    "古典收纳柜": "antique-chest.png",
    "古典桌": "antique-table.png",
    # 石 (Stone)
    "石桌": "stone-table.png",
    # 石长椅 has no matching file found
    # 午睡床 (Naptime)
    "午睡床": "naptime-bed.png",
    # 工业风 (Industrial)
    "工业风床": "industrial-bed.png",
    "工业风书桌": "industrial-desk.png",
    "工业风椅": "industrial-chair.png",
    "工业风长椅": "industrial-bench.png",
    # 大镜子 (Large mirror)
    "大镜子": "large-mirror.png",
    # 时尚矮凳 (Stylish stool)
    "时尚矮凳": "stylish-stool.png",
    # 花朵 (Flower)
    "花朵桌": "flower-table.png",
    "花朵靠垫": "flower-cushion.png",
    # 办公 (Office)
    "办公书桌": "study-desk.png",
    "办公室收纳柜": "office-cabinet.png",
    "办公桌": "office-desk.png",
    "办公椅": "office-chair.png",
    "办公室储物柜": "office-locker.png",
    "办公室架": "office-shelf.png",
    # Misc
    "柜台": "counter.png",
    "多角形架": "polygonal-shelf.png",
    "壁挂镜": "wall-mirror.png",
    "壁挂桌": "wall-mounted-table.png",
    "观众椅": "spectator-chair.png",
    "厨房桌": "kitchen-table.png",
    # 木 (Wooden)
    "木长椅": "wooden-bench.png",
    "木桌": "wooden-table.png",
    "木床": "wooden-bed.png",
    # 树果 (Berry)
    "树果床": "berry-bed.png",
    "树果椅": "berry-chair.png",
    "树果桌": "berry-table.png",
    "树果收纳盒": "berry-case.png",
    # 客房床 (Guest room)
    "客房床": "guest-room-bed.png",
    # 可爱 (Cute)
    "可爱沙发": "cute-sofa.png",
    "可爱桌": "cute-table.png",
    "可爱床": "cute-bed.png",
    "可爱梳妆台": "cute-dresser.png",
    "可爱椅": "cute-chair.png",
    # 花园 (Garden)
    "花园长椅": "garden-bench.png",
    "花园椅": "garden-chair.png",
    "花园桌": "garden-table.png",
    # Special
    "冰岩怪桌": "avalugg-table.png",
    "哈哈镜": "wiggly-mirror.png",
    # 电竞 (Gaming)
    "电竞床": "gaming-bed.png",
    "电竞冰箱": "gaming-fridge.png",
    "电竞椅": "gaming-chair.png",
    # Misc
    "边桌": "side-table.png",
    "躺椅": "deck-chair.png",
    # 豪华 (Luxury)
    "豪华床": "luxury-bed.png",
    "豪华沙发": "luxury-sofa.png",
    "豪华桌": "luxury-table.png",
    "豪华椅": "fancy-chair.png",
    "豪华梳妆台": "luxury-dresser.png",
    # 典雅 (Chic)
    "典雅沙发": "chic-sofa.png",
    "典雅椅": "chic-chair.png",
    "典雅桌": "chic-table.png",
    # Misc
    "收纳箱": "storage-box.png",
    "简约靠垫": "simple-cushion.png",
    # 铁 (Iron)
    "铁桌": "iron-table.png",
    "铁椅": "iron-chair.png",
    "铁床": "iron-bed.png",
    # Misc
    "展示台": "exhibition-stand.png",
    # 自然风 (Plain/Natural)
    "自然风床": "plain-bed.png",
    "自然风椅": "plain-chair.png",
    "自然风桌": "plain-table.png",
    "自然风沙发": "plain-sofa.png",
    "自然风衣柜": "plain-closet.png",
    "自然风台座": "plain-stand.png",
    "自然风迷你床": "mini-plain-bed.png",
    "自然风矮凳": "plain-stool.png",
    "自然风收纳柜": "plain-chest.png",
    # Misc
    "折叠椅": "folding-chair.png",
    "公共长椅": "public-seat.png",
    "大型收纳箱": "big-storage-box.png",
    "皮卡丘沙发": "pikachu-sofa.png",
    # 沙滩 (Beach)
    "沙滩椅": "beach-chair.png",
    # 沙滩伞 has no matching file
    # Misc
    "浴室椅": "waterproof-seat.png",
    "餐饮柜台": "food-counter.png",
    # 干草 (Straw)
    "干草床": "straw-bed.png",
    "干草桌": "straw-table.png",
    "干草凳": "straw-stool.png",
    # Misc
    "箱型沙发": "box-sofa.png",
    "宝可梦中心柜台": "pok-mon-center-counter.png",
    # 普普风 (Pop art)
    "普普风沙发": "pop-art-sofa.png",
    "普普风椅": "pop-art-chair.png",
    "普普风床": "pop-art-bed.png",
    "普普风桌": "pop-art-table.png",
    # 圆木 (Log)
    "圆木桌": "log-table.png",
    "圆木椅": "log-chair.png",
    "圆木床": "log-bed.png",
    # 精灵球 (Poké Ball)
    "精灵球沙发": "pok-ball-sofa.png",
    "精灵球床": "pok-ball-bed.png",
    "精灵球桌": "pok-ball-table.png",
    "精灵球收纳柜": "pok-ball-chest.png",
    # 度假风 (Resort)
    "度假风沙发": "resort-sofa.png",
    "度假风桌": "resort-table.png",
    "度假风吊床": "resort-hammock.png",
    "度假风椅": "soft-seat.png",
    "度假风床": "resort-bed.png",
    "度假风矮凳": "resort-stool.png",
    # Misc
    "推车": "push-cart.png",
}

def main():
    path = r"D:\PokopiaDataSearch-main\PokopiaDataSearch-main\miniprogram\data\furniture.js"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    updated = 0
    skipped = []

    # Process each item: find name_zh and set corresponding image_path
    def replace_image_path(m):
        nonlocal updated
        full_obj = m.group(0)
        # Extract name_zh
        name_match = re.search(r'"name_zh"\s*:\s*"([^"]+)"', full_obj)
        if not name_match:
            return full_obj
        name_zh = name_match.group(1)
        filename = NAME_TO_FILE.get(name_zh)
        if not filename:
            skipped.append(name_zh)
            return full_obj
        cos_url = COS_BASE + filename
        # Replace "image_path":null with the COS URL
        new_obj = re.sub(
            r'"image_path"\s*:\s*null',
            f'"image_path":"{cos_url}"',
            full_obj
        )
        if new_obj != full_obj:
            updated += 1
        return new_obj

    # Match each JSON object in the array
    new_content = re.sub(r'\{[^{}]+\}', replace_image_path, content)

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"Updated: {updated} items")
    print(f"Skipped (no file mapping): {skipped}")

if __name__ == "__main__":
    main()
