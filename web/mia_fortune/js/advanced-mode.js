import { PACKS, EVENT_DAYS, DAILY_MISSION_TICKETS_PER_DAY, FREE_TICKETS_PER_DAY, MILESTONES } from './defaults.js';

// ── Advanced mode ─────────────────────────────────────────────────────────
let advancedMode = true;

export function toggleAdvancedMode() {
  advancedMode = !advancedMode;
  document.getElementById('advToggle').classList.toggle('on', advancedMode);
  document.getElementById('simpleBudget').style.display = advancedMode ? 'none' : '';
  document.getElementById('advSections').style.display  = advancedMode ? '' : 'none';
  if (advancedMode) { buildPacksTable(); updateTicketTotal(); }
}

export function isAdvancedMode() {
  return advancedMode;
}

export function buildPacksTable() {
  const head = document.getElementById('packsHead');
  const body = document.getElementById('packsBody');

  let hRow = '<tr><th>Pack</th><th>Tickets</th>';
  for (let d = 1; d <= EVENT_DAYS; d++) hRow += `<th>D${d}</th>`;
  head.innerHTML = hRow + '</tr>';

  body.innerHTML = PACKS.map((p, pi) => {
    let row = `<tr><td>${p.label}</td><td>${p.tickets}</td>`;
    for (let d = 0; d < EVENT_DAYS; d++) {
      row += `<td><input type="checkbox" id="pack_${pi}_${d}" onchange="onPackChange(${pi},${d})"></td>`;
    }
    return row + '</tr>';
  }).join('');
}

export function onPackChange() {
  // Packs are selected independently — no cheaper-first requirement.
  updateTicketTotal();
}

export function updateTicketTotal() {
  const missionsTickets = DAILY_MISSION_TICKETS_PER_DAY * EVENT_DAYS;
  const freeTickets     = FREE_TICKETS_PER_DAY * EVENT_DAYS;

  let packTickets = 0;
  PACKS.forEach((p, pi) => {
    for (let d = 0; d < EVENT_DAYS; d++) {
      if (document.getElementById(`pack_${pi}_${d}`)?.checked) packTickets += p.tickets;
    }
  });

  const total = missionsTickets + freeTickets + packTickets;

  document.getElementById('missionsTickets').textContent = missionsTickets.toLocaleString();
  document.getElementById('freeTickets').textContent     = freeTickets.toLocaleString();
  document.getElementById('totalTicketsDisplay').textContent = total.toLocaleString() + ' tickets';

  // feed into the budget field that the simulation reads
  document.getElementById('budget').value = total;
}

export function populateMilestoneTable() {
  const tbody = document.querySelector('#table-milestones tbody');
  tbody.innerHTML = '';

  MILESTONES.forEach(m => {
    const tr = document.createElement('tr');

    const tdW = document.createElement('td');
    tdW.innerHTML = `<input type="number" value="${m.wishes}" readonly style="color:var(--muted);cursor:default;text-align:center">`;
    tr.appendChild(tdW);

    const tdR = document.createElement('td');
    tdR.innerHTML = `<input type="text" value="${m.rewardLabel}" readonly style="color:var(--text);cursor:default">`;
    tr.appendChild(tdR);

    const tdT = document.createElement('td');
    if (m.ticketGrant === 0) {
      tdT.innerHTML = `<input type="text" value="–" readonly style="color:var(--muted);cursor:default;text-align:center">`;
    } else {
      tdT.innerHTML = `<input type="number" value="${m.ticketGrant}" readonly style="color:var(--accent);cursor:default;text-align:center">`;
    }
    tr.appendChild(tdT);

    tbody.appendChild(tr);
  });
}
