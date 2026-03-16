"""
translate_required_items.py
============================
将 habitats.js 中 required_items[].name（英文）翻译为中文，
写入 required_items[].name_zh。

同时对"水/熔岩/草丛"等环境类条目打上 is_env=true 标记，
使前端能区别显示（环境条件 vs 具体道具）。

用法：
  python scripts/translate_required_items.py [--dry-run]
"""

import argparse
import json
import re
import sys
import io
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).parent.parent
HABITATS_JS = BASE_DIR / "miniprogram" / "data" / "habitats.js"
CACHE_FILE  = BASE_DIR / "scripts" / "translate_cache_required.json"

# ── 手工对照表（优先级最高，覆盖机器翻译）────────────────────────
MANUAL_MAP = {
    # 环境/地形条件（标记 is_env）
    "Water":              ("水", True),
    "Hot spring water":   ("温泉水", True),
    "Ocean water":        ("海水", True),
    "Muddy water":        ("泥水", True),
    "Lava":               ("熔岩", True),
    "Molten rock":        ("熔岩岩石", True),
    "Waterfall":          ("瀑布", True),
    "Waterwheel":         ("水车", True),
    "Water basin":        ("水盆", True),
    "High-up location":   ("高处", True),
    "Tall grass":         ("绿色高草", True),
    "Tall grass (any)":   ("高草（任意）", True),
    "Red tall grass":     ("红色高草", True),
    "Yellow tall grass":  ("黄色高草", True),
    "Pink tall grass":    ("粉红高草", True),
    "Dry tall grass":     ("枯萎高草", True),
    "Wildflowers":        ("野花", True),
    "Mountain flowers":   ("山岩花", True),
    "Seashore flowers":   ("海滨花", True),
    "Skyland flowers":    ("浮岛花", True),
    "Moss":               ("苔藓", True),
    "Mossy boulder":      ("苔藓岩石", True),
    "Large boulder":      ("大岩石", True),
    "Smooth rock":        ("石块", True),
    "Stalagmites":        ("石笋", True),
    "Strength rock":      ("怪力岩", True),
    "Duckweed":           ("浮萍", True),
    "Large tree (any)":   ("大树（任意）", True),
    "Large palm tree":    ("大棕榈树", True),
    "Berry tree (any)":   ("果实树（任意）", True),
    "Pointy tree":        ("三角树", True),
    "Tree stump":         ("树桩", True),
    "Tree stump (any)":   ("树桩（任意）", True),

    # 家具/道具（手工确认中文名）
    "Seat (any)":         ("椅子（任意）", False),
    "Seat (wide)":        ("长条椅", False),
    "Table (any)":        ("桌子（任意）", False),
    "Table (large)":      ("大型桌子", False),
    "Bed (any)":          ("床铺（任意）", False),
    "Dresser (any)":      ("梳妆台（任意）", False),
    "Closet (any)":       ("衣柜（任意）", False),
    "Partition (any)":    ("隔板（任意）", False),
    "Hedge (any)":        ("篱笆（任意）", False),
    "Hedge":              ("篱笆", False),
    "Stylish hedge":      ("可爱篱笆", False),
    "Post (any)":         ("告示牌（任意）", False),
    "Sign":               ("招牌", False),
    "Sign (any)":         ("招牌（任意）", False),
    "Streetlight (any)":  ("路灯（任意）", False),
    "Lighting (any)":     ("灯具（任意）", False),
    "Toy (any)":          ("玩具（任意）", False),
    "Doll (any)":         ("布偶（任意）", False),
    "Waste bin (any)":    ("垃圾桶（任意）", False),
    "Potted plant (any)": ("盆栽（任意）", False),
    "Potted plant":       ("盆栽", False),
    "Vegetable field (any)": ("蔬菜田（任意）", False),

    "Plated food":        ("盘子上的食物", False),
    "Exhibition stand":   ("展示台", False),
    "Alarm clock":        ("闹钟", False),
    "Cart":               ("手推车", False),
    "Speaker":            ("喇叭", False),
    "Small stage":        ("小舞台", False),
    "Standing mic":       ("立式麦克风", False),
    "Fishing rod":        ("钓竿", False),
    "Campfire":           ("营火", False),
    "Bonfire":            ("篝火", False),
    "Firepit":            ("火盆", False),
    "Gravestone":         ("墓碑", False),
    "Balloons":           ("气球", False),
    "Cardboard boxes":    ("纸箱", False),
    "Wooden birdhouse":   ("木制鸟巢箱", False),
    "Wooden crate":       ("木箱", False),
    "Wheelbarrow":        ("独轮手推车", False),
    "Bookcase":           ("书架", False),
    "Lantern":            ("灯笼", False),
    "Spotlight":          ("聚光灯", False),
    "Television":         ("电视", False),
    "Vending machine":    ("自动贩卖机", False),
    "Arcade machine":     ("街机", False),
    "Slide":              ("溜滑梯", False),
    "Tires":              ("轮胎", False),
    "Tire toy":           ("轮胎玩具", False),
    "Perch":              ("栖木", False),
    "Magazine rack":      ("杂志架", False),
    "Newspaper":          ("报纸", False),
    "Garbage bags":       ("垃圾袋", False),
    "Garbage bin":        ("垃圾桶", False),
    "Crystal ball":       ("水晶球", False),
    "First aid kit":      ("急救箱", False),
    "Punching bag":       ("沙包", False),
    "Sandbags":           ("沙包袋", False),
    "Punching game":      ("打靶游戏机", False),
    "Microscope":         ("显微镜", False),
    "Papers":             ("文件", False),
    "Science experiment": ("科学实验台", False),
    "Control unit":       ("控制台", False),
    "Mug":                ("马克杯", False),
    "Laptop":             ("笔记本电脑", False),
    "Computer":           ("电脑", False),
    "Tablet":             ("平板电脑", False),
    "Whiteboard":         ("白板", False),
    "Cd player":          ("CD播放器", False),
    "Cd rack":            ("CD架", False),
    "Music mat":          ("音乐地毯", False),
    "Big drum":           ("大鼓", False),
    "Cool electric guitar": ("酷炫电吉他", False),
    "Cool bass guitar":   ("酷炫贝斯", False),
    "Counter":            ("柜台", False),
    "Cash register":      ("收银机", False),
    "Food counter":       ("食物柜台", False),
    "Cooking stove":      ("炉灶", False),
    "Frying pan":         ("平底锅", False),
    "Bread oven":         ("烤面包炉", False),
    "Stylish cooking pot": ("时尚料理锅", False),
    "Cutting board":      ("砧板", False),
    "Kitchen table":      ("厨房桌", False),
    "Menu board":         ("菜单板", False),
    "Party platter":      ("拼盘", False),
    "Plated food":        ("盘子上的食物", False),
    "Afternoon tea set":  ("下午茶茶具", False),
    "Sandwiches":         ("三明治", False),
    "Chocolate cookies":  ("巧克力饼干", False),
    "Pizza":              ("披萨", False),
    "Soda float":         ("冰淇淋苏打", False),
    "Shaved ice":         ("刨冰", False),
    "Fried potatoes":     ("炸薯条", False),
    "Ribbon cake":        ("蝴蝶结蛋糕", False),
    "Picnic basket":      ("野餐篮", False),
    "Paper party cups":   ("纸杯", False),
    "Offering dish":      ("供品盘", False),
    "Beach chair":        ("沙滩椅", False),
    "Beach parasol":      ("沙滩伞", False),
    "Inflatable boat":    ("充气船", False),
    "Canoe":              ("独木舟", False),
    "Resort sofa":        ("度假村沙发", False),
    "Resort hammock":     ("度假村吊床", False),
    "Resort table":       ("度假村桌子", False),
    "Resort light":       ("度假村灯饰", False),
    "Wooden path":        ("木栈道", False),
    "Walkway":            ("走道", False),
    "Stepping stone":     ("踏脚石", False),
    "Iron pipes":         ("铁管", False),
    "Iron beam":          ("铁梁", False),
    "Iron scaffold":      ("铁架", False),
    "Concrete pipe":      ("混凝土管", False),
    "Sewer-hole cover":   ("下水道盖板", False),
    "Traffic cone":       ("警示锥", False),
    "Railway track":      ("铁轨", False),
    "Crossing gate":      ("平交道栏杆", False),
    "Utility pole":       ("电线杆", False),
    "Windmill":           ("风车", False),
    "Bathtub":            ("浴缸", False),
    "Shower":             ("淋浴间", False),
    "Sink":               ("水槽", False),
    "Modern sink":        ("现代水槽", False),
    "Towel rack":         ("毛巾架", False),
    "Cleaning supplies":  ("打扫用品", False),
    "Humidifier":         ("加湿器", False),
    "Basket":             ("篮子", False),
    "Berry basket":       ("树果篮", False),
    "Push cart":          ("推车", False),
    "Hot spring spout":   ("温泉喷口", False),
    "Barrel":             ("木桶", False),
    "Metal drum":         ("铁桶", False),
    "Jumbled cords":      ("杂乱电线", False),
    "Mushroom lamp":      ("蘑菇灯", False),
    "Small vase":         ("小花瓶", False),
    "Desk light":         ("桌灯", False),
    "Slender candle":     ("细蜡烛", False),
    "Eerie candle":       ("奇异蜡烛", False),
    "Stone fireplace":    ("石制壁炉", False),
    "Furnace":            ("熔炉", False),
    "Smelting furnace":   ("冶炼炉", False),
    "Hanging scroll":     ("挂轴", False),
    "Wall mirror":        ("壁挂镜", False),
    "Mirror (large)":     ("大镜子", False),
    "Bike":               ("自行车", False),
    "Knitting supplies":  ("编织用品", False),
    "Pitcher pot plant":  ("猪笼草盆栽", False),
    "Chansey plant":      ("吉利蛋造型植物", False),
    "Simple cushion":     ("简约靠垫", False),
    "Step stool":         ("踏脚凳", False),
    "Folding chair":      ("折叠椅", False),
    "Side table":         ("侧桌", False),
    "Stand":              ("展示架", False),
    "Photo cutout board": ("人形立牌", False),
    "Arrow sign":         ("箭头告示牌", False),
    "Raichu sign":        ("雷丘招牌", False),
    "Moonlight dance statue": ("月光舞蹈雕像", False),
    "Cannon":             ("大炮", False),
    "Ship's wheel":       ("船舵", False),
    "Professor's treasure trove": ("教授的宝物堆", False),
    "Lost relic (large)": ("巨大遗迹", False),
    "Auspicious armor":   ("祥瑞铠甲", False),
    "Malicious armor":    ("凶兆铠甲", False),
    "Team rocket wall hanging": ("火箭队壁挂", False),
    "Floor switch":       ("地板开关", False),
    "Boo-in-the-box":     ("捉弄箱", False),
    "Boo-in-th-box":      ("捉弄箱", False),
    "Castform weather charm (sun)": ("随天气改变的魔法石（晴天）", False),
    "Castform weather charm (rain)": ("随天气改变的魔法石（雨天）", False),
    "Pikachu doll":       ("皮卡丘布偶", False),
    "Pikachu sofa":       ("皮卡丘沙发", False),
    "Arcanine doll":      ("风速狗布偶", False),
    "Dragonite doll":     ("快龙布偶", False),
    "Eevee doll":         ("伊布布偶", False),
    "Armor fossil":       ("盾之化石", False),
    "Jaw fossil":         ("颚之化石", False),
    "Skull fossil":       ("骷髅化石", False),
    "Sail fossil":        ("帆之化石", False),
    "Despot fossil (head)":   ("暴君化石（头部）", False),
    "Despot fossil (body)":   ("暴君化石（躯体）", False),
    "Despot fossil (tail)":   ("暴君化石（尾部）", False),
    "Despot fossil (legs)":   ("暴君化石（腿部）", False),
    "Headbut fossil (head)":  ("铁头化石（头部）", False),
    "Headbut fossil (body)":  ("铁头化石（躯体）", False),
    "Headbut fossil (tail)":  ("铁头化石（尾部）", False),
    "Shield fossil (head)":   ("盾之化石（头部）", False),
    "Shield fossil (body)":   ("盾之化石（躯体）", False),
    "Shield tail (body)":     ("盾之化石（尾部）", False),
    "Tundra fossil (head)":   ("冻土化石（头部）", False),
    "Tundra fossil (body)":   ("冻土化石（躯体）", False),
    "Tundra fossil (tail)":   ("冻土化石（尾部）", False),
    "Wing fossil (head)":     ("翼之化石（头部）", False),
    "Wing fossil (body)":     ("翼之化石（躯体）", False),
    "Wing fossil (tail)":     ("翼之化石（尾部）", False),
    "Wing fossil (left wing)": ("翼之化石（左翼）", False),
    "Wing fossil (right wing)": ("翼之化石（右翼）", False),
    "Luxury bed":         ("豪华床", False),
    "Luxury sofa":        ("豪华沙发", False),
    "Luxury table":       ("豪华桌", False),
    "Luxury lamp":        ("豪华灯", False),
    "Industrial bed":     ("工业风床", False),
    "Industrial desk":    ("工业风书桌", False),
    "Industrial chair":   ("工业风椅", False),
    "Iron bed":           ("铁制床", False),
    "Iron chair":         ("铁制椅", False),
    "Iron table":         ("铁制桌", False),
    "Log bed":            ("原木床", False),
    "Log chair":          ("原木椅", False),
    "Log table":          ("原木桌", False),
    "Straw bed":          ("稻草床", False),
    "Straw stool":        ("稻草凳", False),
    "Straw table":        ("稻草桌", False),
    "Naptime bed":        ("午睡床", False),
    "Plain bed":          ("简约床", False),
    "Plain chest":        ("简约收纳箱", False),
    "Plain lamp":         ("简约灯", False),
    "Plain sofa":         ("简约沙发", False),
    "Plain table":        ("简约桌", False),
    "Chic sofa":          ("时尚沙发", False),
    "Chic chair":         ("时尚椅", False),
    "Chic table":         ("时尚桌", False),
    "Cute sofa":          ("可爱沙发", False),
    "Cute table":         ("可爱桌", False),
    "Cute lamp":          ("可爱灯", False),
    "Cute dresser":       ("可爱梳妆台", False),
    "Cute bed":           ("可爱床", False),
    "Berry chair":        ("树果椅", False),
    "Berry table":        ("树果桌", False),
    "Berry bed":          ("树果床", False),
    "Berry table lamp":   ("树果桌灯", False),
    "Pop art bed":        ("波普艺术床", False),
    "Pop art sofa":       ("波普艺术沙发", False),
    "Pop art table":      ("波普艺术桌", False),
    "Poke ball bed":      ("精灵球床", False),
    "Poke ball sofa":     ("精灵球沙发", False),
    "Poke ball table":    ("精灵球桌", False),
    "Poke ball light":    ("精灵球灯", False),
    "Gaming bed":         ("电竞床", False),
    "Gaming pc":          ("电竞电脑", False),
    "Gaming chair":       ("电竞椅", False),
    "Gaming fridge":      ("电竞冰箱", False),
    "Antique closet":     ("古典衣柜", False),
    "Antique bed":        ("古典床", False),
    "Antique dresser":    ("古典梳妆台", False),
    "Antique chair":      ("古典椅", False),
    "Garden chair":       ("庭院椅", False),
    "Garden light":       ("庭院灯", False),
    "Garden table":       ("庭院桌", False),
    "Office desk":        ("办公书桌", False),
    "Office chair":       ("办公椅", False),
    "Office shelf":       ("办公室收纳柜", False),
    "Office locker":      ("办公室储物柜", False),
    "Pencil holder":      ("笔筒", False),
    "Bookcase":           ("书架", False),
    "Excavation tools":   ("挖掘工具", False),
}

