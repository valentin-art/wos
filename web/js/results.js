import { randomSeed } from './prng.js';
import { STRATEGIES } from './defaults.js';
import { readTable, readMilestoneTable } from './table-helpers.js';
import { runStrategy } from './simulation.js';

// ── Main runner ───────────────────────────────────────────────────────────
let charts = {};

export function setProgress(done, total, label) {
  const wrap = document.getElementById('progressWrap');
  wrap.classList.add('visible');
  document.getElementById('progressLabel').textContent = label;
  document.getElementById('progressFill').style.width = `${(done / total) * 100}%`;
  if (done >= total) setTimeout(() => wrap.classList.remove('visible'), 600);
}

export async function runSimulation() {
  const pRed       = parseFloat(document.getElementById('pRed').value);
  const pYellow    = parseFloat(document.getElementById('pYellow').value);
  const nChests    = parseInt(document.getElementById('nChests').value);
  const costOpen   = parseInt(document.getElementById('costOpen').value);
  const costRefresh = parseInt(document.getElementById('costRefresh').value);
  const budget     = parseInt(document.getElementById('budget').value);
  const days       = parseInt(document.getElementById('days').value);
  const freePerDay = parseInt(document.getElementById('freePerDay').value);
  const N          = parseInt(document.getElementById('nRuns').value);
  const threshold  = parseInt(document.getElementById('threshold').value);
  const histStep   = parseInt(document.getElementById('histStep').value);
  const seedInput  = parseInt(document.getElementById('seed').value);
  const seed       = seedInput === 0 ? randomSeed() : seedInput;

  const redDist    = readTable('red',    'roses', 'prob');
  const yellowDist = readTable('yellow', 'roses', 'prob');
  const grayDist   = readTable('gray',   'roses', 'prob');
  const mRaw   = readMilestoneTable().sort((a, b) => a.opens - b.opens);
  const mOpens        = mRaw.map(m => m.opens);
  const mRoseRewards  = mRaw.map(m => m.roses);
  const mChestRewards = mRaw.map(m => m.chests);
  const optMode = document.querySelector('input[name="optMode"]:checked').value;

  if (!redDist.length || !yellowDist.length || !grayDist.length) {
    alert('Please fill in all three chest distributions before running.');
    return;
  }

  const runBtn = document.getElementById('runBtn');
  const resultsEl = document.getElementById('results');
  runBtn.disabled = true;
  resultsEl.innerHTML = '';

  Object.values(charts).forEach(c => c.destroy());
  charts = {};

  try {

  const allResults = {};
  for (let i = 0; i < STRATEGIES.length; i++) {
    const s = STRATEGIES[i];
    setProgress(i, STRATEGIES.length, `Running strategy ${i + 1}/${STRATEGIES.length}…`);
    await new Promise(r => setTimeout(r, 0));
    allResults[s.id] = runStrategy(N, s.id, pRed, pYellow, nChests, costOpen, costRefresh, budget,
                                   redDist, yellowDist, grayDist, days, freePerDay, seed,
                                   mOpens, mRoseRewards, mChestRewards);
  }
  setProgress(STRATEGIES.length, STRATEGIES.length, 'Done');

  const summary = STRATEGIES.map(s => {
    const {roses, opens, gearChests} = allResults[s.id];
    // mean = avg roses (includes rose milestones, excludes chest milestones)
    const mean       = roses.reduce((a, b) => a + b, 0) / N;
    const meanChests = gearChests.reduce((a, b) => a + b, 0) / N;
    // combined = roses + gearChests*10 (used as objective in "chests" mode)
    const meanCombined = mean + meanChests * 10;
    const above      = roses.filter(v => v > threshold).length;
    const prob       = above / N;
    const std        = Math.sqrt(roses.reduce((a, b) => a + (b - mean) ** 2, 0) / N);
    const median     = [...roses].sort((a, b) => a - b)[Math.floor(N / 2)];
    const meanOpens  = opens.reduce((a, b) => a + b, 0) / N;
    return {...s, roses, opens, gearChests, above, prob, mean, std, median, meanOpens, meanChests, meanCombined};
  });

  // Roses mode: maximize avg roses. Chests mode: maximize roses + gearChests*10.
  const rosesMode = optMode === 'roses';
  const winner = rosesMode
    ? summary.reduce((best, s) => s.mean > best.mean ? s : best)
    : summary.reduce((best, s) => s.meanCombined > best.meanCombined ? s : best);

  renderResults(summary, winner, threshold, histStep, mRaw, N, optMode);
  runBtn.disabled = false;
  } catch(e) {
    resultsEl.innerHTML = `<div style="color:#ff6b6b;padding:16px;border:1px solid #ff6b6b;margin-top:16px">
      <strong>Error:</strong> ${e.message}<br><pre style="font-size:11px;margin-top:8px;white-space:pre-wrap">${e.stack}</pre>
    </div>`;
    runBtn.disabled = false;
    throw e;
  }
}

