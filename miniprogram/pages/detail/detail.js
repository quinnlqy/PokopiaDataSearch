const pokemonData = require("../../data/pokemon.js");
const habitatData = require("../../data/habitats.js");
const itemData = require("../../data/items.js");
const furnitureData = require("../../data/furniture.js");
const cosmeticData = require("../../data/cosmetics.js");
const cookingData = require("../../data/cooking.js");
const storage = require("../../utils/storage");

// 合并道具+家具用于图片查找
const allItemData = itemData.concat(furnitureData);

const TOWNS = ["空空镇", "亮晶晶空岛", "凸隆隆山地", "暗沉沉海边", "干巴巴荒野"];

function findByKey(list, key) {
  for (let i = 0; i < list.length; i += 1) {
    if (list[i].key === key) return list[i];
  }
  return null;
}

// 根据英文名/中文名在 allItemData 里查找图片
function findItemImage(nameEn, nameZh) {
  for (let i = 0; i < allItemData.length; i++) {
    const it = allItemData[i];
    if (nameEn && (it.name === nameEn || it.name_en === nameEn || it.name_zh === nameEn)) {
      return it.image_path || it.image_url || null;
    }
  }
  // 中文名兜底
  if (nameZh) {
    for (let i = 0; i < allItemData.length; i++) {
      const it = allItemData[i];
      if (it.name_zh === nameZh || it.name === nameZh || it.name_en === nameZh) {
        return it.image_path || it.image_url || null;
      }
    }
  }
  // 模糊匹配：去掉括号部分再试（处理 "Bed (any)" 这类）
  if (nameEn) {
    const base = nameEn.replace(/\s*\(.*?\)/g, '').trim().toLowerCase();
    for (let i = 0; i < allItemData.length; i++) {
      const it = allItemData[i];
      const n = (it.name || '').toLowerCase();
      const ne = (it.name_en || '').toLowerCase();
      if (n.indexOf(base) === 0 || ne.indexOf(base) === 0) {
        return it.image_path || it.image_url || null;
      }
    }
  }
  return null;
}

