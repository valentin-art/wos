// ── Default data ──────────────────────────────────────────────────────────
export const EVENT_DAYS = 2; // fixed — Mia's Fortune always runs exactly 2 days

export const DAILY_MISSION_TICKETS_PER_DAY = 22;
export const FREE_TICKETS_PER_DAY = 1;

export const PACKS = [
  { label: '$5',   tickets: 50 },
  { label: '$10',  tickets: 90 },
  { label: '$20',  tickets: 170 },
  { label: '$50',  tickets: 340 },
  { label: '$100', tickets: 550 },
];

export const MILESTONES = [
  { wishes: 20,  rewardLabel: '5 fortune tickets',  ticketGrant: 5 },
  { wishes: 100, rewardLabel: '12 fortune tickets', ticketGrant: 12 },
  { wishes: 250, rewardLabel: '3 FC chests',        ticketGrant: 0 },
  { wishes: 750, rewardLabel: '100 FC',             ticketGrant: 0 },
];
