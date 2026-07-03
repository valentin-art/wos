import { GEAR_NAMES, N_CHARMS, CHARM_RESOURCE_KEYS, DEFAULT_RESOURCES, DEFAULT_LEVEL } from './constants.js';
import { upgradeCharms } from './optimizer.js';

let charmRows = [];

function populateLevelSelects() {
  const levels = charmRows.map(r => r.level);
  const defaultIndex = levels.includes(DEFAULT_LEVEL) ? levels.indexOf(DEFAULT_LEVEL) : 0;
  GEAR_NAMES.forEach(name => {
    for (let j = 0; j < N_CHARMS; j++) {
      const select = document.getElementById(`level_${name}_${j}`);
      select.innerHTML = levels.map(l => `<option value="${l}">${l}</option>`).join('');
      select.selectedIndex = defaultIndex;
    }
  });
}

function populateResourceInputs() {
  CHARM_RESOURCE_KEYS.forEach(key => {
    document.getElementById(`res_${key}`).value = DEFAULT_RESOURCES[key] ?? 0;
  });
}

function readResources() {
  const resources = {};
  CHARM_RESOURCE_KEYS.forEach(key => {
    resources[key] = parseInt(document.getElementById(`res_${key}`).value) || 0;
  });
  return resources;
}

function readCharmSpecs() {
  return GEAR_NAMES.map(name => ({
    name,
    currentLevels: Array.from({ length: N_CHARMS }, (_, j) =>
      parseFloat(document.getElementById(`level_${name}_${j}`).value)
    ),
  }));
}

function renderResults({ upgradeTable, cost, remaining, score }, resources) {
  const el = document.getElementById('results');

  const upgradeRows = upgradeTable.map(row => `
    <tr>
      <td>${row.charm}</td>
      <td>${row.oldLevels.join(', ')}</td>
      <td>${row.newLevels.join(', ')}</td>
    </tr>`).join('');

  const resourceRows = CHARM_RESOURCE_KEYS.map(key => `
    <tr>
      <td>${key}</td>
      <td>${resources[key].toLocaleString()}</td>
      <td>${cost[key].toLocaleString()}</td>
      <td>${remaining[key].toLocaleString()}</td>
    </tr>`).join('');

  el.innerHTML = `
    <div class="metrics-row">
      <div class="metric-box">
        <div class="metric-label">Total SvS score</div>
        <div class="metric-value">${Math.floor(score).toLocaleString()}</div>
      </div>
    </div>

    <h2>Upgrades</h2>
    <div class="results-table-wrap">
      <table class="results-table">
        <thead><tr><th>Type</th><th>Old levels</th><th>New levels</th></tr></thead>
        <tbody>${upgradeRows}</tbody>
      </table>
    </div>

    <h2>Used / rest resources</h2>
    <div class="results-table-wrap">
      <table class="results-table">
        <thead><tr><th>Resource</th><th>Available</th><th>Used</th><th>Rest</th></tr></thead>
        <tbody>${resourceRows}</tbody>
      </table>
    </div>
  `;
}

async function calculateUpgrades() {
  const btn = document.getElementById('calcBtn');
  btn.disabled = true;
  try {
    const resources = readResources();
    const charmSpecs = readCharmSpecs();
    const result = upgradeCharms(charmSpecs, charmRows, resources);
    renderResults(result, resources);
  } finally {
    btn.disabled = false;
  }
}

window.calculateUpgrades = calculateUpgrades;

document.addEventListener('DOMContentLoaded', async () => {
  const res = await fetch('/charms/data/charms.json');
  charmRows = await res.json();
  populateLevelSelects();
  populateResourceInputs();
});