function pct(arr, p) {
  const sorted = [...arr].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length * p / 100)];
}

function renderResults(summary, winner, threshold, histStep, milestones, N, optMode) {
  const el = document.getElementById('results');
  const rosesMode = optMode === 'roses';

  const milestoneHTML = milestones.length ? `
    <h2>Milestone reach rates — ${winner.name}</h2>
    <div class="milestone-row">
      ${milestones.map(m => {
        const rate = winner.opens.filter(o => o >= m.opens).length / N;
        const rewardStr = m.roses > 0
          ? `+${m.roses} roses`
          : `+${m.chests} gear chests`;
        return `<div class="milestone-box">
          <div class="milestone-label">≥${m.opens} opens</div>
          <div class="milestone-rate">${(rate * 100).toFixed(1)}%</div>
          <div class="milestone-delta">${rewardStr}</div>
        </div>`;
      }).join('')}
    </div>` : '';

  const tabBtns = summary.map((s, i) =>
    `<button class="tab-btn${i === 0 ? ' active' : ''}" onclick="switchTab(${i})" id="tabBtn${i}">${s.name}</button>`
  ).join('');

  const tabPanes = summary.map((s, i) => {
    const isWinner = s.id === winner.id;
    const pcts = [10, 25, 50, 75, 90, 95].map(p => ({p, v: pct(s.roses, p)}));
    const primaryBox = rosesMode
      ? `<div class="metric-box">
           <div class="metric-label">Avg roses</div>
           <div class="metric-value">${Math.floor(s.mean)} <span style="color:var(--muted);font-size:16px">+ ${Math.floor(s.meanChests)}</span></div>
           <div style="color:var(--muted);font-size:11px;margin-top:4px;letter-spacing:0.06em">roses + milestone chests</div>
         </div>`
      : `<div class="metric-box">
           <div class="metric-label">Avg chests ~ roses</div>
           <div class="metric-value">${Math.floor(s.meanCombined / 10)} <span style="color:var(--muted);font-size:16px">~ ${Math.floor(s.meanCombined)}</span></div>
           <div style="color:var(--muted);font-size:11px;margin-top:4px;letter-spacing:0.06em">chests ~ rose-equivalent</div>
         </div>`;
    return `<div class="tab-pane${i === 0 ? ' active' : ''}" id="tabPane${i}">
      ${isWinner ? `<div class="success-banner">🏆 This is the best strategy for the current settings</div>` : ''}
      <div class="metrics-row">
        ${primaryBox}
        <div class="metric-box"><div class="metric-label">Median roses</div><div class="metric-value">${s.median}</div></div>
        <div class="metric-box"><div class="metric-label">Std dev (σ)</div><div class="metric-value">${s.std.toFixed(1)}</div></div>
      </div>
      <div class="pct-row">
        <div class="pct-box"><div class="pct-label">Min</div><div class="pct-value">${Math.min(...s.roses)}</div></div>
        ${pcts.map(({p, v}) => `<div class="pct-box"><div class="pct-label">P${p}</div><div class="pct-value">${v}</div></div>`).join('')}
        <div class="pct-box"><div class="pct-label">Max</div><div class="pct-value">${Math.max(...s.roses)}</div></div>
      </div>
      <div class="chart-wrap"><canvas id="chart-${s.id}"></canvas></div>
    </div>`;
  }).join('');

  const winnerCard = rosesMode
    ? { eyebrow: 'Best Strategy — Roses',
        big: `${Math.floor(winner.mean)} + ${Math.floor(winner.meanChests)}`,
        sub1: `avg roses + avg milestone chests`,
        sub2: `P(roses &gt; ${threshold}) = <strong style="color:${winner.color}">${(winner.prob * 100).toFixed(2)}%</strong> · median ${winner.median}` }
    : { eyebrow: 'Best Strategy — Chests',
        big: `${Math.floor(winner.meanCombined / 10)} ~ ${Math.floor(winner.meanCombined)}`,
        sub1: `avg chests ~ avg rose-equivalent`,
        sub2: `avg roses ${Math.floor(winner.mean)} · ${Math.floor(winner.meanChests)} milestone chests · median ${winner.median}` };

  el.innerHTML = `
    <hr>
    <div class="winner-card">
      <div class="corner tl"></div><div class="corner tr"></div>
      <div class="corner bl"></div><div class="corner br"></div>
      <div class="winner-eyebrow">${winnerCard.eyebrow}</div>
      <div class="winner-name" style="color:${winner.color}">${winner.name}</div>
      <div class="winner-pct" style="color:${winner.color};text-shadow:0 0 24px ${winner.color}88">${winnerCard.big}</div>
      <div class="winner-sub" style="margin-bottom:6px">${winnerCard.sub1}</div>
      <div class="winner-sub">${winnerCard.sub2}</div>
    </div>

    <h2>All strategies</h2>
    <div class="results-table-wrap">
      <table class="results-table">
        <thead>
          <tr>
            <th>Strategy</th>
            ${rosesMode
              ? `<th>Avg roses</th><th>Milestone chests</th>`
              : `<th>Avg chests</th><th>= Avg roses</th>`}
            <th>P(&gt;${threshold})</th>
            <th>Median roses</th>
            <th>Avg opens</th>
          </tr>
        </thead>
        <tbody>
          ${summary.map(s => `
            <tr class="${s.id === winner.id ? 'winner-row' : ''}">
              <td>${s.name}</td>
              ${rosesMode
                ? `<td>${Math.floor(s.mean)}</td><td>${Math.floor(s.meanChests)}</td>`
                : `<td>${Math.floor(s.meanCombined / 10)}</td><td>${Math.floor(s.meanCombined)}</td>`}
              <td>${(s.prob * 100).toFixed(2)}%</td>
              <td>${s.median}</td>
              <td>${s.meanOpens.toFixed(1)}</td>
            </tr>`).join('')}
        </tbody>
      </table>
    </div>

    ${milestoneHTML}

    <h2>Detail by strategy</h2>
    <div class="tabs">
      <div class="tab-buttons">${tabBtns}</div>
      ${tabPanes}
    </div>
  `;

  // Draw histograms after DOM is updated
  summary.forEach(s => drawHistogram(s, histStep));
}

