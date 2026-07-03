import { DEFAULTS } from './defaults.js';

// ── Editable table helpers ────────────────────────────────────────────────
function makeFixedRow(tbody, cells) {
  const tr = document.createElement('tr');
  cells.forEach(({value, step}) => {
    const td = document.createElement('td');
    const inp = document.createElement('input');
    inp.type = 'number';
    inp.value = value ?? '';
    inp.step = step ?? 1;
    inp.addEventListener('input', updateDistStats);
    td.appendChild(inp);
    tr.appendChild(td);
  });
  tbody.appendChild(tr);
}

export function populateFixedTable(id, rows) {
  const tbody = document.querySelector(`#table-${id} tbody`);
  tbody.innerHTML = '';
  rows.forEach(r => makeFixedRow(tbody, [{value: r.roses, step: 1}, {value: r.prob, step: 0.001}]));
}

export function populateFixedMilestoneTable() {
  const tbody = document.querySelector('#table-milestones tbody');
  tbody.innerHTML = '';
  DEFAULTS.milestones.forEach(m => {
    const tr = document.createElement('tr');

    // Opens (read-only)
    const tdO = document.createElement('td');
    tdO.innerHTML = `<input type="number" value="${m.opens}" step="1" readonly style="color:var(--muted);cursor:default">`;
    tr.appendChild(tdO);

    // Roses — show "–" when no rose reward, otherwise read-only number
    const tdR = document.createElement('td');
    if (m.roses === 0) {
      tdR.innerHTML = `<input type="text" value="–" readonly style="color:var(--muted);cursor:default;text-align:center">`;
    } else {
      const inp = document.createElement('input');
      inp.type = 'number'; inp.value = m.roses; inp.readOnly = true;
      inp.style.cursor = 'default';
      tdR.appendChild(inp);
    }
    tr.appendChild(tdR);

    // Gear chests — show "–" when 0, otherwise read-only number
    const tdC = document.createElement('td');
    if (m.chests === 0) {
      tdC.innerHTML = `<input type="text" value="–" readonly style="color:var(--muted);cursor:default;text-align:center">`;
    } else {
      const inp = document.createElement('input');
      inp.type = 'number'; inp.value = m.chests; inp.readOnly = true;
      inp.style.color = 'var(--accent)'; inp.style.cursor = 'default';
      tdC.appendChild(inp);
    }
    tr.appendChild(tdC);

    tbody.appendChild(tr);
  });
}

export function readMilestoneTable() {
  const rows = [];
  document.querySelectorAll('#table-milestones tbody tr').forEach((tr, i) => {
    const inputs = tr.querySelectorAll('input');
    const opens  = parseFloat(inputs[0].value);
    const roses  = parseFloat(inputs[1].value) || 0;   // "–" parses as NaN → 0
    const chests = parseFloat(inputs[2].value) || 0;
    if (!isNaN(opens)) rows.push({opens, roses, chests});
  });
  return rows;
}

function makeRow(tbody, cells) {
  const tr = document.createElement('tr');
  cells.forEach(({value, step, placeholder}) => {
    const td = document.createElement('td');
    const inp = document.createElement('input');
    inp.type = 'number';
    inp.value = value ?? '';
    inp.step = step ?? 1;
    if (placeholder) inp.placeholder = placeholder;
    inp.addEventListener('input', updateDistStats);
    td.appendChild(inp);
    tr.appendChild(td);
  });
  const delTd = document.createElement('td');
  delTd.className = 'del-col';
  const delBtn = document.createElement('button');
  delBtn.className = 'del-row-btn';
  delBtn.textContent = '×';
  delBtn.addEventListener('click', () => { tr.remove(); updateDistStats(); });
  delTd.appendChild(delBtn);
  tr.appendChild(delTd);
  tbody.appendChild(tr);
}

export function populateTable(id, rows, isRoses) {
  const tbody = document.querySelector(`#table-${id} tbody`);
  tbody.innerHTML = '';
  rows.forEach(r => {
    const cells = isRoses
      ? [{value: r.roses, step: 1}, {value: r.prob, step: 0.001}]
      : [{value: r.opens, step: 1}, {value: r.reward, step: 1}];
    makeRow(tbody, cells);
  });
}

export function addRow(id) {
  const tbody = document.querySelector(`#table-${id} tbody`);
  makeRow(tbody, [{value: '', step: 1}, {value: '', step: 0.001}]);
}

export function addMilestone() {
  const tbody = document.querySelector('#table-milestones tbody');
  makeRow(tbody, [{value: '', step: 1}, {value: '', step: 1}]);
}

export function readTable(id, col0, col1) {
  const rows = [];
  document.querySelectorAll(`#table-${id} tbody tr`).forEach(tr => {
    const inputs = tr.querySelectorAll('input');
    const v0 = parseFloat(inputs[0].value);
    const v1 = parseFloat(inputs[1].value);
    if (!isNaN(v0) && !isNaN(v1)) rows.push({[col0]: v0, [col1]: v1});
  });
  return rows;
}

export function updateDistStats() {
  ['red', 'yellow', 'gray'].forEach(id => {
    const rows = readTable(id, 'roses', 'prob');
    const ev = rows.reduce((acc, r) => acc + r.roses * r.prob, 0);
    const sum = rows.reduce((acc, r) => acc + r.prob, 0);
    document.getElementById(`ev-${id}`).textContent = ev.toFixed(3);
    const sumEl = document.getElementById(`sum-${id}`);
    sumEl.textContent = sum.toFixed(3);
    sumEl.className = 'dist-stat-value' + (Math.abs(sum - 1) > 0.001 ? ' warn' : '');
  });
}
