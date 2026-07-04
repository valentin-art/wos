const PAGES = [
  { path: '/', label: 'FROSTY FORTUNE' },
  { path: '/chief_gears/', label: 'CHIEF GEARS' },
  { path: '/charms/', label: 'CHARMS' },
  { path: '/mia_fortune/', label: 'MIA FORTUNE' },
];

function normalizePath(pathname) {
  let p = pathname.replace(/index\.html$/, '');
  if (!p.endsWith('/')) p += '/';
  return p;
}

export function initNav() {
  const root = document.getElementById('nav-root');
  if (!root) return;

  const current = normalizePath(location.pathname);

  const links = PAGES.map(p =>
    `<a class="nav-link${p.path === current ? ' active' : ''}" href="${p.path}">${p.label}</a>`
  ).join('');

  root.innerHTML = `
    <nav class="nav">
      <div class="nav-logo">
        <div class="logo-diamond"><div class="logo-inner"></div></div>
        <span class="nav-brand">WOS <span>TOOLS</span></span>
      </div>
      <div class="nav-links">${links}</div>
    </nav>
  `;
}

initNav();
