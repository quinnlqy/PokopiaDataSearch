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
    filterScrollPct: 0,      // 滚动条位置 0~1
    filterIndicatorW: 40,    // 指示条宽度百分比（固定40%）
    collectedPokemon: {},
    collectedHabitat: {},
    collectedCosmetic: {},
    stats: {
      pokemonCount: 0, pokemonTotal: 0,
      habitatCount: 0, habitatTotal: 0,
      cosmeticCount: 0, cosmeticTotal: 0
    }
  },

  onShow() {
    const self = this;
    this._reloadCollection();
    // scroll-view 从隐藏恢复时会内部重置，需延迟补发才可靠
    const savedTop = this._savedScrollTop || 0;
    setTimeout(function() {
      if (savedTop > 0) {
        self.setData({ scrollTop: savedTop });
      } else {
        self.setData({ scrollTop: -1 }, function() {
          self.setData({ scrollTop: 0 });
        });
      }
    }, 200);
  },

  onHide() {
    // 页面实例保留，_savedScrollTop 不会丢失，无需额外操作
  },

  onReady() {
    // 提前缓存 filter-row 的实际可见宽度，用于进度条计算
    const self = this;
    wx.createSelectorQuery().select('.filter-row').boundingClientRect(function(rect) {
      if (rect) { self._filterRowViewW = rect.width; }
    }).exec();
  },

  // ── 收集数据刷新 ─────────────────────────────────────────
  _reloadCollection() {
    const collectedPokemon = storage.getAll("pokemon");
    const collectedHabitat = storage.getAll("habitat");
    const collectedCosmetic = storage.getAll("cosmetic");
    this.setData({
      collectedPokemon,
      collectedHabitat,
      collectedCosmetic,
      stats: {
        pokemonCount: Object.keys(collectedPokemon).length,
        pokemonTotal: pokemonData.length,
        habitatCount: Object.keys(collectedHabitat).length,
        habitatTotal: habitatData.length,
        cosmeticCount: Object.keys(collectedCosmetic).length,
        cosmeticTotal: cosmeticData.length
      }
    });
    this.runSearch(this.data.query);
  },

  // ── 收集按钮点击 ─────────────────────────────────────────
  toggleCollect(e) {
    const type = e.currentTarget.dataset.type;
    const key  = e.currentTarget.dataset.key;
    if (type !== "pokemon" && type !== "habitat" && type !== "cosmetic") return;
    storage.toggle(type, key);
    this._reloadCollection();
  },

  // ── 筛选器 ───────────────────────────────────────────────
  setFilter(e) {
    const newFilter = e.currentTarget.dataset.filter;
    this.setData({ activeFilter: newFilter });
    this._resetLimits();
    this.runSearch(this.data.query, newFilter, this.data.collectionFilter);
  },

  setCollectionFilter(e) {
    const newCf = e.currentTarget.dataset.filter;
    this.setData({ collectionFilter: newCf });
    this._resetLimits();
    this.runSearch(this.data.query, this.data.activeFilter, newCf);
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
    this._savedScrollTop = 0;
  },

  // ── 结果列表滚动 → 记录位置 ──────────────────────────
  onResultScroll(e) {
    this._savedScrollTop = e.detail.scrollTop;
  },

  // ── filter-row 滚动 → 更新指示条位置 ──────────────────
  onFilterScroll(e) {
    const { scrollLeft, scrollWidth } = e.detail;
    // 使用实际容器宽度计算最大滚动量
    const self = this;
    if (!this._filterRowViewW) {
      wx.createSelectorQuery().select('.filter-row').boundingClientRect(function(rect) {
        if (rect) {
          self._filterRowViewW = rect.width;
        }
      }).exec();
    }
    const viewW = this._filterRowViewW || scrollWidth * 0.6;
    const maxScroll = scrollWidth - viewW;
    const pct = maxScroll > 0 ? scrollLeft / maxScroll : 0;
    this.setData({ filterScrollPct: Math.min(pct, 1) });
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
  runSearch(query, activeFilter, collectionFilter) {
    const tokens = tokenize(query || "");
    const f = activeFilter !== undefined ? activeFilter : this.data.activeFilter;
    const cf = collectionFilter !== undefined ? collectionFilter : this.data.collectionFilter;
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
        pokemon:   search(pokemonData,   ["name_zh", "name_en", "dex_no", "natdex_no", "types", "favorites"], tokens, 9999),
        habitats:  search(habitatData,   ["name", "name_zh", "id", "required", "required_zh", "attracts", "attracts_zh"], tokens, 9999),
        items:     search(pureItemData,  ["name", "name_zh"], tokens, 9999),
        building:  search(buildingData,  ["name", "name_zh", "category_key"], tokens, 9999),
        furniture: search(furnitureData, ["name", "name_zh"], tokens, 9999),
        cosmetics: search(cosmeticData,  ["name", "name_zh", "location"], tokens, 9999),
        cooking:   search(cookingData,   ["category_zh_recipe", "name", "ingredients", "tools", "power_up_moves"], tokens, 9999)
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

  // 按当前 _limits 截取并更新 data.results，完成后再恢复滚动位置
  _applyLimits() {
    const self = this;
    const targetTop = this._savedScrollTop || 0;
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
    }, function() {
      wx.nextTick(function() {
        if (targetTop === 0) {
          // scrollTop 值可能已是 0，需要先设 -1 才能触发 scroll-view 回顶
          self.setData({ scrollTop: -1 }, function() {
            self.setData({ scrollTop: 0 });
          });
        } else {
          self.setData({ scrollTop: targetTop });
        }
      });
    });
  },

  openDetail(e) {
    const type = e.currentTarget.dataset.type;
    const key  = e.currentTarget.dataset.key;
    wx.navigateTo({
      url: `/pages/detail/detail?type=${type}&key=${encodeURIComponent(key)}`
    });
  },

  onShareAppMessage() {
    return {
      title: 'poko攻略小册',
      path: '/pages/index/index'
    };
  },

  onShareTimeline() {
    return {
      title: 'poko攻略小册'
    };
  }
});
