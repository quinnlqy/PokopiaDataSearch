const { tokenize, search } = require("../../utils/search");

const pokemonData = require("../../data/pokemon.js");
const habitatData = require("../../data/habitats.js");
const itemData = require("../../data/items.js");
const furnitureData = require("../../data/furniture.js");
const cosmeticData = require("../../data/cosmetics.js");
const cookingData = require("../../data/cooking.js");

Page({
  data: {
    query: "",
    activeFilter: "all",
    results: {
      pokemon: [],
      habitats: [],
      items: [],
      furniture: [],
      cosmetics: [],
      cooking: []
    }
  },
  setFilter(e) {
    const activeFilter = e.currentTarget.dataset.filter;
    this.setData({ activeFilter });
    this.runSearch(this.data.query);
  },
  onInput(e) {
    const query = e.detail.value || "";
    this.setData({ query });
    this.runSearch(query);
  },
  runSearch(query) {
    const tokens = tokenize(query || "");
    if (!tokens.length) {
      this.setData({
        results: { pokemon: [], habitats: [], items: [], furniture: [], cosmetics: [], cooking: [] }
      });
      return;
    }
    const allResults = {
      pokemon: search(
        pokemonData,
        ["category", "category_zh", "name_zh", "name_en", "dex_no", "natdex_no", "types", "favorites"],
        tokens,
        8
      ),
      habitats: search(
        habitatData,
        ["category", "category_zh", "name", "name_zh", "id", "required", "required_zh", "attracts", "attracts_zh"],
        tokens,
        6
      ),
      items: search(itemData, ["category", "category_zh", "name", "name_zh"], tokens, 12),
      furniture: search(furnitureData, ["category", "category_zh", "name", "name_zh"], tokens, 12),
      cosmetics: search(cosmeticData, ["category", "category_zh", "name", "name_zh", "location"], tokens, 12),
      cooking: search(
        cookingData,
        ["category", "category_zh", "category_zh_recipe", "name", "ingredients", "tools", "power_up_moves"],
        tokens,
        10
      )
    };

    const f = this.data.activeFilter;
    const filtered = {
      pokemon: f === "all" || f === "pokemon" ? allResults.pokemon : [],
      habitats: f === "all" || f === "habitat" ? allResults.habitats : [],
      items: f === "all" || f === "item" ? allResults.items : [],
      furniture: f === "all" || f === "furniture" ? allResults.furniture : [],
      cosmetics: f === "all" || f === "cosmetic" ? allResults.cosmetics : [],
      cooking: f === "all" || f === "cooking" ? allResults.cooking : []
    };

    this.setData({ results: filtered });
  },
  openDetail(e) {
    const type = e.currentTarget.dataset.type;
    const key = e.currentTarget.dataset.key;
    wx.navigateTo({
      url: `/pages/detail/detail?type=${type}&key=${encodeURIComponent(key)}`
    });
  }
});
