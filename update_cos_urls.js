/**
 * 将家具、服装、料理数据中的外链图片 URL 替换为 COS URL。
 * 
 * 前提：已将 download_for_cos/ 下的文件上传到 COS 对应目录：
 *   furniture/ -> COS: /furniture/
 *   cosmetics/ -> COS: /cosmetics/
 *   cooking/   -> COS: /cooking/
 *
 * 用法：node update_cos_urls.js
 */

var fs = require('fs');
var path = require('path');

var COS_BASE = 'https://pokopia-images-1251329367.cos.ap-guangzhou.myqcloud.com/';
var mapping = require('./download_for_cos/cos_mapping.json');

// 4 个 pokopiaguide 上缺图的家具，用 COS 上已有的英文名文件替代
var FURNITURE_OVERRIDES = {
  '办公室收纳柜': COS_BASE + 'furniture/office-cabinet.png',
  '自然风矮凳':   COS_BASE + 'furniture/plain-stool.png',
  '豪华椅':       COS_BASE + 'furniture/fancy-chair.png',
  '普普风椅':     COS_BASE + 'furniture/pop-art-chair.png'
};

// 统计
var stats = { furniture: 0, cosmetics: 0, cooking: 0, overrides: 0 };

function updateFile(dataPath, category) {
  var data = require(dataPath);
  var changed = 0;
  data.forEach(function(item) {
    // 优先用 override（解决占位图问题）
    var nameZh = item.name_zh || item.name;
    if (category === 'furniture' && FURNITURE_OVERRIDES[nameZh]) {
      item.image_path = FURNITURE_OVERRIDES[nameZh];
      changed++;
      stats.overrides++;
      console.log('  [override] ' + nameZh + ' -> ' + FURNITURE_OVERRIDES[nameZh].split('/').pop());
      return;
    }
    // 常规映射
    var url = item.image_url;
    if (url && mapping[url]) {
      item.image_path = COS_BASE + mapping[url];
      changed++;
    }
  });
  fs.writeFileSync(dataPath, 'module.exports = ' + JSON.stringify(data) + ';', 'utf8');
  stats[category] = changed;
  console.log(category + ': updated ' + changed + ' items');
}

updateFile(path.resolve('./miniprogram/data/furniture.js'), 'furniture');
updateFile(path.resolve('./miniprogram/data/cosmetics.js'), 'cosmetics');
updateFile(path.resolve('./miniprogram/data/cooking.js'), 'cooking');

console.log('\nDone! Total updated:', stats.furniture + stats.cosmetics + stats.cooking);
console.log('  (including ' + stats.overrides + ' placeholder overrides using existing COS files)');
console.log('image_path now points to COS, image_url kept as fallback.');
