import { PACKS } from './defaults.js';

// ── Advanced mode ─────────────────────────────────────────────────────────
let advancedMode = true;

export function toggleAdvancedMode() {
  advancedMode = !advancedMode;
  document.getElementById('advToggle').classList.toggle('on', advancedMode);
  document.getElementById('simpleBudget').style.display = advancedMode ? 'none' : '';
  document.getElementById('advSections').style.display  = advancedMode ? '' : 'none';
  if (advancedMode) { buildPacksTable(); updateGems(); }
}

export function isAdvancedMode() {
  return advancedMode;
}

export function buildPacksTable() {
  const days = parseInt(document.getElementById('days').value) || 1;
  const head = document.getElementById('packsHead');
  const body = document.getElementById('packsBody');

  let hRow = '<tr><th>Pack</th><th>💎</th>';
  for (let d = 1; d <= days; d++) hRow += `<th>D${d}</th>`;
  head.innerHTML = hRow + '</tr>';

  body.innerHTML = PACKS.map((p, pi) => {
    let row = `<tr><td>${p.label}</td><td>${p.gems}</td>`;
    for (let d = 0; d < days; d++) {
      row += `<td><input type="checkbox" id="pack_${pi}_${d}" onchange="onPackChange(${pi},${d})"></td>`;
    }
    return row + '</tr>';
  }).join('');
}

export function onPackChange(pi, d) {
  const checked = document.getElementById(`pack_${pi}_${d}`).checked;
  if (checked) {
    // also check every cheaper pack in the same day column
    for (let i = 0; i < pi; i++) {
      const cb = document.getElementById(`pack_${i}_${d}`);
      if (cb) cb.checked = true;
    }
  } else {
    // also uncheck every more expensive pack in the same day column
    for (let i = pi + 1; i < PACKS.length; i++) {
      const cb = document.getElementById(`pack_${i}_${d}`);
      if (cb) cb.checked = false;
    }
  }
  updateGems();
}

export function updateGems() {
  const days = parseInt(document.getElementById('days').value) || 1;
  const tomeOn = document.getElementById('tomeCb')?.checked ?? false;

  const tomeGems     = tomeOn ? 360 : 0;
  const missionsGems = tomeOn ? 1680 : 840;
  const drillGems    = tomeOn ? 600  : 240;

  let packGems = 0;
  PACKS.forEach((p, pi) => {
    for (let d = 0; d < days; d++) {
      if (document.getElementById(`pack_${pi}_${d}`)?.checked) packGems += p.gems;
    }
  });

  const total = tomeGems + packGems + missionsGems + drillGems;

  document.getElementById('missionsGems').textContent = missionsGems.toLocaleString();
  document.getElementById('drillGems').textContent    = drillGems.toLocaleString();
  document.getElementById('totalGemsDisplay').textContent = total.toLocaleString() + ' gems';

  // feed into the budget field that the simulation reads
  document.getElementById('budget').value = total;
}
