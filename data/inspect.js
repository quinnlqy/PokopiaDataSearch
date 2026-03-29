const fs = require('fs');
const html = fs.readFileSync('data/debug_items_page.html', 'utf8');
const parts = html.split('<script');
const inline = parts.filter(p => p.startsWith(' src=') === false && p.includes('>'));
inline.forEach(function(s, i) {
  const end = s.indexOf('</script>');
  const content = s.slice(s.indexOf('>')+1, end >= 0 ? end : undefined);
  if (content.includes('"nameZh"') || content.includes('"obtain"') || content.includes('"image_url"') || content.length > 10000) {
    console.log('--- script', i, '长度:', content.length, '---');
    console.log(content.slice(0, 1000));
    console.log('...\n');
  }
});
