const pokemonData = require("../../data/pokemon.js");
const habitatData = require("../../data/habitats.js");
const itemData = require("../../data/items.js");
const furnitureData = require("../../data/furniture.js");
const cosmeticData = require("../../data/cosmetics.js");
const cookingData = require("../../data/cooking.js");

function findByKey(list, key) {
  for (let i = 0; i < list.length; i += 1) {
    if (list[i].key === key) return list[i];
  }
  return null;
}

Page({
  data: {
    item: null
  },
  onLoad(query) {
    const type = query.type;
    const key = decodeURIComponent(query.key || "");
    let item = null;
    if (type === "pokemon") item = findByKey(pokemonData, key);
    if (type === "habitat") item = findByKey(habitatData, key);
    if (type === "item") item = findByKey(itemData, key);
    if (type === "furniture") item = findByKey(furnitureData, key);
    if (type === "cosmetic") item = findByKey(cosmeticData, key);
    if (type === "cooking") item = findByKey(cookingData, key);
    this.setData({ item });
    this._type = type;
  }
  ,
  openHabitat(e) {
    const key = e.currentTarget.dataset.key;
    wx.navigateTo({
      url: `/pages/detail/detail?type=habitat&key=${encodeURIComponent(key)}`
    });
  },
  openPokemon(e) {
    const key = e.currentTarget.dataset.key;
    wx.navigateTo({
      url: `/pages/detail/detail?type=pokemon&key=${encodeURIComponent(key)}`
    });
  }
});
