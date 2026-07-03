function combinationsWithReplacement(n, k) {
  if (k === 0) return [[]];
  const results = [];
  const combo = new Array(k).fill(0);
  function rec(start, depth) {
    if (depth === k) { results.push(combo.slice()); return; }
    for (let i = start; i < n; i++) {
      combo[depth] = i;
      rec(i, depth + 1);
    }
  }
  rec(0, 0);
  return results;
}

function cartesianProduct(arrays) {
  return arrays.reduce((acc, arr) => {
    const next = [];
    for (const a of acc) {
      for (const item of arr) next.push([...a, item]);
    }
    return next;
  }, [[]]);
}

// Cumulative upgrade table for one charm, starting at currentLevel.
// Mirrors src/struct/charm.py Charm._single_table().
export function singleCharmTable(charmRows, currentLevel, resources) {
  const table = [];
  const cumulative = { Guide: 0, Design: 0, SvS: 0 };
  let started = false;

  for (const row of charmRows) {
    if (row.level === currentLevel) {
      started = true;
      table.push({ level: row.level, Guide: 0, Design: 0, SvS: 0 });
      continue;
    }
    if (!started) continue;

    if (row.guide != null) cumulative.Guide += row.guide;
    if (row.design != null) cumulative.Design += row.design;
    cumulative.SvS += row.svsScore;

    if (cumulative.Guide > (resources.Guide ?? 0) || cumulative.Design > (resources.Design ?? 0)) break;

    table.push({ level: row.level, Guide: cumulative.Guide, Design: cumulative.Design, SvS: cumulative.SvS });
  }

  return table;
}

// Builds the option list for one equipment type (its N_CHARMS independent
// charms), grouping charms by identical current level (combinations_with_replacement
// within a subgroup, cartesian product across subgroups). Mirrors
// src/struct/charm.py Charm.compute_upgrades().
export function computeCharmTypeOptions(charmRows, currentLevels, resources) {
  const distinctLevels = [...new Set(currentLevels)];
  const charmTables = {};
  distinctLevels.forEach(lvl => { charmTables[lvl] = singleCharmTable(charmRows, lvl, resources); });

  const counts = new Map();
  currentLevels.forEach(lvl => counts.set(lvl, (counts.get(lvl) ?? 0) + 1));

  const perSubgroup = [];
  for (const [lvl, count] of counts.entries()) {
    const rows = charmTables[lvl];
    const combos = combinationsWithReplacement(rows.length, count);
    const sub = combos.map(indices => ({
      pairs: indices.map(j => [lvl, rows[j].level]),
      Guide: indices.reduce((s, j) => s + rows[j].Guide, 0),
      Design: indices.reduce((s, j) => s + rows[j].Design, 0),
      SvS: indices.reduce((s, j) => s + rows[j].SvS, 0),
    }));
    perSubgroup.push(sub);
  }

  const options = [];
  for (const combo of cartesianProduct(perSubgroup)) {
    const guide = combo.reduce((s, c) => s + c.Guide, 0);
    const design = combo.reduce((s, c) => s + c.Design, 0);
    const svs = combo.reduce((s, c) => s + c.SvS, 0);
    if (guide > (resources.Guide ?? 0) || design > (resources.Design ?? 0)) continue;
    const pairs = combo.flatMap(c => c.pairs);
    const levels = pairs.map(p => p[1]).sort((a, b) => a - b);
    options.push({ pairs, levels, Guide: guide, Design: design, SvS: svs });
  }

  options.sort((a, b) => a.Guide - b.Guide || a.Design - b.Design);
  return options;
}
