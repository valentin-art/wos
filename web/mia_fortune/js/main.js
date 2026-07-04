import { POOLS_CONFIG, getCumulativeCost } from './constants.js';
import { simulateFarmingStrategy } from './simulation.js';
import { makePRNG, randomSeed } from './prng.js';
import { MILESTONES } from './defaults.js';
import {
  toggleAdvancedMode,
  buildPacksTable,
  onPackChange,
  updateTicketTotal,
  populateMilestoneTable,
} from './advanced-mode.js';

let chart = null;

function setProgress(done, total, label) {
  const wrap = document.getElementById('progressWrap');
  wrap.classList.add('visible');
  document.getElementById('progressLabel').textContent = label;
  document.getElementById('progressFill').style.width = `${(done / total) * 100}%`;
  if (done >= total) setTimeout(() => wrap.classList.remove('visible'), 600);
}

function readPools() {
  return POOLS_CONFIG.map(p => ({
    key: p.key,
    count: p.count,
    itemProb: parseFloat(document.getElementById(`prob_${p.key}`).value) || 0,
  }));
}

function toggleUnifiedWeights() {
  const unified = document.getElementById('unifiedWeights').checked;
  POOLS_CONFIG.forEach(p => {
    const input = document.getElementById(`prob_${p.key}`);
    if (unified) {
      input.value = 10;
      input.disabled = true;
    } else {
      input.disabled = false;
    }
  });
}

async function runFarmingAnalysis() {
  const budget = parseInt(document.getElementById('budget').value);
  const numSims = parseInt(document.getElementById('simulations').value);
  const seedInput = parseInt(document.getElementById('seed').value);
  const seed = seedInput === 0 ? randomSeed() : seedInput;
  const prizeThreshold = parseInt(document.getElementById('prizeThreshold').value) || 0;
  const pools = readPools();

  const runBtn = document.getElementById('runAnalysis');
  runBtn.disabled = true;

  const results = [];

  for (let round = 1; round <= 10; round++) {
    setProgress(round - 1, 10, `Testing reset at round ${round}/10…`);
    await new Promise(resolve => setTimeout(resolve, 0));

    const cumulativeCost = getCumulativeCost(round);
    if (budget < cumulativeCost) {
      results.push({
        resetRound: round,
        avgGrandPrizes: 0,
        efficiency: 0,
        avgCostPerPrize: 0,
        budgetUtilization: 0,
        avgBudgetUsed: 0,
        avgMilestoneTickets: 0,
        probAboveThreshold: 0,
        impossible: true,
      });
    } else {
      results.push(simulateFarmingStrategy(pools, round, budget, numSims, makePRNG(seed), MILESTONES, prizeThreshold));
    }
  }
  setProgress(10, 10, 'Done');

  renderResults(results, budget, prizeThreshold);
  runBtn.disabled = false;
}