export function switchTab(idx) {
  document.querySelectorAll('.tab-btn').forEach((b, i) => b.classList.toggle('active', i === idx));
  document.querySelectorAll('.tab-pane').forEach((p, i) => p.classList.toggle('active', i === idx));
  // Redraw chart if needed (canvas may have been hidden)
  const s = STRATEGIES[idx];
  if (charts[s.id]) charts[s.id].update();
}

function drawHistogram(s, step) {
  const canvas = document.getElementById(`chart-${s.id}`);
  if (!canvas) return;

  const buckets = {};
  s.roses.forEach(v => {
    const b = Math.floor(v / step) * step;
    buckets[b] = (buckets[b] || 0) + 1;
  });
  const keys = Object.keys(buckets).map(Number).sort((a, b) => a - b);

  charts[s.id] = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: keys.map(k => k.toString()),
      datasets: [{
        data: keys.map(k => buckets[k]),
        backgroundColor: s.color + 'bb',
        borderColor: s.color,
        borderWidth: 1,
        borderRadius: 3,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {legend: {display: false}},
      scales: {
        x: {ticks: {color: '#A9B4C2', font: {family:'Rajdhani'}, maxRotation: 0}, grid: {color: 'rgba(27,107,133,0.15)'}},
        y: {ticks: {color: '#A9B4C2', font: {family:'Rajdhani'}}, grid: {color: 'rgba(27,107,133,0.15)'}},
      },
    }
  });
}
