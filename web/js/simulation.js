import { makePRNG } from './prng.js';

// ── Simulation core ───────────────────────────────────────────────────────
export function normProbs(dist) {
  const total = dist.reduce((s, r) => s + r.prob, 0);
  return dist.map(r => r.prob / total);
}

function sampleBatch(dist, probs, count, rng) {
  let total = 0;
  for (let i = 0; i < count; i++) {
    const r = rng();
    let cum = 0;
    for (let j = 0; j < probs.length; j++) {
      cum += probs[j];
      if (r <= cum) { total += dist[j].roses; break; }
    }
  }
  return total;
}

function simOneRun(sid, pRed, pYellow, nChests, costOpen, costRefresh, budget,
                   redDist, redProbs, yellowDist, yellowProbs, grayDist, grayProbs,
                   days, freePerDay, rng, mOpens, mRoseRewards, mChestRewards) {
  let remaining = budget;
  let roses = 0;
  let gearChests = 0;
  let totalOpens = 0;
  let nextIdx = 0;
  const nm = mOpens.length;

  for (let day = 0; day < days; day++) {
    let freeLeft = freePerDay;
    const isLast = day === days - 1;

    while (true) {
      let refreshCost;
      if (freeLeft > 0)       refreshCost = 0;
      else if (isLast)        refreshCost = costRefresh;
      else                    break;

      if (refreshCost > 0 && remaining < refreshCost) break;
      if (freeLeft > 0) freeLeft--; else remaining -= refreshCost;

      let redCount = 0, yellowCount = 0;
      for (let i = 0; i < nChests; i++) {
        const r = rng();
        if (r < pRed) redCount++;
        else if (r < pRed + pYellow) yellowCount++;
      }
      const grayCount = nChests - redCount - yellowCount;

      let toRed, toYellow, toGray;
      if (sid === 1) {
        toRed = redCount; toYellow = 0; toGray = 0;
      } else if (sid === 2) {
        toRed = redCount; toYellow = yellowCount; toGray = 0;
      } else if (sid === 3) {
        toRed = redCount; toYellow = yellowCount; toGray = grayCount;
      } else {
        if (redCount + yellowCount >= 6) {
          toRed = redCount; toYellow = yellowCount; toGray = grayCount;
        } else {
          toRed = redCount; toYellow = 0; toGray = 0;
        }
      }

      const totalToOpen = toRed + toYellow + toGray;
      if (totalToOpen === 0) continue;

      const canOpen = Math.min(totalToOpen, Math.floor(remaining / costOpen));
      if (canOpen === 0) break;
      remaining -= canOpen * costOpen;

      let left = canOpen;
      const chests = [[toRed, redDist, redProbs], [toYellow, yellowDist, yellowProbs], [toGray, grayDist, grayProbs]];
      for (const [cnt, dist, probs] of chests) {
        if (left === 0) break;
        const n = Math.min(left, cnt);
        if (n > 0) { roses += sampleBatch(dist, probs, n, rng); left -= n; }
      }

      totalOpens += canOpen;
      while (nextIdx < nm && totalOpens >= mOpens[nextIdx]) {
        roses      += mRoseRewards[nextIdx];
        gearChests += mChestRewards[nextIdx];
        nextIdx++;
      }
      if (canOpen < totalToOpen) break;
    }
  }
  return {roses, opens: totalOpens, gearChests};
}

export function runStrategy(N, sid, pRed, pYellow, nChests, costOpen, costRefresh, budget,
                     redDist, yellowDist, grayDist, days, freePerDay, seed,
                     mOpens, mRoseRewards, mChestRewards) {
  const rng = makePRNG(seed);
  const redProbs    = normProbs(redDist);
  const yellowProbs = normProbs(yellowDist);
  const grayProbs   = normProbs(grayDist);
  const roses      = new Int32Array(N);
  const opens      = new Int32Array(N);
  const gearChests = new Int32Array(N);
  for (let i = 0; i < N; i++) {
    const r = simOneRun(sid, pRed, pYellow, nChests, costOpen, costRefresh, budget,
                        redDist, redProbs, yellowDist, yellowProbs, grayDist, grayProbs,
                        days, freePerDay, rng, mOpens, mRoseRewards, mChestRewards);
    roses[i]      = r.roses;
    opens[i]      = r.opens;
    gearChests[i] = r.gearChests;
  }
  return {roses, opens, gearChests};
}
