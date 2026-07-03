import { RESOURCE_KEYS } from './constants.js';
import { computeGearUpgrades } from './gear.js';

// Mirrors src/optimizers/gears.py SCORE_MULTIPLIER.
const SCORE_MULTIPLIER = 36;

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

// DFS over gear slots, budget-pruned, tie-break by per-gear SvS in slot
// priority order. Mirrors src/optimizers/gears.py upgrade_chief_gears(),
// but tracks the running best directly instead of materializing the full
// all_combos list (the Streamlit page never displays all_combos — see plan
// notes for why this yields an identical result).
export function upgradeChiefGears(gearSpecs, gearRows, resources) {
  const tables = gearSpecs.map(g => computeGearUpgrades(gearRows, g.currentTier, resources));

  let bestKey = [-1];
  let bestChosen = null;
  let bestCost = null;

  const acc = { Alloy: 0, Polish: 0, Plans: 0, Amber: 0, SvS: 0 };
  const chosen = [];

  function dfs(i) {
    if (i === tables.length) {
      const candidate = [acc.SvS, ...chosen.map(row => row.SvS)];
      if (tupleGreater(candidate, bestKey)) {
        bestKey = candidate;
        bestChosen = chosen.slice();
        bestCost = { Alloy: acc.Alloy, Polish: acc.Polish, Plans: acc.Plans, Amber: acc.Amber };
      }
      return;
    }

    for (const row of tables[i]) {
      if (RESOURCE_KEYS.some(r => acc[r] + row[r] > (resources[r] ?? 0))) break;

      for (const r of RESOURCE_KEYS) acc[r] += row[r];
      acc.SvS += row.SvS;
      chosen.push(row);

      dfs(i + 1);

      chosen.pop();
      acc.SvS -= row.SvS;
      for (const r of RESOURCE_KEYS) acc[r] -= row[r];
    }
  }

  dfs(0);

  if (bestChosen === null) {
    throw new Error('No feasible upgrade combination found.');
  }

  const remaining = {};
  for (const r of RESOURCE_KEYS) remaining[r] = (resources[r] ?? 0) - bestCost[r];

  const upgradeTable = gearSpecs.map((g, idx) => ({
    gear: g.name,
    oldTier: g.currentTier,
    newTier: bestChosen[idx].tier,
  }));

  const score = bestKey[0] * SCORE_MULTIPLIER;

  return { upgradeTable, cost: bestCost, remaining, score };
}
