// Reward pools: each pool holds `count` identical items, each item drawn
// with weight `itemProb` (renormalized over whatever remains on the board).
// `itemProb` values here are only the defaults used to seed the editable
// sidebar table — the live values are read from the DOM at run time.
export const POOLS_CONFIG = [
  { key: 'pool1',      label: 'Pool 1',      count: 3, itemProb: 19.95 },
  { key: 'pool2',      label: 'Pool 2',      count: 2, itemProb: 7.67 },
  { key: 'pool3',      label: 'Pool 3',      count: 1, itemProb: 7.67 },
  { key: 'pool4',      label: 'Pool 4',      count: 1, itemProb: 9.21 },
  { key: 'pool5',      label: 'Pool 5',      count: 1, itemProb: 3.07 },
  { key: 'pool6',      label: 'Pool 6',      count: 1, itemProb: 3.07 },
  { key: 'grandPrize', label: 'Grand Prize', count: 1, itemProb: 1.79 },
];

export const ROUND_COSTS = [0, 1, 2, 3, 4, 6, 8, 12, 15, 20, 25]; // index 0 unused, rounds 1-10
export const RESET_COSTS = [0, 15, 14, 13, 10, 6, 5, 4, 3, 2, 1, 0]; // index 0 unused, rounds 1-11

export function getCumulativeCost(round) {
  let total = 0;
  for (let i = 1; i <= round; i++) total += ROUND_COSTS[i];
  return total;
}