Page({
  data: {
    item: null,
    collectible: false,
    collected: false,
    isPokemon: false,
    towns: TOWNS,
    townIndex: -1
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

    if (item && (type === "item" || type === "furniture")) {
      // 给 materials 补充图片和 key，用于点击跳转
      if (item.materials && item.materials.length) {
        const materials = item.materials.map(function(mat) {
          const found = allItemData.find(function(d) {
            return d.name === mat.name || d.name_zh === mat.name || d.name_en === mat.name;
          });
          return Object.assign({}, mat, {
            image_path: found ? (found.image_path || found.image_url || null) : null,
            item_key:   found ? found.key : null,
            item_type:  found ? found.category : null,
          });
        });
        item = Object.assign({}, item, { materials: materials });
      }
    }

    if (item && type === "habitat") {
      // 构建吸引宝可梦列表（英文名 + 中文名兜底 + 去重）
      const attractRefs = [];
      const addedKeys = {};
      function addRef(pk) {
        if (pk && !addedKeys[pk.key]) {
          addedKeys[pk.key] = true;
          attractRefs.push(pk);
        }
      }
      // 1) 用英文名匹配（含引号变体）
      const attracts = item.attracts || [];
      for (let i = 0; i < attracts.length; i++) {
        const nameEn = attracts[i];
        const pk = pokemonData.find(function(p) {
          return p.name_en === nameEn ||
            p.name_en === nameEn.replace(/'/g, '\u2019') ||
            p.name_en === nameEn.replace(/\u2019/g, "'");
        });
        addRef(pk);
      }
      // 2) 用中文名兜底（补充英文名匹配不到的）
      const attractsZh = item.attracts_zh || [];
      for (let i = 0; i < attractsZh.length; i++) {
        const nameZh = attractsZh[i];
        const pk = pokemonData.find(function(p) {
          return p.name_zh === nameZh;
        });
        addRef(pk);
      }

      // 给 required_items 补充图片和跳转 key
      const requiredItems = (item.required_items || []).map(function(req) {
        const img = findItemImage(req.name, req.name_zh);
        // 找对应道具，补充 key 用于跳转（is_env 的环境条件不跳转）
        const found = req.is_env ? null : allItemData.find(function(d) {
          return d.name === req.name_zh || d.name_zh === req.name_zh ||
                 d.name === req.name   || d.name_zh === req.name ||
                 d.name_en === req.name || d.name_en === req.name_zh;
        });
        return Object.assign({}, req, {
          image_path: img || null,
          item_key:   found ? found.key : null,
          item_type:  found ? found.category : null,
        });
      });

      item = Object.assign({}, item, {
        attract_refs: attractRefs,
        required_items: requiredItems
      });
    }

    if (item && type === "pokemon") {
      // 动态重建 habitat_refs，使用 habitatData 里的最新图片和中文需求
      const habitatRefs = [];
      const habitats = item.habitats || [];
      for (let i = 0; i < habitats.length; i++) {
        const habName = habitats[i];
        const hab = habitatData.find(function(h) {
          return h.name_zh === habName || h.name === habName;
        });
        if (hab) {
          // 从 required_items 动态生成摘要，避免 required_zh 字段不完整的问题
          var summary = '';
          if (hab.required_items && hab.required_items.length) {
            summary = hab.required_items.map(function(r) {
              return (r.name_zh || r.name) + ' ×' + r.qty;
            }).join(' / ');
          } else {
            summary = hab.required_zh || hab.required || '';
          }
          habitatRefs.push(Object.assign({}, hab, { required_summary: summary }));
        }
      }
      item = Object.assign({}, item, { habitat_refs: habitatRefs });
    }

    this.setData({ item });
    this._type = type;

    // 判断此类型是否支持收集标记
    const collectible = type === "pokemon" || type === "habitat" || type === "cosmetic";
    this._collectType = collectible ? type : null;
    this._collectKey = item ? item.key : null;
    this.setData({
      collectible: collectible && !!item,
      collected: collectible && item ? storage.isCollected(type, item.key) : false
    });

    // 宝可梦城镇选择
    if (type === "pokemon" && item) {
      var savedTown = storage.getTown(item.key);
      this.setData({
        isPokemon: true,
        townIndex: savedTown ? TOWNS.indexOf(savedTown) : -1
      });
    }
  },

  onShow() {
    // 返回详情页时同步收集状态（与列表页保持一致）
    if (this._collectType && this._collectKey) {
      this.setData({ collected: storage.isCollected(this._collectType, this._collectKey) });
    }
  },

  toggleCollect() {
    if (!this._collectType || !this._collectKey) return;
    const newState = storage.toggle(this._collectType, this._collectKey);
    this.setData({ collected: newState });
  },
  onTownChange(e) {
    var idx = Number(e.detail.value);
    var town = TOWNS[idx] || "";
    var key = this.data.item ? this.data.item.key : "";
    if (!key) return;
    storage.setTown(key, town);
    this.setData({ townIndex: idx });
  },
  openMaterial(e) {
    const key = e.currentTarget.dataset.key;
    const type = e.currentTarget.dataset.type;
    if (!key) return;
    wx.navigateTo({
      url: `/pages/detail/detail?type=${type}&key=${encodeURIComponent(key)}`
    });
  },
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
  },

  onShareAppMessage() {
    const item = this.data.item;
    return {
      title: item ? (item.name_zh || item.name) + ' - poko攻略小册' : 'poko攻略小册',
      path: `/pages/detail/detail?type=${this._type}&key=${encodeURIComponent(item ? item.key.split(':')[1] : '')}`
    };
  },

  onShareTimeline() {
    const item = this.data.item;
    return {
      title: item ? (item.name_zh || item.name) + ' - poko攻略小册' : 'poko攻略小册'
    };
  }
});
