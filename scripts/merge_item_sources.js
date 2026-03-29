/**
 * 把 data/item_sources.json 的来源信息合并进 miniprogram/data/items.js
 *
 * 匹配策略（按优先级）：
 *   1. 按道具名字匹配
 *   2. 按图片 URL 中的 item id 匹配（应对改名道具）
 *
 * 新增字段：
 *   - description : 道具描述文字
 *   - obtain      : 来源数组（地图捡取、宝可梦产出等）
 *   - recipe      : 来源数组（商店购买含等级、任务奖励、特殊条件等）
 *   - materials   : 制作材料数组 [{name, count}]
 *
 * 用法：node scripts/merge_item_sources.js
 */

var fs = require('fs');
var path = require('path');

var ITEMS_PATH   = path.join(__dirname, '../miniprogram/data/items.js');
var SOURCES_PATH = path.join(__dirname, '../data/item_sources.json');

// ── 读取数据 ───────────────────────────────────────────────────────────────
var items   = require(ITEMS_PATH);
var sources = require(SOURCES_PATH);

// ── 建立两级索引 ───────────────────────────────────────────────────────────
var sourceByName = {};
var sourceByImgId = {};

sources.forEach(function(s) {
  sourceByName[s.name] = s;
  var m = s.imageUrl && s.imageUrl.match(/item-(\d+)\.png/);
  if (m) sourceByImgId[m[1]] = s;
});

function getImgId(url) {
  if (!url) return null;
  var m = url.match(/item-(\d+)\.png/);
  return m ? m[1] : null;
}

// ── 合并 ───────────────────────────────────────────────────────────────────
var stats = { byName: 0, byId: 0, noMatch: 0 };

var merged = items.map(function(item) {
  // 找对应的 source 记录
  var src = sourceByName[item.name];
  if (src) {
    stats.byName++;
  } else {
    var id = getImgId(item.image_url);
    if (id && sourceByImgId[id]) {
      src = sourceByImgId[id];
      stats.byId++;
    }
  }

  if (!src) {
    stats.noMatch++;
    return item; // 没找到就原样保留
  }

  // 只保留材料的 name 和 count，不需要 id / imageUrl
  var materials = (src.materials || []).map(function(mat) {
    return { name: mat.name, count: mat.count };
  });

  return Object.assign({}, item, {
    description : src.description   || null,
    obtain      : src.obtain        || [],
    recipe      : src.recipe        || [],
    materials   : materials,
  });
});

// ── 输出统计 ───────────────────────────────────────────────────────────────
console.log('合并完成:');
console.log('  按名字匹配:', stats.byName);
console.log('  按图片id匹配:', stats.byId);
console.log('  未匹配（原样保留）:', stats.noMatch);

// ── 写入 items.js ─────────────────────────────────────────────────────────
var output = 'module.exports = ' + JSON.stringify(merged, null, 2) + ';\n';
fs.writeFileSync(ITEMS_PATH, output, 'utf8');
console.log('\n✅ 已写入:', ITEMS_PATH);
