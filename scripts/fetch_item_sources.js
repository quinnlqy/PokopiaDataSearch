/**
 * 抓取 pokopiaguide.com/zh-Hans/items 页面里内嵌的 __next_f 流式数据，
 * 提取每个道具的来源信息（obtain / recipe / materials），
 * 写入 data/item_sources.json。
 *
 * 用法：node scripts/fetch_item_sources.js
 */

const https = require('https');
const fs = require('fs');
const path = require('path');

// ── 伪装成普通 Chrome 用户 ─────────────────────────────────────────────────
const USER_AGENTS = [
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0',
];

function randomUA() {
  return USER_AGENTS[Math.floor(Math.random() * USER_AGENTS.length)];
}

function sleep(ms) {
  return new Promise(function(resolve) { setTimeout(resolve, ms); });
}

// ── 核心请求函数 ──────────────────────────────────────────────────────────
function fetchPage(url) {
  return new Promise(function(resolve, reject) {
    var options = {
      headers: {
        'User-Agent': randomUA(),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-Hans,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'identity',
        'Connection': 'keep-alive',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Referer': 'https://pokopiaguide.com/',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Upgrade-Insecure-Requests': '1',
      },
    };

    https.get(url, options, function(res) {
      if (res.statusCode === 301 || res.statusCode === 302) {
        return fetchPage(res.headers.location).then(resolve).catch(reject);
      }
      if (res.statusCode !== 200) {
        return reject(new Error('HTTP ' + res.statusCode + ' for ' + url));
      }
      var chunks = [];
      res.on('data', function(chunk) { chunks.push(chunk); });
      res.on('end', function() { resolve(Buffer.concat(chunks).toString('utf8')); });
      res.on('error', reject);
    }).on('error', reject);
  });
}

// ── 从 __next_f 流式 HTML 中提取道具数组 ─────────────────────────────────
//
// Next.js App Router 把页面数据以这种格式写入 HTML：
//   self.__next_f.push([1, "...大段转义JSON字符串..."]);
//
// 道具数据嵌套在其中，格式（原始，未转义）为：
//   {"items":[{"id":"135","name":"CD播放器","nameJa":"...","categoryKey":"goods",
//              "imageUrl":"/images/items/item-135.png","description":"...",
//              "obtain":["从梦之岛的精灵球取得","在商店购买（崭新小镇Lv.3）"],
//              "recipe":["在商店购买（闪亮浮岛 Lv. 3）"],
//              "materials":[{"id":"78","name":"宝可金属","count":1,"imageUrl":"..."}]},
//             ...]}
//
// 在 HTML 里这段数据是双重转义的：\" 变成 \\\"，/ 保持不变
//
function extractItems(html) {
  // 找 \"obtain\" 的转义形式（在 HTML 的 JS 字符串字面量里）
  var OBTAIN_MARKER = '\\"obtain\\"';
  var firstObtain = html.indexOf(OBTAIN_MARKER);
  if (firstObtain < 0) {
    throw new Error('找不到 obtain 字段，页面结构可能已变化');
  }

  // 往前找 \"items\":[ 的起点（道具数组的开始）
  var ITEMS_MARKER = '\\"items\\":[{\\"id\\":\\"';
  var itemsStart = html.lastIndexOf(ITEMS_MARKER, firstObtain);
  if (itemsStart < 0) {
    throw new Error('找不到 items 数组起点');
  }

  // \"items\": 共10个字符（\+"+"items+\+"+:），之后紧跟 [
  // 用 indexOf('[', itemsStart) 但限制在10字符内，确保找的是紧跟的那个 [
  var ITEMS_KEY_LEN = '\\"items\\":'.length; // = 10
  var arrayStart = html.indexOf('[', itemsStart + ITEMS_KEY_LEN - 1);
  if (arrayStart < 0 || arrayStart > itemsStart + ITEMS_KEY_LEN + 2) {
    throw new Error('找不到 [ 数组起始括号');
  }

  // 在转义字符串里手动匹配括号，注意 \\\" 是转义引号，\\\\ 是转义反斜杠
  // 我们在 HTML 原始字节层面扫描，遇到 \\" 跳过下一字符
  var depth = 0;
  var i = arrayStart;
  var end = -1;
  while (i < html.length) {
    // 处理转义：\\ 后面的字符跳过
    if (html[i] === '\\' && i + 1 < html.length) {
      i += 2;
      continue;
    }
    var ch = html[i];
    if (ch === '[' || ch === '{') depth++;
    else if (ch === ']' || ch === '}') {
      depth--;
      if (depth === 0) { end = i; break; }
    }
    i++;
  }

  if (end < 0) {
    throw new Error('找不到数组结束括号，数据可能被截断');
  }

  // 截取这段转义字符串，包成合法 JSON 字符串再解析
  var escapedArray = html.slice(arrayStart, end + 1);

  // 这段内容是 JSON 字符串里的内容（\\\" → \"，\\\\ → \\）
  // 用 JSON.parse 包装成字符串解析来正确反转义
  var unescaped;
  try {
    unescaped = JSON.parse('"' + escapedArray + '"');
  } catch (e) {
    throw new Error('反转义失败: ' + e.message);
  }

  return JSON.parse(unescaped);
}

