import { RESOURCE_KEYS } from './constants.js';

// Cumulative upgrade table for one gear, starting at its current tier.
// Mirrors src/struct/gear.py Gear.compute_upgrades().
export function computeGearUpgrades(rows, currentTier, resources) {
  const table = [];
  const cumulative = { Alloy: 0, Polish: 0, Plans: 0, Amber: 0, SvS: 0 };
  let started = false;

  for (const row of rows) {
    if (row.tier === currentTier) {
      started = true;
      table.push({ tier: row.tier, Alloy: 0, Polish: 0, Plans: 0, Amber: 0, SvS: 0 });
      continue;
    }
    if (!started) continue;

    for (const r of RESOURCE_KEYS) {
      const v = row[r.toLowerCase()];
      if (v != null) cumulative[r] += v;
    }
    cumulative.SvS += row.svsScore;

    if (RESOURCE_KEYS.some(r => cumulative[r] > (resources[r] ?? 0))) break;

    table.push({
      tier: row.tier,
      Alloy: cumulative.Alloy,
      Polish: cumulative.Polish,
      Plans: cumulative.Plans,
      Amber: cumulative.Amber,
      SvS: cumulative.SvS,
    });
  }

  return table;
}
