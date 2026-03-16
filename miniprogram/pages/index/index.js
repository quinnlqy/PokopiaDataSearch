const { tokenize, search } = require("../../utils/search");
const storage = require("../../utils/storage");

const pokemonData = require("../../data/pokemon.js");
const habitatData = require("../../data/habitats.js");
const itemData = require("../../data/items.js");
const furnitureData = require("../../data/furniture.js");
const cosmeticData = require("../../data/cosmetics.js");
const cookingData = require("../../data/cooking.js");

const BUILDING_KEYS = ["building", "block", "kit"];
const buildingData = itemData.filter(function(it) {
  return BUILDING_KEYS.indexOf(it.category_key) >= 0;
});
const pureItemData = itemData.filter(function(it) {
  return BUILDING_KEYS.indexOf(it.category_key) < 0;
});

// 每次触底追加的条数
const PAGE_SIZE = 20;
// 初始显示条数
const INIT_SIZE = 20;

// 完整的分类结果（未分页），搜索/筛选变化时更新
var _fullResults = {
  pokemon: [], habitats: [], items: [],
  building: [], furniture: [], cosmetics: [], cooking: []
};

// 当前各分类已显示条数
var _limits = {
  pokemon: INIT_SIZE, habitats: INIT_SIZE, items: INIT_SIZE,
  building: INIT_SIZE, furniture: INIT_SIZE, cosmetics: INIT_SIZE, cooking: INIT_SIZE
};