# ── JS 读写 ────────────────────────────────────────────────
def load_js(path: Path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^module\.exports\s*=\s*", text)
    if m:
        text = text[m.end():]
    return json.loads(text.rstrip().rstrip(";"))

def save_js(path: Path, data) -> None:
    content = "module.exports = " + json.dumps(
        data, ensure_ascii=False, separators=(",", ":")
    ) + ";\n"
    path.write_text(content, encoding="utf-8")

# ── 翻译（带缓存，fallback 机器翻译）────────────────────────
def load_cache():
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    return {}

def save_cache(cache):
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

def translate_name(name: str, cache: dict) -> tuple[str, bool]:
    """返回 (中文名, is_env)"""
    # 手工表优先
    if name in MANUAL_MAP:
        return MANUAL_MAP[name]
    # 缓存
    if name in cache:
        return cache[name]["zh"], cache[name].get("is_env", False)
    # 机器翻译
    try:
        from deep_translator import GoogleTranslator
        zh = GoogleTranslator(source="en", target="zh-CN").translate(name)
        time.sleep(0.5)
        result = (zh, False)
        cache[name] = {"zh": zh, "is_env": False}
        save_cache(cache)
        print(f"  [GT] {name!r:40s} -> {zh}")
        return result
    except Exception as e:
        print(f"  [GT FAIL] {name}: {e}")
        return (name, False)  # 翻译失败，保留英文

# ── 主流程 ─────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    habitats = load_js(HABITATS_JS)
    cache = load_cache()

    # 收集所有需要翻译的名称
    all_en_names = set()
    for h in habitats:
        for ri in (h.get("required_items") or []):
            n = ri.get("name", "")
            if re.match(r"^[A-Za-z]", n):
                all_en_names.add(n)

    print(f"需要翻译的英文名：{len(all_en_names)} 个")

    # 手工表覆盖率
    manual_hit = sum(1 for n in all_en_names if n in MANUAL_MAP)
    print(f"手工对照表命中：{manual_hit} / {len(all_en_names)}")
    need_machine = [n for n in sorted(all_en_names) if n not in MANUAL_MAP and n not in cache]
    print(f"需要机器翻译：{len(need_machine)} 个")
    if need_machine:
        print("  未覆盖名称：")
        for n in need_machine:
            print(f"    {n}")

    if args.dry_run:
        return

    # 翻译并写入 name_zh / is_env
    changed = 0
    for h in habitats:
        for ri in (h.get("required_items") or []):
            n = ri.get("name", "")
            if not re.match(r"^[A-Za-z]", n):
                continue
            zh, is_env = translate_name(n, cache)
            if ri.get("name_zh") != zh or ri.get("is_env") != is_env:
                ri["name_zh"] = zh
                if is_env:
                    ri["is_env"] = True
                elif "is_env" in ri:
                    del ri["is_env"]
                changed += 1

    print(f"\n更新了 {changed} 个 required_items 条目")

    if not args.dry_run:
        save_js(HABITATS_JS, habitats)
        print("habitats.js 已保存")

if __name__ == "__main__":
    main()
