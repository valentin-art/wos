import { ROUND_COSTS, RESET_COSTS } from './constants.js';

class GameState {
  constructor(poolsConfig) {
    this.poolsConfig = poolsConfig;
    this.reset();
  }

  reset() {
    this.pools = {};
    for (const p of this.poolsConfig) {
      this.pools[p.key] = { count: p.count, itemProb: p.itemProb };
    }
    this.totalItems = Object.values(this.pools).reduce((sum, pool) => sum + pool.count, 0);
    this.round = 1;
    this.grandPrizeWon = false;
  }

  drawItem(rng) {
    if (this.totalItems === 0 || this.grandPrizeWon) return null;

    const currentProbs = this.getCurrentProbabilities();
    const rand = rng() * 100;
    let cumulative = 0;

    for (const [key, pool] of Object.entries(this.pools)) {
      if (pool.count > 0) {
        cumulative += currentProbs[key];
        if (rand <= cumulative) {
          pool.count--;
          this.totalItems--;

          if (key === 'grandPrize') this.grandPrizeWon = true;

          this.round++;
          return key;
        }
      }
    }
    return null;
  }

  getCurrentProbabilities() {
    const probs = {};
    let totalRemainingProb = 0;

    for (const [key, pool] of Object.entries(this.pools)) {
      if (pool.count > 0) {
        probs[key] = pool.itemProb * pool.count;
        totalRemainingProb += probs[key];
      } else {
        probs[key] = 0;
      }
    }

    if (totalRemainingProb > 0) {
      for (const key in probs) probs[key] = (probs[key] / totalRemainingProb) * 100;
    }

    return probs;
  }
}

export function simulateFarmingStrategy(poolsConfig, resetRound, budget, numSimulations, rng, milestones = [], prizeThreshold = 0) {
  let totalGrandPrizes = 0;
  let totalBudgetUsed = 0;
  let totalMilestoneTickets = 0;
  let countAboveThreshold = 0;
  const costPerPrize = [];

  const mWishes = milestones.map(m => m.wishes);
  const mGrants = milestones.map(m => m.ticketGrant);
  const nm = mWishes.length;

  for (let sim = 0; sim < numSimulations; sim++) {
    const game = new GameState(poolsConfig);
    let remainingBudget = budget;
    let grandPrizesThisSim = 0;
    let budgetUsed = 0;
    let sessionCount = 0;
    let cumulativeWishes = 0; // persists across board resets within this trial
    let nextMilestoneIdx = 0;
    let milestoneTicketsThisSim = 0;

    while (remainingBudget > 0 && sessionCount < 1000) { // safety limit
      sessionCount++;
      let roundsPlayed = 0;
      let sessionCost = 0;

      if (remainingBudget < ROUND_COSTS[game.round]) break; // can't afford the next round

      while (roundsPlayed < resetRound &&
             game.round <= 10 &&
             !game.grandPrizeWon &&
             game.pools.grandPrize.count > 0) {

        const nextRoundCost = ROUND_COSTS[game.round];
        if (remainingBudget < nextRoundCost) break;

        const item = game.drawItem(rng);
        if (item === null) break;

        cumulativeWishes++; // one wish = one opened orb
        while (nextMilestoneIdx < nm && cumulativeWishes >= mWishes[nextMilestoneIdx]) {
          remainingBudget += mGrants[nextMilestoneIdx];
          milestoneTicketsThisSim += mGrants[nextMilestoneIdx];
          nextMilestoneIdx++;
        }

        const currentRoundCost = ROUND_COSTS[game.round - 1]; // cost of round just played
        sessionCost += currentRoundCost;
        remainingBudget -= currentRoundCost;
        budgetUsed += currentRoundCost;
        roundsPlayed++;

        if (item === 'grandPrize') {
          grandPrizesThisSim++;
          costPerPrize.push(sessionCost);
          game.reset(); // grand prize won - free reset
          sessionCost = 0;
          break;
        }
      }

      if (!game.grandPrizeWon && remainingBudget > 0 && game.pools.grandPrize.count > 0) {
        const resetCost = RESET_COSTS[Math.min(game.round, 11)];
        if (remainingBudget >= resetCost) {
          remainingBudget -= resetCost;
          budgetUsed += resetCost;
          sessionCost += resetCost;
          game.reset();
        } else {
          break; // not enough budget to reset
        }
      } else if (game.pools.grandPrize.count === 0 || game.round > 10) {
        game.reset(); // board exhausted, reset for free
        sessionCost = 0;
      }

      if (remainingBudget <= 0) break;
    }

    totalGrandPrizes += grandPrizesThisSim;
    totalBudgetUsed += budgetUsed;
    totalMilestoneTickets += milestoneTicketsThisSim;
    if (grandPrizesThisSim > prizeThreshold) countAboveThreshold++;
  }

  const avgGrandPrizes = totalGrandPrizes / numSimulations;
  const avgBudgetUsed = totalBudgetUsed / numSimulations;
  const efficiency = avgGrandPrizes / budget; // prizes per nominal starting token
  const avgCostPerPrize = costPerPrize.length > 0
    ? costPerPrize.reduce((a, b) => a + b, 0) / costPerPrize.length
    : 0;
  const budgetUtilization = (avgBudgetUsed / budget) * 100; // can exceed 100% once milestone tickets extend a run
  const avgMilestoneTickets = totalMilestoneTickets / numSimulations;
  const probAboveThreshold = countAboveThreshold / numSimulations;

  return { resetRound, avgGrandPrizes, efficiency, avgCostPerPrize, budgetUtilization, avgBudgetUsed, avgMilestoneTickets, probAboveThreshold };
}
