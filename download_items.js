const https = require('https');
const fs = require('fs');
const path = require('path');

const nums = [1,3,5,6,10,15,17,24,25,29,39,51,54,55,57,60,61,70,72,75,80,83,86,87,90,94,97,
  104,106,107,112,118,119,122,123,124,127,134,142,143,144,145,149,152,155,157,166,168,175,
  177,178,179,180,193,196,198,199,201,204,207,208,209,216,219,220,222,224,226,227,228,229,
  230,231,232,233,234,235,236,237,238,239,240,241,242,243,244,245,246,247,248,249,250,251,
  253,259,260,267,268,269,270,271,274,275,276,277,279,280,281,282,285,292,297,298,305,318,
  319,320,321,322,326,327,330,333,340,341,346,347,349,353,372,380,381,383,384,387,391,392,
  396,400,406,407,408,412,414,418,420,422,424,425,426,427,428,429,434,452,453,456,457,460,
  461,463,465,479,485,486,493,499,506,507,516,517,520,529,531,533,534,536,540,541,542,543,
  544,545,551,561,563,564,565,566,567,568,569,570,571,572,573,574,575,576,577,578,579,580,
  582,583,589,590,591,592,593,601,602,603,604,605,607,616,619,621,623,628,633,635,637,640,
  642,654,667,670,674,677,687,691,716,720,721,724,726,727,728,729,731,732,734,740,745,753,
  755,756,758,759,760,762,768,769,770,773,774,775,776,777,778,779,780,781,785,787,788,791,
  793,794,796,798,802,803,808,814,815,818,819,820,825,828,833,835,839,843,844,846,847,850,
  853,854,855];

const outDir = path.join(__dirname, 'download_items');
if (!fs.existsSync(outDir)) fs.mkdirSync(outDir);

let done = 0, errors = [];

function download(num, cb) {
  const url = 'https://pokopiaguide.com/images/items/item-' + num + '.png';
  const dest = path.join(outDir, 'item-' + num + '.png');
  const file = fs.createWriteStream(dest);
  https.get(url, function(res) {
    if (res.statusCode !== 200) {
      file.close();
      fs.unlinkSync(dest);
      errors.push('item-' + num + ' (' + res.statusCode + ')');
      cb();
      return;
    }
    res.pipe(file);
    file.on('finish', function() { file.close(cb); });
  }).on('error', function(e) {
    errors.push('item-' + num + ' (error)');
    cb();
  });
}

// 并发10个
var queue = nums.slice();
var running = 0;
var concurrency = 10;

function next() {
  while (running < concurrency && queue.length > 0) {
    var n = queue.shift();
    running++;
    download(n, function() {
      running--;
      done++;
      if (done % 30 === 0) process.stdout.write(done + '/' + nums.length + '...\n');
      if (queue.length === 0 && running === 0) {
        console.log('\n完成! 成功:', done - errors.length, '失败:', errors.length);
        if (errors.length) console.log('失败列表:', errors.join(', '));
        console.log('图片保存在:', outDir);
      }
      next();
    });
  }
}

console.log('开始下载', nums.length, '张图片...');
next();