Page({
  data: {
    query: "",
    activeFilter: "all",
    collectionFilter: "all",
    results: {
      pokemon: [], habitats: [], items: [],
      building: [], furniture: [], cosmetics: [], cooking: []
    },
    scrollTop: 0,
    collectedPokemon: {},
    collectedHabitat: {},
    stats: {
      pokemonCount: 0, pokemonTotal: 0,
      habitatCount: 0, habitatTotal: 0
    }
  },

  onShow() {
    this._reloadCollection();
  },

  // ── 收集数据刷新 ─────────────────────────────────────────
  _reloadCollection() {
    const collectedPokemon = storage.getAll("pokemon");
    const collectedHabitat = storage.getAll("habitat");
    this.setData({
      collectedPokemon,
      collectedHabitat,
      stats: {
        pokemonCount: Object.keys(collectedPokemon).length,
        pokemonTotal: pokemonData.length,
        habitatCount: Object.keys(collectedHabitat).length,
        habitatTotal: habitatData.length
      }
    });
    this.runSearch(this.data.query);
  },

  // ── 收集按钮点击 ─────────────────────────────────────────
  toggleCollect(e) {
    const type = e.currentTarget.dataset.type;
    const key  = e.currentTarget.dataset.key;
    if (type !== "pokemon" && type !== "habitat") return;
    storage.toggle(type, key);
    this._reloadCollection();
  },

  // ── 筛选器 ───────────────────────────────────────────────
  setFilter(e) {
    this.setData({ activeFilter: e.currentTarget.dataset.filter });
    this._resetLimits();
    this.runSearch(this.data.query);
  },

  setCollectionFilter(e) {
    this.setData({ collectionFilter: e.currentTarget.dataset.filter });
    this._resetLimits();
    this.runSearch(this.data.query);
  },

  onInput(e) {
    const query = e.detail.value || "";
    this.setData({ query });
    this._resetLimits();
    this.runSearch(query);
  },

  // 重置分页（搜索词/筛选变化时）
  _resetLimits() {
    _limits = {
      pokemon: INIT_SIZE, habitats: INIT_SIZE, items: INIT_SIZE,
      building: INIT_SIZE, furniture: INIT_SIZE, cosmetics: INIT_SIZE, cooking: INIT_SIZE
    };
    this.setData({ scrollTop: 0 });
  },

  // ── 触底加载更多 ─────────────────────────────────────────
  onScrollToLower() {
    const f = this.data.activeFilter;
    const cats = f === "all"
      ? ["pokemon", "habitats", "items", "building", "furniture", "cosmetics", "cooking"]
      : f === "pokemon"   ? ["pokemon"]
      : f === "habitat"   ? ["habitats"]
      : f === "item"      ? ["items"]
      : f === "building"  ? ["building"]
      : f === "furniture" ? ["furniture"]
      : f === "cosmetic"  ? ["cosmetics"]
      : f === "cooking"   ? ["cooking"]
      : [];

    let changed = false;
    cats.forEach(function(cat) {
      if (_limits[cat] < _fullResults[cat].length) {
        _limits[cat] = Math.min(_limits[cat] + PAGE_SIZE, _fullResults[cat].length);
        changed = true;
      }
    });

    if (changed) {
      this._applyLimits();
    }
  },

  // ── 核心搜索 ─────────────────────────────────────────────
  runSearch(query) {
    const tokens = tokenize(query || "");
    const f = this.data.activeFilter;
    const cf = this.data.collectionFilter;
    const collectedPokemon = this.data.collectedPokemon;
    const collectedHabitat = this.data.collectedHabitat;

    function filterByCollection(list, type) {
      const map = type === "pokemon" ? collectedPokemon : collectedHabitat;
      if (cf === "collected")   return list.filter(function(r) { return !!map[r.key]; });
      if (cf === "uncollected") return list.filter(function(r) { return !map[r.key]; });
      return list;
    }

    // 计算完整结果（无分页限制）
    let base;
    if (!tokens.length) {
      base = {
        pokemon:   pokemonData.slice(),
        habitats:  habitatData.slice(),
        items:     pureItemData.slice(),
        building:  buildingData.slice(),
        furniture: furnitureData.slice(),
        cosmetics: cosmeticData.slice(),
        cooking:   cookingData.slice()
      };
    } else {
      base = {
        pokemon:   search(pokemonData,   ["category", "category_zh", "name_zh", "name_en", "dex_no", "natdex_no", "types", "favorites"], tokens, 9999),
        habitats:  search(habitatData,   ["category", "category_zh", "name", "name_zh", "id", "required", "required_zh", "attracts", "attracts_zh"], tokens, 9999),
        items:     search(pureItemData,  ["category", "category_zh", "name", "name_zh"], tokens, 9999),
        building:  search(buildingData,  ["category", "category_zh", "name", "name_zh", "category_key"], tokens, 9999),
        furniture: search(furnitureData, ["category", "category_zh", "name", "name_zh"], tokens, 9999),
        cosmetics: search(cosmeticData,  ["category", "category_zh", "name", "name_zh", "location"], tokens, 9999),
        cooking:   search(cookingData,   ["category", "category_zh", "category_zh_recipe", "name", "ingredients", "tools", "power_up_moves"], tokens, 9999)
      };
    }

    _fullResults = {
      pokemon:   (f === "all" || f === "pokemon")   ? filterByCollection(base.pokemon,  "pokemon") : [],
      habitats:  (f === "all" || f === "habitat")   ? filterByCollection(base.habitats, "habitat") : [],
      items:     (f === "all" || f === "item")       ? base.items     : [],
      building:  (f === "all" || f === "building")  ? base.building  : [],
      furniture: (f === "all" || f === "furniture") ? base.furniture : [],
      cosmetics: (f === "all" || f === "cosmetic")  ? base.cosmetics : [],
      cooking:   (f === "all" || f === "cooking")   ? base.cooking   : []
    };

    this._applyLimits();
  },

  // 按当前 _limits 截取并更新 data.results
  _applyLimits() {
    this.setData({
      results: {
        pokemon:   _fullResults.pokemon.slice(0,   _limits.pokemon),
        habitats:  _fullResults.habitats.slice(0,  _limits.habitats),
        items:     _fullResults.items.slice(0,     _limits.items),
        building:  _fullResults.building.slice(0,  _limits.building),
        furniture: _fullResults.furniture.slice(0, _limits.furniture),
        cosmetics: _fullResults.cosmetics.slice(0, _limits.cosmetics),
        cooking:   _fullResults.cooking.slice(0,   _limits.cooking)
      }
    });
  },

  openDetail(e) {
    const type = e.currentTarget.dataset.type;
    const key  = e.currentTarget.dataset.key;
    wx.navigateTo({
      url: `/pages/detail/detail?type=${type}&key=${encodeURIComponent(key)}`
    });
  }
});
