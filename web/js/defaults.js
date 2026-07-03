// ── Default data ──────────────────────────────────────────────────────────
export const DEFAULTS = {
  red:    [{roses: 100, prob: 0.02}, {roses: 50, prob: 0.06}, {roses: 20, prob: 0.42}, {roses: 0, prob: 0.50}],
  yellow: [{roses: 100, prob: 0.005}, {roses: 20, prob: 0.06}, {roses: 6, prob: 0.42}, {roses: 0, prob: 0.515}],
  gray:   [{roses: 100, prob: 0.003}, {roses: 6, prob: 0.107}, {roses: 3, prob: 0.405}, {roses: 0, prob: 0.485}],
  milestones: [
    {opens:  20, roses:  30, chests:  0},
    {opens:  50, roses:  50, chests:  0},
    {opens: 100, roses:   0, chests: 20},
    {opens: 150, roses: 100, chests:  0},
    {opens: 300, roses: 200, chests:  0},
    {opens: 500, roses:   0, chests: 30},
  ],
};

export const STRATEGIES = [
  {id: 1, name: "S1 — Red only",        desc: "Open red chests if any; otherwise refresh",         color: "#ff6b6b"},
  {id: 2, name: "S2 — Red + Yellow",    desc: "Open red & yellow if any; otherwise refresh",       color: "#ffd93d"},
  {id: 3, name: "S3 — Open all",        desc: "Open all chests every time",                        color: "#74b9ff"},
  {id: 4, name: "S4 — Hybrid (≥6→all)", desc: "≥6 valuable → open all; otherwise red only",       color: "#a29bfe"},
];

export const PACKS = [
  {label: '$1',   gems: 120},
  {label: '$3',   gems: 360},
  {label: '$5',   gems: 500},
  {label: '$10',  gems: 900},
  {label: '$20',  gems: 1700},
  {label: '$50',  gems: 3500},
  {label: '$100', gems: 6000},
];