// ── 主流程 ────────────────────────────────────────────────────────────────
async function main() {
  var TARGET_URL = 'https://pokopiaguide.com/zh-Hans/items';
  var OUT_PATH = path.join(__dirname, '../data/item_sources.json');

  console.log('准备抓取道具来源数据...');
  console.log('目标:', TARGET_URL);

  var waitMs = 800 + Math.floor(Math.random() * 1200);
  console.log('等待 ' + waitMs + 'ms 后开始请求...');
  await sleep(waitMs);

  console.log('正在请求页面...');
  var html;
  try {
    html = await fetchPage(TARGET_URL);
  } catch (err) {
    console.error('请求失败:', err.message);
    process.exit(1);
  }

  console.log('页面大小: ' + (html.length / 1024).toFixed(1) + ' KB');

  // 提取道具数组
  var items;
  try {
    items = extractItems(html);
  } catch (err) {
    console.error('提取道具数据失败:', err.message);
    fs.writeFileSync(path.join(__dirname, '../data/debug_items_page.html'), html);
    console.log('已保存原始 HTML 到 data/debug_items_page.html，请手动检查');
    process.exit(1);
  }

  if (!Array.isArray(items)) {
    console.error('解析结果不是数组，请检查 data/debug_items_page.html');
    process.exit(1);
  }

  console.log('找到 ' + items.length + ' 个道具');

  // 打印前2个道具看结构是否正确
  console.log('\n── 前2个道具示例 ──');
  items.slice(0, 2).forEach(function(item, i) {
    console.log('[' + i + ']', JSON.stringify(item, null, 2));
  });
  console.log('──────────────────\n');

  // 统计
  var withObtain = items.filter(function(s) { return s.obtain && s.obtain.length > 0; }).length;
  var withRecipe = items.filter(function(s) { return s.recipe && s.recipe.length > 0; }).length;
  var withMaterials = items.filter(function(s) { return s.materials && s.materials.length > 0; }).length;
  console.log('有 obtain（地图/宝可梦等来源）: ' + withObtain);
  console.log('有 recipe（商店/等级/特殊来源）: ' + withRecipe);
  console.log('有 materials（制作材料）: ' + withMaterials);

  // 写入结果
  fs.mkdirSync(path.dirname(OUT_PATH), { recursive: true });
  fs.writeFileSync(OUT_PATH, JSON.stringify(items, null, 2), 'utf8');
  console.log('\n✅ 完成！来源数据已保存到: ' + OUT_PATH);
}

main().catch(function(err) {
  console.error('未知错误:', err);
  process.exit(1);
});
