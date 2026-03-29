const items = require('../miniprogram/data/items.js');
const sources = require('./item_sources.json');

// 同时用 name 和 imageUrl 中的 id 建立索引
const sourceByName = {};
const sourceById = {};
sources.forEach(function(s) {
  sourceByName[s.name] = s;
  // 从 imageUrl 提取 item id，如 /images/items/item-135.png → 135
  var m = s.imageUrl && s.imageUrl.match(/item-(\d+)\.png/);
  if (m) sourceById[m[1]] = s;
});

// 从 items.js 的 image_url 提取 id
function getIdFromUrl(url) {
  if (!url) return null;
  var m = url.match(/item-(\d+)\.png/);
  return m ? m[1] : null;
}

var matchedByName = 0, matchedById = 0, unmatched = [];
items.forEach(function(item) {
  var s = sourceByName[item.name];
  if (s) { matchedByName++; return; }
  var id = getIdFromUrl(item.image_url);
  if (id && sourceById[id]) { matchedById++; return; }
  unmatched.push({ name: item.name, image_url: item.image_url });
});

console.log('按名字匹配:', matchedByName);
console.log('按图片id匹配:', matchedById);
console.log('未匹配:', unmatched.length);
console.log('\n前10个未匹配:');
unmatched.slice(0, 10).forEach(function(u) { console.log(u); });
