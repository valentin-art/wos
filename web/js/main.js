import { DEFAULTS } from './defaults.js';
import {
  populateFixedTable,
  populateFixedMilestoneTable,
  updateDistStats,
} from './table-helpers.js';
import { updateSidebarLabels } from './sidebar.js';
import { runSimulation, switchTab } from './results.js';
import {
  toggleAdvancedMode,
  buildPacksTable,
  onPackChange,
  updateGems,
  isAdvancedMode,
} from './advanced-mode.js';

// ── Expose entry points referenced by inline on*="" HTML attributes ────────
// (module scripts are not global, so these must be attached explicitly)
window.toggleAdvancedMode = toggleAdvancedMode;
window.runSimulation = runSimulation;
window.switchTab = switchTab;
window.onPackChange = onPackChange;
window.updateGems = updateGems;

// ── Init ──────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  populateFixedTable('red',    DEFAULTS.red);
  populateFixedTable('yellow', DEFAULTS.yellow);
  populateFixedTable('gray',   DEFAULTS.gray);
  populateFixedMilestoneTable();
  updateDistStats();
  updateSidebarLabels();
  document.getElementById('advToggle').classList.add('on');
  buildPacksTable();
  updateGems();

  ['pRed', 'pYellow', 'days', 'freePerDay'].forEach(id =>
    document.getElementById(id).addEventListener('input', updateSidebarLabels)
  );

  // Rebuild packs table when days changes (advanced mode)
  document.getElementById('days').addEventListener('input', () => {
    if (isAdvancedMode()) { buildPacksTable(); updateGems(); }
  });
});
