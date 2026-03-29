/**
 * storage.js
 * 本地收集状态管理，数据仅存于用户本机。
 * key 格式：
 *   pokemon  -> Storage key "collected_pokemon"  -> { "pokemon:皮卡丘": true, ... }
 *   habitat  -> Storage key "collected_habitat"  -> { "habitat:xxx": true, ... }
 */

const KEYS = {
  pokemon: "collected_pokemon",
  habitat: "collected_habitat",
  cosmetic: "collected_cosmetic"
};

// 默认已收集的宝可梦（主角，游戏开始即拥有）
var DEFAULT_POKEMON = {
  "pokemon:132": true,  // 百变怪
  "pokemon:465": true   // 巨蔓藤
};

// 首次使用时初始化默认收集状态
(function initDefaults() {
  try {
    var inited = wx.getStorageSync("_defaults_inited");
    if (!inited) {
      var map = wx.getStorageSync(KEYS.pokemon) || {};
      var changed = false;
      for (var k in DEFAULT_POKEMON) {
        if (!map[k]) {
          map[k] = true;
          changed = true;
        }
      }
      if (changed) {
        wx.setStorageSync(KEYS.pokemon, map);
      }
      wx.setStorageSync("_defaults_inited", true);
    }
  } catch (e) {}
})();

/** 读取某类型的收集 map（{key: true}） */
function getAll(type) {
  try {
    return wx.getStorageSync(KEYS[type]) || {};
  } catch (e) {
    return {};
  }
}

/** 是否已收集 */
function isCollected(type, key) {
  const map = getAll(type);
  return !!map[key];
}

/** 切换收集状态，返回新状态 true/false */
function toggle(type, key) {
  const map = getAll(type);
  if (map[key]) {
    delete map[key];
  } else {
    map[key] = true;
  }
  try {
    wx.setStorageSync(KEYS[type], map);
  } catch (e) {}
  return !!map[key];
}

/** 获取已收集数量 */
function getCount(type) {
  return Object.keys(getAll(type)).length;
}

/** 获取某只宝可梦的所在城镇 */
function getTown(key) {
  try {
    var map = wx.getStorageSync("pokemon_town") || {};
    return map[key] || "";
  } catch (e) {
    return "";
  }
}

/** 设置某只宝可梦的所在城镇，town 为空则删除 */
function setTown(key, town) {
  try {
    var map = wx.getStorageSync("pokemon_town") || {};
    if (town) {
      map[key] = town;
    } else {
      delete map[key];
    }
    wx.setStorageSync("pokemon_town", map);
  } catch (e) {}
}

module.exports = { getAll, isCollected, toggle, getCount, getTown, setTown };
