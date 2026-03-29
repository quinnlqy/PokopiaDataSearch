var fs = require('fs');
var items = require('../miniprogram/data/items.js');
var sources = require('./item_sources.json');

var srcByName = {};
sources.forEach(function(s) { srcByName[s.name] = s; });

var src = srcByName['水力发电套件'];
console.log('水力发电套件 数据:', JSON.stringify(src, null, 2));

var patched = 0;
var newItems = items.map(function(item) {
  var isHydro = item.name.indexOf('水力发电') >= 0 || item.name.indexOf('水利发电') >= 0;
  if (!isHydro) return item;
  if (item.obtain || item.recipe || item.materials) return item;

  patched++;
  var materials = (src.materials || []).map(function(m) { return { name: m.name, count: m.count }; });
  return Object.assign({}, item, {
    description: src.description || null,
    obtain:      src.obtain      || [],
    recipe:      src.recipe      || [],
    materials:   materials,
  });
});

console.log('补全数量:', patched);
newItems.filter(function(i) { return i.name.indexOf('水力发电') >= 0 || i.name.indexOf('水利发电') >= 0; })
  .forEach(function(i) { console.log(i.name, '| recipe:', i.recipe); });

fs.writeFileSync(
  '../miniprogram/data/items.js',
  'module.exports = ' + JSON.stringify(newItems, null, 2) + ';\n',
  'utf8'
);
console.log('✅ 已写入');
