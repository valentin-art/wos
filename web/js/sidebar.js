// ── Sidebar reactive updates ──────────────────────────────────────────────
export function updateSidebarLabels() {
  const pRed = parseFloat(document.getElementById('pRed').value) || 0;
  const pYellow = parseFloat(document.getElementById('pYellow').value) || 0;
  const pGray = Math.max(0, 1 - pRed - pYellow);
  document.getElementById('pGrayBadge').textContent = `P(gray) auto: ${pGray.toFixed(4)}`;

  const days = parseInt(document.getElementById('days').value) || 0;
  const free = parseInt(document.getElementById('freePerDay').value) || 0;
  document.getElementById('totalFreesBadge').textContent = `Total free refreshes: ${days * free}`;

  const caption = `Monte Carlo · ${days} day${days !== 1 ? 's' : ''} · ${free} free refreshes/day · All 4 strategies simulated`;
  document.getElementById('mainCaption').textContent = caption;
  updateLogicText();
}

export function updateLogicText() {
  const days = parseInt(document.getElementById('days').value) || 6;
  const free = parseInt(document.getElementById('freePerDay').value) || 3;
  document.getElementById('logicText').innerHTML = `
    <strong>Optimal play strategy used for every strategy variant:</strong><br><br>
    • <strong>Days 1 to ${days - 1}:</strong> only free refreshes are used.
      Once the ${free} free refreshes per day are exhausted, the day ends — no paid refreshes happen.<br>
    • <strong>Day ${days} (last day):</strong> free refreshes first, then paid refreshes until the budget runs out.<br>
    • <strong>Within each refresh cycle:</strong> chests are generated, then opened according to the strategy (S1–S4).
      If the budget can't cover everything desired, we open as many as affordable
      (priority red → yellow → gray), then end the day.<br>
    • <strong>Milestone rewards:</strong> cumulative — every time total opens (any chest type) reach a threshold,
      the reward is added to the rose total.<br><br>
    All four strategies run on the <strong>same random chest sequences</strong> (shared seed)
    so differences reflect strategy choice, not random noise.
  `;
}
