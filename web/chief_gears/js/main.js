import { GEAR_NAMES, DISPLAY_ORDER, RESOURCE_KEYS, DEFAULT_RESOURCES } from './constants.js';
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

  const byName = Object.fromEntries(upgradeTable.map(row => [row.gear, row]));
  const pairs = [];
  for (let i = 0; i < DISPLAY_ORDER.length; i += 2) {
    pairs.push([DISPLAY_ORDER[i], DISPLAY_ORDER[i + 1]]);
  }

  const upgradeRows = pairs.map(([leftName, rightName]) => {
    const left = byName[leftName];
    const right = byName[rightName];
    return `
    <tr>
      <td class="gear-name">${leftName}</td>
      <td>${left.oldTier}</td>
      <td><strong>${left.newTier}</strong></td>
      <td class="col-gap"></td>
      <td class="gear-name">${rightName}</td>
      <td>${right.oldTier}</td>
      <td><strong>${right.newTier}</strong></td>
    </tr>`;
  }).join('');

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
      <table class="results-table upgrade-pair-table">
        <thead>
          <tr>
            <th></th><th>Old Tier</th><th>New Tier</th>
            <th class="col-gap"></th>
            <th></th><th>Old Tier</th><th>New Tier</th>
          </tr>
        </thead>
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
  const res = await fetch('/chief_gears/svs_map/gears.json');
  gearRows = await res.json();
  populateTierSelects();
  populateResourceInputs();
});
