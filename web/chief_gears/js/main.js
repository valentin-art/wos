import { GEAR_NAMES, RESOURCE_KEYS, DEFAULT_RESOURCES } from './constants.js';
import { upgradeChiefGears } from './optimizer.js';

let gearRows = [];

function populateTierSelects() {
  const tiers = gearRows.map(r => r.tier);
  GEAR_NAMES.forEach(name => {
    const select = document.getElementById(`tier_${name}`);
    select.innerHTML = tiers.map(t => `<option value="${t}">${t}</option>`).join('');
  });
}

function populateResourceInputs() {
  RESOURCE_KEYS.forEach(key => {
    document.getElementById(`res_${key}`).value = DEFAULT_RESOURCES[key] ?? 0;
  });
}

function readResources() {
  const resources = {};
  RESOURCE_KEYS.forEach(key => {
    resources[key] = parseInt(document.getElementById(`res_${key}`).value) || 0;
  });
  return resources;
}

function readGearSpecs() {
  return GEAR_NAMES.map(name => ({
    name,
    currentTier: document.getElementById(`tier_${name}`).value,
  }));
}

function renderResults({ upgradeTable, cost, remaining, score }, resources) {
  const el = document.getElementById('results');

  const upgradeRows = upgradeTable.map(row => `
    <tr>
      <td>${row.gear}</td>
      <td>${row.oldTier}</td>
      <td>${row.newTier}</td>
    </tr>`).join('');

  const resourceRows = RESOURCE_KEYS.map(key => `
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
        <thead><tr><th>Gear</th><th>Old tier</th><th>New tier</th></tr></thead>
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
    const gearSpecs = readGearSpecs();
    const result = upgradeChiefGears(gearSpecs, gearRows, resources);
    renderResults(result, resources);
  } finally {
    btn.disabled = false;
  }
}

window.calculateUpgrades = calculateUpgrades;

document.addEventListener('DOMContentLoaded', async () => {
  const res = await fetch('/chief_gears/data/gears.json');
  gearRows = await res.json();
  populateTierSelects();
  populateResourceInputs();
});
