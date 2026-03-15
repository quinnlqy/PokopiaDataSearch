function tokenize(q) {
  const base = q
    .trim()
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean);
  return expandTokens(base);
}

function expandTokens(tokens) {
  const extra = [];
  const map = {
    草: ["grass"],
    火: ["fire"],
    水: ["water"],
    电: ["electric"],
    雷: ["electric"],
    岩: ["rock"],
    地: ["ground"],
    飞: ["flying"],
    冰: ["ice"],
    虫: ["bug"],
    毒: ["poison"],
    超: ["psychic"],
    鬼: ["ghost"],
    钢: ["steel"],
    龙: ["dragon"],
    妖: ["fairy"],
    格斗: ["fighting"],
    恶: ["dark"],
    一般: ["normal"],
    料理: ["料理", "食谱", "菜谱", "食物"]
  };
  tokens.forEach((t) => {
    Object.keys(map).forEach((k) => {
      if (t.indexOf(k) >= 0) {
        map[k].forEach((v) => extra.push(v));
      }
    });
  });
  return Array.from(new Set(tokens.concat(extra)));
}

function matchScore(text, tokens) {
  const t = text.toLowerCase();
  let score = 0;
  tokens.forEach((tok) => {
    if (t.indexOf(tok) >= 0) score += 1;
  });
  return score;
}

function search(rows, fields, tokens, limit) {
  const scored = [];
  rows.forEach((row) => {
    const parts = [];
    fields.forEach((f) => {
      const v = row[f];
      if (Array.isArray(v)) {
        parts.push(v.join(" "));
      } else if (v !== null && v !== undefined) {
        parts.push(String(v));
      }
    });
    const text = parts.join(" | ");
    const score = matchScore(text, tokens);
    if (score > 0) scored.push({ score, row });
  });
  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, limit).map((x) => x.row);
}

module.exports = {
  tokenize,
  search
};
