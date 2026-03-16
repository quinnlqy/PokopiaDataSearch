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

// 字段分类及权重
const NAME_FIELDS = ["name", "name_zh", "name_en"];   // 子串匹配，高权重
const EXACT_FIELDS = ["types", "favorites", "attracts", "attracts_zh", "tools", "power_up_moves"]; // 列表项整词匹配，低权重
const NAME_SCORE = 10;
const EXACT_SCORE = 2;
const OTHER_SCORE = 1;

// 判断 token 是否与列表中某项完整匹配（该项包含 token 且 token 不是某更长词的片段）
function matchList(arr, tok) {
  const t = tok.toLowerCase();
  for (var i = 0; i < arr.length; i++) {
    var item = String(arr[i]).toLowerCase();
    // 整词匹配：item 等于 token，或 item 以 token 开头/结尾且紧邻边界
    // 简单策略：item 包含 token 且 item 长度 <= token 长度 * 2
    if (item === t) return true;
    if (item.indexOf(t) >= 0 && item.length <= t.length * 2) return true;
  }
  return false;
}

function search(rows, fields, tokens, limit) {
  const scored = [];
  rows.forEach((row) => {
    let score = 0;
    fields.forEach((f) => {
      const v = row[f];
      if (v === null || v === undefined) return;

      if (NAME_FIELDS.indexOf(f) >= 0) {
        // 名称字段：子串匹配，高权重
        const text = String(v).toLowerCase();
        tokens.forEach((tok) => {
          if (text.indexOf(tok) >= 0) score += NAME_SCORE;
        });
      } else if (Array.isArray(v) && EXACT_FIELDS.indexOf(f) >= 0) {
        // 列表字段（喜好/属性等）：整词匹配，中权重
        tokens.forEach((tok) => {
          if (matchList(v, tok)) score += EXACT_SCORE;
        });
      } else {
        // 其他字段：子串匹配，低权重
        const text = (Array.isArray(v) ? v.join(" ") : String(v)).toLowerCase();
        tokens.forEach((tok) => {
          if (text.indexOf(tok) >= 0) score += OTHER_SCORE;
        });
      }
    });
    if (score > 0) scored.push({ score, row });
  });
  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, limit).map((x) => x.row);
}

module.exports = {
  tokenize,
  search
};
