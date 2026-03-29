var d = require('./miniprogram/data/items.js');
// 完整看这几个条目
['帅气电贝斯','帅气电吉他','酷炫贝斯','酷炫电吉他'].forEach(function(n){
  var x = d.find(function(i){ return i.name_zh===n; });
  if(x) console.log(JSON.stringify({name_zh:x.name_zh, name:x.name, key:x.key, image_url:x.image_url, image_path:(x.image_path||'').split('/').pop()}));
});
