/**
 * 下载家具、服装、料理的外链图片到本地，准备上传 COS。
 * 
 * 输出目录：
 *   download_for_cos/furniture/   — 107 张
 *   download_for_cos/cosmetics/   — 21 张
 *   download_for_cos/cooking/     — 24 张
 *
 * 用法：node download_for_cos.js
 */

var https = require('https');
var http = require('http');
var fs = require('fs');
var path = require('path');

var furniture = require('./miniprogram/data/furniture.js');
var cosmetics = require('./miniprogram/data/cosmetics.js');
var cooking = require('./miniprogram/data/cooking.js');

var OUT_BASE = path.join(__dirname, 'download_for_cos');

// ---------- 收集下载任务 ----------

var tasks = [];

// 家具：用中文名转拼音不靠谱，直接从 URL 提取 item-xxx.png 作为文件名
furniture.forEach(function(item) {
  var url = item.image_url;
  if (!url) return;
  // URL 格式: https://pokopiaguide.com/images/items/item-472.png
  var m = url.match(/\/(item-\d+\.png)$/);
  var filename = m ? m[1] : null;
  if (!filename) {
    // fallback: 用 name_zh 做文件名
    filename = (item.name_zh || item.name || 'unknown').replace(/[\/\\:*?"<>|]/g, '_') + '.png';
  }
  tasks.push({
    cat: 'furniture',
    name: item.name_zh || item.name,
    url: url,
    filename: filename,
    cos_key: 'furniture/' + filename
  });
});

// 服装：URL 格式 https://www.serebii.net/pokemonpokopia/custom/th/1.jpg
cosmetics.forEach(function(item) {
  var url = item.image_url;
  if (!url) return;
  var m = url.match(/\/(\d+\.jpg)$/);
  // 用英文名做文件名（更易辨识）
  var safeName = (item.name || item.name_zh || 'unknown').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  var filename = safeName + '.jpg';
  tasks.push({
    cat: 'cosmetics',
    name: item.name_zh || item.name,
    url: url,
    filename: filename,
    cos_key: 'cosmetics/' + filename
  });
});

// 料理：URL 格式 https://pokopiaguide.com/images/cooking/cooking-xxx.png
cooking.forEach(function(item) {
  var url = item.image_url;
  if (!url) return;
  var m = url.match(/\/(cooking-[^/]+\.png)$/);
  var filename = m ? m[1] : null;
  if (!filename) {
    // fallback: 从 URL 取最后一段
    var parts = url.split('/');
    filename = parts[parts.length - 1] || 'unknown.png';
  }
  tasks.push({
    cat: 'cooking',
    name: item.name_zh || item.name,
    url: url,
    filename: filename,
    cos_key: 'cooking/' + filename
  });
});

console.log('Download tasks:');
console.log('  furniture:', tasks.filter(function(t) { return t.cat === 'furniture'; }).length);
console.log('  cosmetics:', tasks.filter(function(t) { return t.cat === 'cosmetics'; }).length);
console.log('  cooking:', tasks.filter(function(t) { return t.cat === 'cooking'; }).length);
console.log('  total:', tasks.length);

// ---------- 创建目录 ----------

['furniture', 'cosmetics', 'cooking'].forEach(function(dir) {
  var p = path.join(OUT_BASE, dir);
  fs.mkdirSync(p, { recursive: true });
});

// ---------- 下载 ----------

var USER_AGENTS = [
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
];

function randomUA() {
  return USER_AGENTS[Math.floor(Math.random() * USER_AGENTS.length)];
}

function download(task, cb) {
  var dest = path.join(OUT_BASE, task.cat, task.filename);
  
  // 已存在则跳过
  if (fs.existsSync(dest) && fs.statSync(dest).size > 100) {
    return cb(null, 'skipped');
  }

  var client = task.url.indexOf('https') === 0 ? https : http;
  var options = {
    headers: {
      'User-Agent': randomUA(),
      'Accept': 'image/avif,image/webp,image/png,image/jpeg,*/*',
      'Referer': task.url.indexOf('serebii') >= 0 ? 'https://www.serebii.net/' : 'https://pokopiaguide.com/',
    }
  };

  client.get(task.url, options, function(res) {
    if (res.statusCode === 301 || res.statusCode === 302) {
      // follow redirect
      task.url = res.headers.location;
      return download(task, cb);
    }
    if (res.statusCode !== 200) {
      return cb('HTTP ' + res.statusCode, null);
    }
    var file = fs.createWriteStream(dest);
    res.pipe(file);
    file.on('finish', function() {
      file.close(function() { cb(null, 'ok'); });
    });
    file.on('error', function(e) { cb(e.message, null); });
  }).on('error', function(e) {
    cb(e.message, null);
  });
}

// 并发控制
var queue = tasks.slice();
var running = 0;
var CONCURRENCY = 5;
var doneCount = 0;
var errors = [];

function nextTask() {
  while (running < CONCURRENCY && queue.length > 0) {
    var task = queue.shift();
    running++;
    (function(t) {
      download(t, function(err, status) {
        running--;
        doneCount++;
        if (err) {
          errors.push({ name: t.name, cat: t.cat, url: t.url, error: err });
          process.stdout.write('  FAIL [' + t.cat + '] ' + t.name + ': ' + err + '\n');
        }
        if (doneCount % 20 === 0 || doneCount === tasks.length) {
          process.stdout.write('  progress: ' + doneCount + '/' + tasks.length + '\n');
        }
        if (queue.length === 0 && running === 0) {
          finish();
        } else {
          nextTask();
        }
      });
    })(task);
  }
}

function finish() {
  console.log('\n=== Done ===');
  console.log('Success:', doneCount - errors.length);
  console.log('Failed:', errors.length);
  if (errors.length > 0) {
    console.log('\nFailed items:');
    errors.forEach(function(e) {
      console.log('  [' + e.cat + '] ' + e.name + ' : ' + e.error);
      console.log('    ' + e.url);
    });
  }

  // 生成 COS 路径映射表，方便后续替换
  var mapping = {};
  tasks.forEach(function(t) {
    mapping[t.url] = t.cos_key;
  });
  fs.writeFileSync(path.join(OUT_BASE, 'cos_mapping.json'), JSON.stringify(mapping, null, 2), 'utf8');
  console.log('\nCOS mapping saved to download_for_cos/cos_mapping.json');
  console.log('Images saved to download_for_cos/');
  console.log('\n下一步：将 download_for_cos/ 下的三个文件夹上传到 COS 对应目录');
}

console.log('\nStarting downloads...\n');
nextTask();
