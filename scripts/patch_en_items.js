/**
 * 抓取中英文两个页面，建立 英文name → 中文name 的对照表，
 * 然后补全 items.js 里那批英文名道具的来源数据。
 *
 * 用法：node scripts/patch_en_items.js
 */

var https = require('https');
var fs = require('fs');
var path = require('path');

var USER_AGENTS = [
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
];

function sleep(ms) {
  return new Promise(function(resolve) { setTimeout(resolve, ms); });
}

function fetchPage(url, lang) {
  return new Promise(function(resolve, reject) {
    var options = {
      headers: {
        'User-Agent': USER_AGENTS[Math.floor(Math.random() * USER_AGENTS.length)],
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': lang === 'en' ? 'en-US,en;q=0.9' : 'zh-Hans,zh;q=0.9',
        'Accept-Encoding': 'identity',
        'Referer': 'https://pokopiaguide.com/',
      }
    };
    https.get(url, options, function(res) {
      if (res.statusCode === 301 || res.statusCode === 302) {
        return fetchPage(res.headers.location, lang).then(resolve).catch(reject);
      }
      if (res.statusCode !== 200) return reject(new Error('HTTP ' + res.statusCode));
      var chunks = [];
      res.on('data', function(c) { chunks.push(c); });
      res.on('end', function() { resolve(Buffer.concat(chunks).toString('utf8')); });
      res.on('error', reject);
    }).on('error', reject);
  });
}

// 从 HTML 提取道具数组（同 fetch_item_sources.js 的逻辑）
function extractItems(html) {
  var ITEMS_MARKER = '\\"items\\":[{\\"id\\":\\"';
  var firstObtain = html.indexOf('\\"obtain\\"');
  if (firstObtain < 0) throw new Error('找不到 obtain 字段');
  var itemsStart = html.lastIndexOf(ITEMS_MARKER, firstObtain);
  if (itemsStart < 0) throw new Error('找不到 items 数组起点');
  var ITEMS_KEY_LEN = '\\"items\\":'.length;
  var arrayStart = html.indexOf('[', itemsStart + ITEMS_KEY_LEN - 1);
  if (arrayStart < 0) throw new Error('找不到数组起始括号');

  var depth = 0, i = arrayStart, end = -1;
  while (i < html.length) {
    if (html[i] === '\\' && i + 1 < html.length) { i += 2; continue; }
    var ch = html[i];
    if (ch === '[' || ch === '{') depth++;
    else if (ch === ']' || ch === '}') { depth--; if (depth === 0) { end = i; break; } }
    i++;
  }
  if (end < 0) throw new Error('找不到数组结束括号');

  var unescaped = JSON.parse('"' + html.slice(arrayStart, end + 1) + '"');
  return JSON.parse(unescaped);
}

async function main() {
  // 1. 抓英文页
  console.log('抓取英文页...');
  await sleep(600 + Math.floor(Math.random() * 800));
  var enHtml = await fetchPage('https://pokopiaguide.com/items', 'en');
  console.log('英文页大小:', (enHtml.length / 1024).toFixed(1), 'KB');

  var enItems = extractItems(enHtml);
  console.log('英文道具数:', enItems.length);

  // 2. 读取已有中文 sources（已经抓过了，直接用）
  var zhSources = require('../data/item_sources.json');
  console.log('中文道具数:', zhSources.length);

  // 3. 用 imageUrl 中的 item-id 建立 id → 中文name 的对照
  //    英文和中文页同一个道具的 imageUrl 是相同的
  var zhById = {};
  zhSources.forEach(function(s) {
    var m = s.imageUrl && s.imageUrl.match(/item-(\d+)\.png/);
    if (m) zhById[m[1]] = s;
  });

  // 4. 给英文道具找对应的中文name
  var enToZh = {}; // 英文name → 中文name
  var matched = 0, unmatched = [];
  enItems.forEach(function(en) {
    var m = en.imageUrl && en.imageUrl.match(/item-(\d+)\.png/);
    if (m && zhById[m[1]]) {
      enToZh[en.name] = zhById[m[1]].name;
      matched++;
    } else {
      unmatched.push(en.name);
    }
  });
  console.log('\n英文→中文 对照建立:', matched, '条');
  console.log('英文页里也没有中文对应的:', unmatched.length, '条');

  // 保存对照表
  fs.writeFileSync(
    path.join(__dirname, '../data/en_to_zh_name.json'),
    JSON.stringify(enToZh, null, 2), 'utf8'
  );
  console.log('对照表已保存到 data/en_to_zh_name.json');

  // 5. 用对照表补全 items.js 里英文名道具的来源数据
  var itemsPath = path.join(__dirname, '../miniprogram/data/items.js');
  var items = require(itemsPath);

  var sourceByZhName = {};
  zhSources.forEach(function(s) { sourceByZhName[s.name] = s; });

  var patched = 0;
  var stillMissing = [];

  var newItems = items.map(function(item) {
    // 已有来源数据的跳过
    if (item.obtain || item.recipe || item.materials) return item;

    // 用对照表找中文名
    var zhName = enToZh[item.name];
    if (!zhName) { stillMissing.push(item.name); return item; }

    var src = sourceByZhName[zhName];
    if (!src) { stillMissing.push(item.name + ' (中文名已找到:' + zhName + ',但sources里没有)'); return item; }

    var hasAny = (src.obtain && src.obtain.length > 0)
               || (src.recipe && src.recipe.length > 0)
               || (src.materials && src.materials.length > 0);
    if (!hasAny) { stillMissing.push(item.name + ' (数据为空)'); return item; }

    patched++;
    var materials = (src.materials || []).map(function(mat) {
      return { name: mat.name, count: mat.count };
    });
    return Object.assign({}, item, {
      name_zh:     zhName,
      description: src.description || null,
      obtain:      src.obtain      || [],
      recipe:      src.recipe      || [],
      materials:   materials,
    });
  });

  console.log('\n补全道具数:', patched);
  console.log('仍然缺失:', stillMissing.length);
  if (stillMissing.length) {
    console.log('缺失列表:');
    stillMissing.forEach(function(n) { console.log(' ', n); });
  }

  // 写回 items.js
  fs.writeFileSync(itemsPath, 'module.exports = ' + JSON.stringify(newItems, null, 2) + ';\n', 'utf8');
  console.log('\n✅ 已写入:', itemsPath);
}

main().catch(function(err) { console.error('错误:', err.message); process.exit(1); });