function renderResults(results, budget, prizeThreshold) {
  const el = document.getElementById('results');
  const possible = results.filter(r => !r.impossible);
  const best = possible.reduce((a, b) => (b.avgGrandPrizes > a.avgGrandPrizes ? b : a));

  const leftover = budget - best.avgBudgetUsed;
  const roi = best.avgBudgetUsed > 0 ? (best.avgGrandPrizes * 100) / best.avgBudgetUsed : 0;

  el.innerHTML = `
    <hr>
    <div class="winner-card">
      <div class="corner tl"></div><div class="corner tr"></div>
      <div class="corner bl"></div><div class="corner br"></div>
      <div class="winner-eyebrow">Optimal Farming Strategy</div>
      <div class="winner-name">Reset after round ${best.resetRound}</div>
      <div class="winner-split">
        <div class="winner-split-item">
          <div class="winner-split-label">Expected grand prizes</div>
          <div class="winner-split-value">${Math.floor(best.avgGrandPrizes)}</div>
        </div>
        <div class="winner-split-item">
          <div class="winner-split-label">P(&gt; ${prizeThreshold} grand prizes)</div>
          <div class="winner-split-value">${(best.probAboveThreshold * 100).toFixed(1)}%</div>
        </div>
      </div>
      <div class="winner-sub" style="margin-bottom:6px">expected grand prizes per ${budget}-token budget</div>
      <div class="winner-sub">efficiency ${best.efficiency.toFixed(4)}/token · ${best.budgetUtilization.toFixed(1)}% budget used</div>
    </div>

    <h2>Cost breakdown — best strategy</h2>
    <div class="metrics-row">
      <div class="metric-box"><div class="metric-label">Cost per prize</div><div class="metric-value">${best.avgCostPerPrize.toFixed(1)}</div></div>
      <div class="metric-box"><div class="metric-label">Avg budget used</div><div class="metric-value">${best.avgBudgetUsed.toFixed(1)}</div></div>
      <div class="metric-box"><div class="metric-label">Avg leftover</div><div class="metric-value">${leftover.toFixed(1)}</div></div>
      <div class="metric-box"><div class="metric-label">ROI (prize = 1 token)</div><div class="metric-value">${roi.toFixed(1)}%</div></div>
      <div class="metric-box"><div class="metric-label">Avg milestone tickets</div><div class="metric-value">${best.avgMilestoneTickets.toFixed(1)}</div></div>
    </div>

    <h2>Grand prizes by reset strategy</h2>
    <div class="chart-wrap"><canvas id="chart-farming"></canvas></div>

    <h2>Detailed strategy analysis</h2>
    <div class="results-table-wrap">
      <table class="results-table">
        <thead>
          <tr>
            <th>Reset round</th>
            <th>Avg grand prizes</th>
            <th>Efficiency (per token)</th>
            <th>Avg cost per prize</th>
            <th>Budget utilization</th>
            <th>Expected profit margin</th>
          </tr>
        </thead>
        <tbody>
          ${results.map(r => `
            <tr class="${r.resetRound === best.resetRound ? 'winner-row' : ''} ${r.impossible ? 'impossible-row' : ''}">
              <td>${r.resetRound}</td>
              <td>${r.impossible ? `IMPOSSIBLE (needs ${getCumulativeCost(r.resetRound)} tokens)` : Math.floor(r.avgGrandPrizes)}</td>
              <td>${r.impossible ? '—' : r.efficiency.toFixed(4)}</td>
              <td>${r.impossible ? '—' : r.avgCostPerPrize.toFixed(1)}</td>
              <td>${r.impossible ? '—' : r.budgetUtilization.toFixed(1) + '%'}</td>
              <td>${r.impossible ? '—' : (((r.avgGrandPrizes * 10) - r.avgBudgetUsed) / r.avgBudgetUsed * 100).toFixed(1) + '%'}</td>
            </tr>`).join('')}
        </tbody>
      </table>
    </div>
  `;

  drawChart(results, best);
}

function drawChart(results, best) {
  const canvas = document.getElementById('chart-farming');
  if (!canvas) return;
  if (chart) chart.destroy();

  chart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: results.map(r => `R${r.resetRound}`),
      datasets: [{
        data: results.map(r => r.avgGrandPrizes),
        backgroundColor: results.map(r =>
          r.impossible ? 'rgba(169,180,194,0.15)' :
          r.resetRound === best.resetRound ? '#27D3FF' : 'rgba(39,211,255,0.35)'
        ),
        borderColor: results.map(r =>
          r.impossible ? '#A9B4C2' : r.resetRound === best.resetRound ? '#27D3FF' : '#1B6B85'
        ),
        borderWidth: 1,
        borderRadius: 3,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#A9B4C2', font: { family: 'Rajdhani' } }, grid: { color: 'rgba(27,107,133,0.15)' } },
        y: { ticks: { color: '#A9B4C2', font: { family: 'Rajdhani' } }, grid: { color: 'rgba(27,107,133,0.15)' } },
      },
    },
  });
}

window.runFarmingAnalysis = runFarmingAnalysis;
window.toggleAdvancedMode = toggleAdvancedMode;
window.onPackChange = onPackChange;
window.updateTicketTotal = updateTicketTotal;
window.toggleUnifiedWeights = toggleUnifiedWeights;

document.addEventListener('DOMContentLoaded', () => {
  populateMilestoneTable();
  document.getElementById('advToggle').classList.add('on'); // advanced mode defaults ON
  buildPacksTable();
  updateTicketTotal();
  toggleUnifiedWeights(); // uniform weights defaults ON
});
