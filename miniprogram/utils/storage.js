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

module.exports = { getAll, isCollected, toggle, getCount };
