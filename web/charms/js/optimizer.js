import { computeCharmTypeOptions } from './charm.js';

// Mirrors src/optimizers/charms.py SCORE_MULTIPLIER.
const SCORE_MULTIPLIER = 70;

// Lexicographic tuple compare: true if a > b, comparing element by element.
// Missing trailing elements compare as -Infinity (matches Python's tuple
// ordering for the (-1,) sentinel starting key).
function tupleGreater(a, b) {
  const len = Math.max(a.length, b.length);
  for (let i = 0; i < len; i++) {
    const av = i < a.length ? a[i] : -Infinity;
    const bv = i < b.length ? b[i] : -Infinity;
    if (av !== bv) return av > bv;
  }
  return false;
}

// DFS over the 6 charm types, budget-pruned (Guide-sorted options -> break
// on overflow; Design isn't sorted -> continue), tie-break by per-type SvS
// in type priority order. Mirrors src/optimizers/charms.py upgrade_charms(),
// tracking the running best directly instead of materializing all_combos
// (see plan notes for why this yields an identical result).
export function upgradeCharms(charmSpecs, charmRows, resources) {
  const groups = charmSpecs.map(c => computeCharmTypeOptions(charmRows, c.currentLevels, resources));

  let bestKey = [-1];
  let bestChosen = null;
  let bestCost = null;

  const acc = { Guide: 0, Design: 0, SvS: 0 };
  const chosen = [];

  function dfs(i) {
    if (i === groups.length) {
      const candidate = [acc.SvS, ...chosen.map(o => o.SvS)];
      if (tupleGreater(candidate, bestKey)) {
        bestKey = candidate;
        bestChosen = chosen.slice();
        bestCost = { Guide: acc.Guide, Design: acc.Design };
      }
      return;
    }

    for (const opt of groups[i]) {
      if (acc.Guide + opt.Guide > (resources.Guide ?? 0)) break;
      if (acc.Design + opt.Design > (resources.Design ?? 0)) continue;

      acc.Guide += opt.Guide;
      acc.Design += opt.Design;
      acc.SvS += opt.SvS;
      chosen.push(opt);

      dfs(i + 1);

      chosen.pop();
      acc.SvS -= opt.SvS;
      acc.Guide -= opt.Guide;
      acc.Design -= opt.Design;
    }
  }

  dfs(0);

  if (bestChosen === null) {
    throw new Error('No feasible upgrade combination found.');
  }

  const remaining = {
    Guide: (resources.Guide ?? 0) - bestCost.Guide,
    Design: (resources.Design ?? 0) - bestCost.Design,
  };

  const upgradeTable = charmSpecs.map((c, idx) => ({
    charm: c.name,
    oldLevels: c.currentLevels,
    newLevels: bestChosen[idx].levels,
  }));

  const score = bestKey[0] * SCORE_MULTIPLIER;

  return { upgradeTable, cost: bestCost, remaining, score };
}
