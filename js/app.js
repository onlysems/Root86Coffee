/* ============================================================
   ROOT 86 COFFEE — Main Application v2
   ============================================================ */

// ── State ──────────────────────────────────────────────────
const state = {
  quote: [],
  filters: { origin: '', process: '', certification: '', warehouse: '', special: '', search: '' },
  filteredCoffees: COFFEES.filter(c => !c.hidden),
  activeCoffeeId: null,
  panelOpen: false
};

// ── Flags ───────────────────────────────────────────────────
// ISO-3166 alpha-2 codes for our origins. Windows renders 🇵🇪 as "PE",
// so we use flagcdn.com PNGs instead of emoji.
const FLAG_CODES = {
  'Brazil':'br','Colombia':'co','Costa Rica':'cr','Ethiopia':'et',
  'Guatemala':'gt','Honduras':'hn','Indonesia':'id','Kenya':'ke',
  'Mexico':'mx','Nicaragua':'ni','Panama':'pa','Papua New Guinea':'pg',
  'Peru':'pe','Rwanda':'rw','Tanzania':'tz','Uganda':'ug'
};
function flagImg(origin, size = 'w40') {
  const code = FLAG_CODES[origin];
  if (!code) {
    // Blends / unknown → globe glyph
    return `<span class="flag-glyph" aria-label="${origin || 'Blend'}">🌍</span>`;
  }
  return `<img class="flag-img" src="https://flagcdn.com/${size}/${code}.png" srcset="https://flagcdn.com/${size === 'w80' ? 'w160' : 'w80'}/${code}.png 2x" width="24" height="18" alt="${origin} flag" loading="lazy" />`;
}
// Back-compat shim — some older call sites used FLAGS[origin] directly
const FLAGS = new Proxy({}, { get: (_, k) => flagImg(k) });

const CERT_CLASS = {
  'Organic':'cflag-organic','Fair Trade':'cflag-ft',
  'Rainforest Alliance':'cflag-rfa',"Women's Lot":'cflag-womens','Decaf':'cflag-decaf'
};

// ── DOM ────────────────────────────────────────────────────
const $ = (s,c=document) => c.querySelector(s);
const $$ = (s,c=document) => [...c.querySelectorAll(s)];

// ── Init ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initHeroCanvas();
  initNav();
  buildFilters();
  renderGrid();
  renderQuoteItems();
  bindEvents();
  initScrollProgress();
  initStatCounters();
  initMap();
  initBtbCarousel();
  initCursor();
  initNewsletter();
});

// ================================================
// NEWSLETTER SIGNUP
// Posts to <formEndpoint>/subscribe (Cloudflare Worker).
// ================================================
function initNewsletter(){
  const form = document.getElementById('newsletter-form');
  if (!form) return;
  const btn    = document.getElementById('newsletter-btn');
  const status = document.getElementById('newsletter-status');
  const emailEl = document.getElementById('newsletter-email');
  const nameEl  = document.getElementById('newsletter-name');

  form.addEventListener('submit', async e => {
    e.preventDefault();
    if (!status || !btn) return;
    const email = (emailEl.value || '').trim();
    const name  = (nameEl.value || '').trim();
    const website = (form.querySelector('input[name="website"]')?.value || '').trim();

    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      status.textContent = 'Please enter a valid email.';
      status.className = 'newsletter-status err';
      return;
    }

    const base = (typeof SITE_SETTINGS !== 'undefined' && SITE_SETTINGS.formEndpoint)
      ? SITE_SETTINGS.formEndpoint.replace(/\/+$/, '') : '';
    if (!base) {
      status.textContent = 'Signup isn\'t configured yet.';
      status.className = 'newsletter-status err';
      return;
    }

    btn.disabled = true;
    const origLabel = btn.textContent;
    btn.textContent = 'Subscribing…';
    status.textContent = '';
    status.className = 'newsletter-status';

    try {
      const r = await fetch(base + '/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, name, website, source: 'homepage' })
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok || !data.ok) throw new Error(data.error || 'Something went wrong');

      status.textContent = data.duplicate
        ? 'You\'re already on the list, thanks!'
        : 'You\'re in. Watch your inbox for the next arrival drop.';
      status.className = 'newsletter-status ok';
      form.reset();
    } catch(err) {
      status.textContent = 'Couldn\'t subscribe, try again in a moment.';
      status.className = 'newsletter-status err';
    } finally {
      btn.disabled = false;
      btn.textContent = origLabel;
    }
  });
}

// ================================================
// CUSTOM CURSOR — red dot + trailing ring
// Disabled on touch devices and when reduced-motion is preferred.
// ================================================
function initCursor(){
  const dot  = document.getElementById('cursor-dot');
  const ring = document.getElementById('cursor-ring');
  if (!dot || !ring) return;
  if (window.matchMedia('(pointer: coarse)').matches) {
    dot.style.display = 'none'; ring.style.display = 'none';
    return;
  }

  let mx = 0, my = 0, rx = 0, ry = 0, started = false;

  document.addEventListener('mousemove', e => {
    mx = e.clientX; my = e.clientY;
    dot.style.left = mx + 'px';
    dot.style.top  = my + 'px';
    if (!started) {
      // First move: snap ring to pointer so it doesn't fly in from 0,0
      rx = mx; ry = my;
      ring.style.left = rx + 'px';
      ring.style.top  = ry + 'px';
      started = true;
    }
  }, { passive: true });

  // Hide when leaving the window, restore on re-entry
  document.addEventListener('mouseleave', () => {
    dot.style.opacity = '0'; ring.style.opacity = '0';
  });
  document.addEventListener('mouseenter', () => {
    dot.style.opacity = '1'; ring.style.opacity = '0.55';
  });

  // Smooth ring follow
  function tick(){
    rx += (mx - rx) * 0.14;
    ry += (my - ry) * 0.14;
    ring.style.left = rx + 'px';
    ring.style.top  = ry + 'px';
    requestAnimationFrame(tick);
  }
  tick();

  // Hover expand on interactive elements
  const hover = e => e.target.closest('a, button, [role="button"], input, select, textarea, .ccard, label') && ring.classList.add('hover');
  const unhover = e => e.target.closest('a, button, [role="button"], input, select, textarea, .ccard, label') && ring.classList.remove('hover');
  document.addEventListener('mouseover', hover);
  document.addEventListener('mouseout', unhover);
}

// ================================================
// BEHIND-THE-BAG IMAGE CAROUSEL
// Cycles through origin-story photos from /wix images/.
// ================================================
const BTB_IMAGES = [
  { file: 'Abakundakawa2.jpg',                             caption: 'Abakundakawa cooperative, Rwanda' },
  { file: 'Brazil Mogiana.jpg',                            caption: 'Mogiana region, Brazil' },
  { file: 'Brazil Mogiana natural.jpg',                    caption: 'Natural process, Mogiana · Brazil' },
  { file: 'Brazil Pocos de Caldas.jpg',                    caption: 'Poços de Caldas, Sul de Minas · Brazil' },
  { file: 'Pocos de Caldas.jpg',                           caption: 'Poços de Caldas · Brazil' },
  { file: 'Sitio do Campo.png',                            caption: 'Sítio do Campo estate · Brazil' },
  { file: 'cafe capucas hon2.jpg',                         caption: 'Café Capucas · Honduras' },
  { file: 'Ethiopia natural drying bed.jpg',               caption: 'Natural drying beds · Ethiopia' },
  { file: 'Shakiso washed 2.jpg',                          caption: 'Shakiso washing station · Ethiopia' },
  { file: 'Sidama.jpg',                                    caption: 'Sidama region · Ethiopia' },
  { file: 'Yirgacheffe.jpg',                               caption: 'Yirgacheffe · Ethiopia' },
  { file: 'Guatemala_NuevaGranada.webp',                   caption: 'Nueva Granada · Guatemala' },
  { file: 'Ketiara1_edited.jpg',                           caption: 'Ketiara cooperative · Sumatra' },
  { file: 'Sumatra-Picker.jpg',                            caption: 'Coffee picker · Sumatra' },
  { file: 'Mexico Chiapas cherry picking.jpg',             caption: 'Cherry picking, Chiapas · Mexico' },
  { file: 'Mexico Chiapas coffee milling.jpg',             caption: 'Coffee milling, Chiapas · Mexico' },
  { file: 'moyobamba2.jpg',                                caption: 'Moyobamba · Peru' },
  { file: 'Uganda coffee pickers.jpg',                     caption: 'Coffee pickers · Uganda' },
  { file: 'sipi_falls_mount_elgon_national_park uganda.jpg', caption: 'Sipi Falls, Mount Elgon · Uganda' },
  { file: 'V&G10.jpg',                                     caption: 'Producer partner visit' },
  { file: '20140410_141343.jpg',                           caption: 'Origin trip · 2014' },
  { file: '_edited.jpg',                                   caption: 'On the farm' },
  { file: 'Screen Shot 2022-11-01 at 2.26.47 PM.png',      caption: 'From the cupping table' }
];

function initBtbCarousel(){
  const wrap = document.getElementById('btb-carousel');
  const dotsWrap = document.getElementById('btb-dots');
  if (!wrap) return;

  // Shuffle so the order varies each load (but seed by day so it's stable for repeat visitors same day)
  const images = BTB_IMAGES.slice();
  const dayOffset = new Date().getUTCDate() % images.length;
  const ordered = images.slice(dayOffset).concat(images.slice(0, dayOffset));

  ordered.forEach((img, i) => {
    const src = 'wix%20images/' + encodeURIComponent(img.file);
    const slide = document.createElement('div');
    slide.className = 'btb-slide' + (i === 0 ? ' active' : '');
    slide.innerHTML = `
      <img src="${src}" alt="${img.caption}" loading="${i === 0 ? 'eager' : 'lazy'}" onerror="this.parentElement.classList.add('broken')" />
      <div class="btb-slide-label">
        <span class="btb-slide-name">${img.caption}</span>
      </div>`;
    wrap.appendChild(slide);

    if (dotsWrap) {
      const dot = document.createElement('button');
      dot.className = 'btb-dot' + (i === 0 ? ' active' : '');
      dot.type = 'button';
      dot.setAttribute('aria-label', `Show image ${i + 1}`);
      dot.addEventListener('click', () => goTo(i));
      dotsWrap.appendChild(dot);
    }
  });

  const slides = wrap.querySelectorAll('.btb-slide');
  const dots   = dotsWrap ? dotsWrap.querySelectorAll('.btb-dot') : [];
  let idx = 0;
  let timer;

  function goTo(n){
    slides[idx].classList.remove('active');
    if (dots[idx]) dots[idx].classList.remove('active');
    idx = (n + slides.length) % slides.length;
    slides[idx].classList.add('active');
    if (dots[idx]) dots[idx].classList.add('active');
    restart();
  }
  function next(){ goTo(idx + 1); }
  function restart(){ clearInterval(timer); timer = setInterval(next, 4200); }

  restart();

  // Pause when tab hidden / off-screen
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) clearInterval(timer); else restart();
  });
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver(entries => {
      entries.forEach(e => { if (e.isIntersecting) restart(); else clearInterval(timer); });
    }, { threshold: 0.1 });
    io.observe(wrap);
  }
}

// ================================================
// HERO CANVAS (particle animation)
// ================================================
function initHeroCanvas() {
  const canvas = $('#hero-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const particles = [];
  const COUNT = 90;

  function resize() {
    canvas.width  = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;
  }
  resize();
  window.addEventListener('resize', resize);

  for (let i = 0; i < COUNT; i++) {
    particles.push({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      r: Math.random() * 1.5 + 0.3,
      vx: (Math.random() - 0.5) * 0.35,
      vy: (Math.random() - 0.5) * 0.35,
      o: Math.random() * 0.5 + 0.1
    });
  }

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    particles.forEach(p => {
      p.x += p.vx; p.y += p.vy;
      if (p.x < 0) p.x = canvas.width;
      if (p.x > canvas.width) p.x = 0;
      if (p.y < 0) p.y = canvas.height;
      if (p.y > canvas.height) p.y = 0;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(200,16,46,${p.o})`;
      ctx.fill();
    });

    // Draw connecting lines
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const dist = Math.sqrt(dx*dx + dy*dy);
        if (dist < 120) {
          ctx.beginPath();
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.strokeStyle = `rgba(200,16,46,${0.06 * (1 - dist/120)})`;
          ctx.lineWidth = 0.8;
          ctx.stroke();
        }
      }
    }
    requestAnimationFrame(draw);
  }
  draw();
}

// ================================================
// NAV SCROLL
// ================================================
function initNav() {
  window.addEventListener('scroll', () => {
    const nav = $('#main-nav');
    if (nav) nav.classList.toggle('scrolled', window.scrollY > 60);
  }, { passive: true });
}

// ================================================
// FILTERS
// ================================================
function buildFilters() {
  // Count how many catalogue coffees match each filter value
  const visible = COFFEES.filter(c => !c.hidden);
  const countIn = (picker) => {
    const out = {};
    visible.forEach(c => {
      const val = picker(c);
      if (Array.isArray(val)) val.forEach(v => { if (v) out[v] = (out[v]||0) + 1; });
      else if (val) out[val] = (out[val]||0) + 1;
    });
    return out;
  };
  const counts = {
    origin:  countIn(c => c.origin),
    process: countIn(c => c.process),
    cert:    countIn(c => c.certifications || []),
    wh:      countIn(c => c.warehouses || [])
  };
  const add = (id, opts, key) => {
    const sel = $(id); if (!sel) return;
    opts.forEach(o => {
      const n = counts[key][o] || 0;
      const el = document.createElement('option');
      el.value = o;
      el.textContent = n ? `${o} (${n})` : o;
      sel.appendChild(el);
    });
  };
  add('#filter-origin',  FILTER_OPTIONS.origins,        'origin');
  add('#filter-process', FILTER_OPTIONS.processes,      'process');
  add('#filter-cert',    FILTER_OPTIONS.certifications, 'cert');
  add('#filter-wh',      FILTER_OPTIONS.warehouses,     'wh');
}

function applyFilters() {
  const { origin, process, certification, warehouse, special, search } = state.filters;
  state.filteredCoffees = COFFEES.filter(c => {
    if (c.hidden) return false;
    if (origin && c.origin !== origin) return false;
    if (process && c.process !== process) return false;
    if (certification && !c.certifications.includes(certification)) return false;
    if (warehouse && !c.warehouses.includes(warehouse)) return false;
    if (special === 'favourite' && !c.favourite) return false;
    if (special === 'onSale' && !c.onSale) return false;
    if (search) {
      const q = search.toLowerCase();
      if (!c.name.toLowerCase().includes(q) &&
          !c.origin.toLowerCase().includes(q) &&
          !c.region.toLowerCase().includes(q) &&
          !c.tastingNotes.toLowerCase().includes(q)) return false;
    }
    return true;
  });
  renderGrid();
}

// ================================================
// COFFEE GRID
// ================================================
function renderGrid() {
  const grid = $('#coffee-grid');
  const countEl = $('#results-count');
  if (!grid) return;

  const count = state.filteredCoffees.length;
  if (countEl) countEl.innerHTML = `Showing <strong>${count}</strong> coffee${count !== 1 ? 's' : ''}`;

  if (count === 0) {
    grid.innerHTML = `<div class="no-results"><p>No coffees found</p><span>Try adjusting your filters</span></div>`;
    return;
  }

  grid.innerHTML = state.filteredCoffees.map(c => cardHTML(c)).join('');

  $$('.more-info-btn', grid).forEach(btn =>
    btn.addEventListener('click', e => { e.stopPropagation(); openModal(parseInt(btn.dataset.id)); }));
  $$('.add-quote-btn', grid).forEach(btn =>
    btn.addEventListener('click', e => {
      e.stopPropagation();
      const id = parseInt(btn.dataset.id);
      const wasIn = state.quote.some(q => q.id === id);
      toggleQuote(id, btn);
      // Fly-to-cart animation only when ADDING (not removing / not on incompat)
      if (!wasIn && state.quote.some(q => q.id === id)) flyToCart(btn);
    }));
  $$('.ccard', grid).forEach(card =>
    card.addEventListener('click', e => {
      // Don't open the modal if the user clicked a button inside the card
      if (e.target.closest('button')) return;
      openModal(parseInt(card.dataset.id));
    }));

  updateGridButtons();
}

function cardHTML(c) {
  const flag = flagImg(c.origin);
  const inQ  = state.quote.some(q => q.id === c.id);
  const na = '<span class="ccard-na">N/A</span>';
  const fallback = v => (v && String(v).trim()) ? v : na;
  const certFlags = c.certifications.map(cert =>
    `<span class="cflag ${CERT_CLASS[cert] || ''}">${cert}</span>`).join('');
  const ribbons = [
    c.favourite ? `<span class="ccard-ribbon ribbon-fav" title="Root 86 Favourite">★ Favourite</span>` : '',
    c.onSale    ? `<span class="ccard-ribbon ribbon-sale" title="On Sale">On Sale</span>` : ''
  ].filter(Boolean).join('');
  const warehouses = (c.warehouses || []).map(w => w.split(',')[0]);
  const stockLine = c.available
    ? `<span class="stock-dot" aria-hidden="true"></span><span class="stock-label">In stock</span>${warehouses.length ? `<span class="stock-sep">·</span><span class="stock-where">${warehouses.join(' · ')}</span>` : ''}`
    : `<span class="stock-dot out" aria-hidden="true"></span><span class="stock-label">Out of stock</span>`;

  return `
    <article class="ccard${!c.available || c.soldOut ? ' sold-out' : ''}" data-id="${c.id}">
      ${ribbons ? `<div class="ccard-ribbons">${ribbons}</div>` : ''}
      <header class="ccard-head">
        <div class="ccard-origin">${flag ? `<span class="ccard-flag">${flag}</span>` : ''}<span class="ccard-origin-name">${c.origin}</span></div>
        <h3 class="ccard-name">${c.name}</h3>
      </header>
      <blockquote class="ccard-notes" data-notes="${(c.tastingNotes||'').replace(/"/g,'&quot;')}">${c.tastingNotes && c.tastingNotes.trim() ? c.tastingNotes : 'Tasting notes coming soon.'}</blockquote>
      <dl class="ccard-specs">
        <div class="spec spec-region"><dt>Region</dt><dd>${fallback(c.region)}</dd></div>
        <div class="spec"><dt>Process</dt><dd>${fallback(c.process)}</dd></div>
        <div class="spec"><dt>Bag</dt><dd>${c.bagWeight ? c.bagWeight + ' lbs' : na}</dd></div>
      </dl>
      ${certFlags ? `<div class="ccard-certs">${certFlags}</div>` : ''}
      <div class="ccard-foot">
        <div class="ccard-stock${c.available ? '' : ' out'}">${stockLine}</div>
        <div class="ccard-actions">
          <button class="more-info-btn" data-id="${c.id}">Details</button>
          <button class="add-quote-btn${inQ ? ' added' : ''}" data-id="${c.id}" ${!c.available ? 'disabled' : ''}>
            ${inQ ? '✓ Added' : 'Add to Quote'}
          </button>
        </div>
      </div>
    </article>`;
}

function updateGridButtons() {
  const compat = quoteCompatibleZones();
  const hasQuote = state.quote.length > 0;
  $$('.add-quote-btn').forEach(btn => {
    const id = parseInt(btn.dataset.id);
    const coffee = COFFEES.find(c => c.id === id);
    const inQ = state.quote.some(q => q.id === id);
    const zones = coffee ? coffeeZones(coffee) : new Set();
    const compatible = !hasQuote || inQ || [...zones].some(z => compat.has(z));
    btn.classList.toggle('added', inQ);
    btn.classList.toggle('incompatible', !compatible);
    if (inQ) btn.textContent = 'Added';
    else if (!compatible) btn.textContent = 'Different warehouse';
    else btn.textContent = 'Add to Quote';
    // Keep clickable so the toast can explain — but visually dimmed
    btn.title = compatible ? '' :
      `Your quote ships from ${[...compat].map(zoneLabel).join(' or ')}; this coffee is at ${[...zones].map(zoneLabel).join(' or ') || 'no matching warehouse'}.`;
  });
  // Modal button
  const mb = $('#modal-add-btn');
  if (mb && state.activeCoffeeId) {
    const coffee = COFFEES.find(c => c.id === state.activeCoffeeId);
    const inQ = state.quote.some(q => q.id === state.activeCoffeeId);
    const zones = coffee ? coffeeZones(coffee) : new Set();
    const compatible = !hasQuote || inQ || [...zones].some(z => compat.has(z));
    mb.classList.toggle('added', inQ);
    mb.classList.toggle('incompatible', !compatible);
    if (inQ) mb.textContent = 'In Quote - Remove';
    else if (!compatible) mb.textContent = 'Different warehouse';
    else mb.textContent = 'Add to Quote';
    mb.title = compatible ? '' :
      `Your quote ships from ${[...compat].map(zoneLabel).join(' or ')}; this coffee is at ${[...zones].map(zoneLabel).join(' or ') || 'no matching warehouse'}.`;
  }
}

// ================================================
// QUOTE
// ================================================
// Warehouse-zone compatibility: a quote must resolve to a SINGLE
// shipping origin. Vancouver + Parksville are interchangeable
// (both BC); Lévis/Quebec is separate.
function coffeeZones(coffee){
  const zones = new Set();
  (coffee.warehouses || []).forEach(w => {
    const s = (w || '').toLowerCase();
    if (s.indexOf('vancouver') !== -1 || s.indexOf('parksville') !== -1) zones.add('west');
    if (s.indexOf('lévis') !== -1 || s.indexOf('levis') !== -1 || s.indexOf('qc') !== -1 || s.indexOf('quebec') !== -1) zones.add('east');
  });
  return zones;
}
function quoteCompatibleZones(){
  // Intersection of zones across everything currently in the quote
  if (!state.quote.length) return new Set(['west','east']);
  let inter = null;
  for (const c of state.quote) {
    const z = coffeeZones(c);
    if (inter === null) inter = new Set(z);
    else inter = new Set([...inter].filter(x => z.has(x)));
  }
  return inter || new Set();
}
function zoneLabel(z){
  if (z === 'west') return 'BC (Vancouver / Parksville)';
  if (z === 'east') return 'Quebec (Lévis)';
  return z;
}

// Specific BC warehouses for a coffee ('vancouver' / 'parksville')
function bcWarehouses(coffee){
  const set = new Set();
  (coffee.warehouses || []).forEach(w => {
    const s = (w || '').toLowerCase();
    if (s.indexOf('vancouver') !== -1) set.add('vancouver');
    if (s.indexOf('parksville') !== -1) set.add('parksville');
  });
  return set;
}
// Intersection of BC warehouse options across the full quote, so only
// warehouses that stock every selected coffee are valid pickup points.
function quoteBcPickupOptions(){
  if (!state.quote.length) return new Set();
  let inter = null;
  for (const c of state.quote) {
    const set = bcWarehouses(c);
    if (inter === null) inter = new Set(set);
    else inter = new Set([...inter].filter(x => set.has(x)));
  }
  return inter || new Set();
}
// Decide what to show in the pickup-location field based on the current
// quote and pickup-checkbox state. Called whenever either changes.
function updatePickupLocationField(){
  const wrap   = $('#pickup-loc-wrap');
  const auto   = $('#pickup-loc-auto');
  const select = $('#field-pickup-location');
  const label  = $('#pickup-loc-label');
  if (!wrap || !auto || !select) return;

  const zones  = quoteCompatibleZones();
  const isQC   = zones.has('east') && !zones.has('west');
  const isBC   = zones.has('west') && !zones.has('east');
  const pickup = $('#field-pickup') && $('#field-pickup').checked;

  // QC quote: always show warehouse (per spec, even without pickup)
  if (isQC) {
    wrap.style.display = '';
    label.textContent = pickup ? 'Pickup Location' : 'Shipping From';
    auto.textContent = 'Lévis, QC';
    auto.style.display = '';
    select.style.display = 'none';
    select.value = 'Lévis, QC';
    return;
  }

  // BC quote: only matters if the customer wants to pick up
  if (isBC && pickup) {
    const opts = quoteBcPickupOptions();
    wrap.style.display = '';
    label.textContent = 'Pickup Location';
    if (opts.size === 1) {
      const only = opts.has('vancouver') ? 'Vancouver, BC' : 'Parksville, BC';
      auto.textContent = only;
      auto.style.display = '';
      select.style.display = 'none';
      select.value = only;
    } else if (opts.size >= 2) {
      // Ambiguous — customer picks
      auto.style.display = 'none';
      select.style.display = '';
      // Preserve prior selection if still valid
      if (!select.value) select.value = '';
    } else {
      // No common warehouse (shouldn't happen if compatibility logic is working)
      auto.textContent = 'No shared BC warehouse';
      auto.style.display = '';
      select.style.display = 'none';
      select.value = '';
    }
    return;
  }

  // Otherwise hide the field entirely
  wrap.style.display = 'none';
  select.value = '';
}

function toggleQuote(id) {
  const coffee = COFFEES.find(c => c.id === id);
  if (!coffee) return;
  const idx = state.quote.findIndex(q => q.id === id);
  if (idx === -1) {
    // Check warehouse compatibility before adding
    const currentZones = quoteCompatibleZones();
    const newZones = coffeeZones(coffee);
    const inter = new Set([...currentZones].filter(x => newZones.has(x)));
    if (state.quote.length && inter.size === 0) {
      const currentLabel = [...currentZones].map(zoneLabel).join(' or ');
      const newLabel = [...newZones].map(zoneLabel).join(' or ') || 'no shared warehouse';
      showToast(`Can't mix warehouses, your quote ships from ${currentLabel}, but this coffee is only at ${newLabel}.`, true);
      return;
    }
    state.quote.push({ ...coffee, qty: 1 });
    showToast(coffee.name.split(' ').slice(0,3).join(' ') + ' added to quote');
  } else {
    state.quote.splice(idx, 1);
    showToast('Removed from quote', true);
  }
  renderQuoteItems();
  updateGridButtons();
  updateFloatBtn();
  updateNavCount();
}

function updateQty(id, delta) {
  const item = state.quote.find(q => q.id === id);
  if (!item) return;
  item.qty = Math.max(1, (item.qty || 1) + delta);
  renderQuoteItems();
  updateFloatBtn();
  updateNavCount();
}

function renderQuoteItems() {
  const wrap = $('#quote-items-wrap');
  const totalEl = $('#qp-bag-total');
  if (!wrap) return;
  // Refresh pickup-location affordance whenever the quote changes
  updatePickupLocationField();

  const totalBags = state.quote.reduce((s, q) => s + (q.qty || 1), 0);
  if (totalEl) totalEl.textContent = totalBags > 0 ? `(${totalBags} bag${totalBags !== 1 ? 's' : ''})` : '';

  if (state.quote.length === 0) {
    wrap.innerHTML = `
      <div class="quote-empty-state">
        <div class="quote-empty-icon">☕</div>
        <p>Your quote is empty</p>
        <span>Browse coffees and add them here</span>
      </div>`;
    return;
  }

  wrap.innerHTML = `<div class="quote-items">${state.quote.map(c => `
    <div class="quote-item">
      <div class="qi-info">
        <div class="qi-name">${c.name}</div>
        <div class="qi-detail">${c.origin} · ${c.process} · ${c.bagWeight} lbs/bag</div>
        <div class="qi-bags">${(c.qty || 1)} bag${(c.qty||1)!==1?'s':''} · ${(c.qty||1)*c.bagWeight} lbs total</div>
      </div>
      <div class="qi-controls">
        <div class="qi-qty">
          <button class="qi-qty-btn qi-minus" data-id="${c.id}">-</button>
          <span class="qi-qty-num">${c.qty || 1}</span>
          <button class="qi-qty-btn qi-plus" data-id="${c.id}">+</button>
        </div>
        <button class="qi-remove" data-id="${c.id}" title="Remove">x</button>
      </div>
    </div>`).join('')}</div>`;

  $$('.qi-remove', wrap).forEach(btn =>
    btn.addEventListener('click', () => toggleQuote(parseInt(btn.dataset.id))));
  $$('.qi-minus', wrap).forEach(btn =>
    btn.addEventListener('click', () => updateQty(parseInt(btn.dataset.id), -1)));
  $$('.qi-plus', wrap).forEach(btn =>
    btn.addEventListener('click', () => updateQty(parseInt(btn.dataset.id), 1)));
}

function updateFloatBtn() {
  const count = state.quote.reduce((s, q) => s + (q.qty || 1), 0);
  const el = $('#qf-count');
  if (el) { el.textContent = count; el.classList.toggle('visible', count > 0); }
}

function updateNavCount() {
  const count = state.quote.reduce((s, q) => s + (q.qty || 1), 0);
  const el = $('#nav-quote-count');
  if (el) { el.textContent = count; el.classList.toggle('visible', count > 0); }
}

// ================================================
// PANEL (slide-in quote)
// ================================================
function openPanel() {
  $('#quote-panel')?.classList.add('open');
  $('#quote-overlay')?.classList.add('open');
  document.body.style.overflow = 'hidden';
  state.panelOpen = true;
}
function closePanel() {
  $('#quote-panel')?.classList.remove('open');
  $('#quote-overlay')?.classList.remove('open');
  document.body.style.overflow = '';
  state.panelOpen = false;
}

// ================================================
// MODAL
// ================================================
function openModal(id) {
  const c = COFFEES.find(x => x.id === id);
  if (!c) return;
  state.activeCoffeeId = id;
  const flag = flagImg(c.origin, 'w80');
  const inQ  = state.quote.some(q => q.id === id);

  $('#modal-flag').innerHTML  = flag;
  $('#modal-name').textContent  = c.name;
  $('#modal-region').textContent = `${c.region} · ${c.origin}`;
  $('#modal-process').textContent  = c.process;
  $('#modal-grade').textContent    = c.grade;
  $('#modal-variety').textContent  = c.variety;
  $('#modal-altitude').textContent = c.altitude;
  $('#modal-weight').textContent   = `${c.bagWeight} lbs`;
  $('#modal-desc').textContent     = c.description;

  const mtWrap = $('#modal-maintext-wrap');
  const mt = (c.mainText || '').trim();
  if (mt) {
    $('#modal-maintext').textContent = mt;
    mtWrap.hidden = false;
  } else {
    mtWrap.hidden = true;
  }

  $('#modal-badges').innerHTML = [
    `<span class="cflag cflag-origin">${c.origin}</span>`,
    ...c.certifications.map(cert => `<span class="cflag ${CERT_CLASS[cert] || ''}">${cert}</span>`)
  ].join('');

  $('#modal-tasting-notes').innerHTML = c.tastingNotes.split(',').map(n =>
    `<span class="tasting-note">${n.trim()}</span>`).join('');

  $('#modal-warehouses').innerHTML = c.warehouses.map(w =>
    `<span class="warehouse-badge"><span class="warehouse-dot"></span>${w}</span>`).join('');

  const addBtn = $('#modal-add-btn');
  addBtn.classList.toggle('added', inQ);
  addBtn.textContent = inQ ? 'In Quote - Remove' : 'Add to Quote';
  addBtn.onclick = () => {
    const wasIn = state.quote.some(q => q.id === id);
    toggleQuote(id);
    if (!wasIn && state.quote.some(q => q.id === id)) flyToCart(addBtn);
  };

  $('#modal-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';

  if (window.r86Track) window.r86Track('coffee_view', { coffeeId: id });
}
function closeModal() {
  $('#modal-overlay')?.classList.remove('open');
  if (!state.panelOpen) document.body.style.overflow = '';
  state.activeCoffeeId = null;
}

// ================================================
// FORM SUBMIT
// ================================================
async function handleSubmit(e) {
  e.preventDefault();
  if (state.quote.length === 0) { showToast('Add at least one coffee first', true); return; }
  // If the pickup-location selector is visible and empty, the customer
  // still has to choose Vancouver or Parksville before we can submit.
  const locSel = $('#field-pickup-location');
  if (locSel && locSel.style.display !== 'none' && !locSel.value) {
    showToast('Please choose a pickup warehouse', true);
    locSel.focus();
    return;
  }

  const btn = $('#form-submit');
  btn.disabled = true; btn.textContent = 'Sending...';

  const items = state.quote.map(c => ({
    name: c.name,
    origin: c.origin,
    qty: c.qty || 1,
    bagWeight: c.bagWeight,
    process: c.process
  }));

  const payload = {
    form_type:   'quote',
    name:        $('#field-contact').value,
    company:     $('#field-company').value,
    email:       $('#field-email').value,
    phone:       $('#field-phone').value,
    address:     $('#field-address').value,
    residential: $('#field-residential').value,
    payment:     $('#field-payment').value,
    pickup:      $('#field-pickup').checked,
    pickup_location: $('#field-pickup-location') ? ($('#field-pickup-location').value || '') : '',
    tailgate:    $('#field-tailgate').checked,
    notes:       $('#field-notes').value,
    items:       items,
    website:     $('#field-website') ? $('#field-website').value : '' // honeypot
  };

  try {
    await submitForm(payload);
    showSuccess();
  } catch(err) {
    console.error(err);
    btn.disabled = false; btn.textContent = 'Send Quote Request';
    showToast('Something went wrong. Please try again.', true);
  }
}

function showSuccess() {
  $('#quote-form').style.display = 'none';
  $('#form-success').style.display = 'block';
  state.quote = [];
  renderQuoteItems(); updateFloatBtn(); updateNavCount(); updateGridButtons();
}

// ================================================
// TOAST
// ================================================
function showToast(msg, isRemove = false) {
  const t = $('#toast');
  if (!t) return;
  t.textContent = msg;
  t.className = `toast${isRemove ? ' removed' : ''} visible`;
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove('visible'), 3000);
}

// ================================================
// NUMBER ANIMATION
// ================================================
function animateNumbers(scope) {
  const nodes = (scope || document).querySelectorAll('[data-target]');
  nodes.forEach(el => {
    if (el.dataset.ran === '1') return;
    el.dataset.ran = '1';
    const target = parseInt(el.dataset.target);
    const suffix = el.dataset.suffix || '';
    if (isNaN(target)) return;
    let cur = 0;
    const step = Math.max(1, Math.ceil(target / 40));
    const timer = setInterval(() => {
      cur = Math.min(cur + step, target);
      el.textContent = cur + suffix;
      if (cur >= target) clearInterval(timer);
    }, 35);
  });
}
function initStatCounters(){
  // Scroll-trigger the counters when they enter the viewport, not on load.
  const band = document.querySelector('.stat-band');
  if (!band || !('IntersectionObserver' in window)) { animateNumbers(); return; }
  const io = new IntersectionObserver((entries, obs) => {
    entries.forEach(e => {
      if (e.isIntersecting) { animateNumbers(e.target); obs.unobserve(e.target); }
    });
  }, { threshold: 0.4 });
  io.observe(band);
}

// ================================================
// SCROLL PROGRESS BAR
// ================================================
function initScrollProgress(){
  const bar = document.getElementById('scroll-progress');
  if (!bar) return;
  let ticking = false;
  function update(){
    const h = document.documentElement;
    const max = h.scrollHeight - h.clientHeight;
    const pct = max > 0 ? (window.scrollY / max) * 100 : 0;
    bar.style.width = pct + '%';
    ticking = false;
  }
  window.addEventListener('scroll', () => {
    if (!ticking) { requestAnimationFrame(update); ticking = true; }
  }, { passive: true });
  update();
}

// ================================================
// ADD-TO-QUOTE CART PULSE (bean trail + fly animation removed per user request)
// ================================================
function flyToCart(/* sourceEl */){
  const btn = document.getElementById('nav-quote-btn');
  if (!btn) return;
  btn.classList.remove('cart-pulse');
  void btn.offsetWidth; // restart animation
  btn.classList.add('cart-pulse');
}

// ================================================
// CANADA MAP (Leaflet)
// ================================================
function initMap() {
  const el = document.getElementById('canada-map');
  if (!el || typeof L === 'undefined') return;

  const LOCATIONS = [
    {
      lat: 49.2827, lng: -123.1207,
      city: 'Vancouver', province: 'British Columbia',
      desc: 'Serving Western Canada\'s thriving specialty roaster community with fast access and competitive freight from the Pacific coast.',
      delay: '0s'
    },
    {
      lat: 49.3186, lng: -124.3137,
      city: 'Parksville', province: 'British Columbia',
      desc: 'Our Vancouver Island home base and sample courier address, supporting Vancouver Island\'s growing community of independent roasters.',
      delay: '0.8s'
    },
    {
      lat: 46.8090, lng: -71.1804,
      city: 'Lévis', province: 'Quebec',
      desc: 'Our Eastern hub, strategically positioned to serve Quebec and Atlantic roasters with efficient delivery across the French-speaking market.',
      delay: '1.6s'
    }
  ];

  // Initialise map — centred on Canada, no scroll zoom
  const map = L.map('canada-map', {
    center: [56, -96],
    zoom: 4,
    zoomControl: false,
    scrollWheelZoom: false,
    attributionControl: true
  });

  // Clean, minimal tile layer (CartoDB Positron — free, no key)
  L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 19
  }).addTo(map);

  // Zoom control bottom-right
  L.control.zoom({ position: 'bottomright' }).addTo(map);

  // Custom div icon
  function makeIcon(delay) {
    return L.divIcon({
      className: '',
      html: `<div class="r86-marker" style="animation-delay:${delay}"></div>`,
      iconSize: [16, 16],
      iconAnchor: [8, 8],
      popupAnchor: [0, -14]
    });
  }

  // Add markers with branded popups
  // Per-location label direction/offset so Vancouver & Parksville (very close)
  // don't overlap each other.
  const LABEL_DIRS = {
    'Vancouver': { direction: 'bottom', offset: [0, 10] },
    'Parksville': { direction: 'top', offset: [0, -10] },
    'Lévis': { direction: 'right', offset: [10, 0] }
  };
  LOCATIONS.forEach(loc => {
    const popup = L.popup({ closeButton: true, maxWidth: 260, className: 'r86-popup-wrap' })
      .setContent(`
        <div class="r86-popup">
          <div class="r86-popup-city">${loc.city}</div>
          <span class="r86-popup-prov">${loc.province}</span>
          <p class="r86-popup-desc">${loc.desc}</p>
        </div>`);

    const marker = L.marker([loc.lat, loc.lng], { icon: makeIcon(loc.delay) })
      .addTo(map)
      .bindPopup(popup);
    const lbl = LABEL_DIRS[loc.city] || { direction: 'right', offset: [10, 0] };
    marker.bindTooltip(loc.city, {
      permanent: true,
      direction: lbl.direction,
      offset: lbl.offset,
      className: 'r86-map-label'
    });
  });

  // Branded title in the top-left corner of the map
  const TitleControl = L.Control.extend({
    options: { position: 'topleft' },
    onAdd: function() {
      const el = L.DomUtil.create('div', 'r86-map-title');
      el.innerHTML = 'Root 86 Coffee';
      L.DomEvent.disableClickPropagation(el);
      return el;
    }
  });
  new TitleControl().addTo(map);

  // Fit bounds to show all markers with padding
  const bounds = L.latLngBounds(LOCATIONS.map(l => [l.lat, l.lng]));
  map.fitBounds(bounds, { padding: [80, 120] });

  // ── Animated shipping routes ──────────────────────────────────
  // Red pulses travel from each warehouse to major Canadian cities on
  // a continuous loop. Conveys "we ship coast-to-coast from in-country"
  // visually, without requiring the visitor to read the copy.
  initShippingRoutes(map, el, LOCATIONS);
}

function initShippingRoutes(map, el, LOCATIONS){
  const NS = 'http://www.w3.org/2000/svg';
  const DESTINATIONS = [
    { lat: 48.4284, lng: -123.3656 }, // Victoria
    { lat: 49.8880, lng: -119.4960 }, // Kelowna
    { lat: 51.0447, lng: -114.0719 }, // Calgary
    { lat: 53.5461, lng: -113.4938 }, // Edmonton
    { lat: 52.1332, lng: -106.6700 }, // Saskatoon
    { lat: 49.8951, lng:  -97.1384 }, // Winnipeg
    { lat: 48.3809, lng:  -89.2477 }, // Thunder Bay
    { lat: 43.6532, lng:  -79.3832 }, // Toronto
    { lat: 45.4215, lng:  -75.6972 }, // Ottawa
    { lat: 45.5017, lng:  -73.5673 }, // Montreal
    { lat: 46.8139, lng:  -71.2080 }, // Quebec City
    { lat: 44.6488, lng:  -63.5752 }, // Halifax
    { lat: 46.2382, lng:  -63.1311 }, // Charlottetown
    { lat: 45.2733, lng:  -66.0633 }, // Saint John
    { lat: 47.5615, lng:  -52.7126 }, // St. John's
  ];

  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('class', 'r86-routes');
  svg.style.cssText = 'position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none;z-index:400';
  el.appendChild(svg);

  function spawnPulse(){
    if (document.hidden) return;
    const origin = LOCATIONS[Math.floor(Math.random() * LOCATIONS.length)];
    const dest   = DESTINATIONS[Math.floor(Math.random() * DESTINATIONS.length)];
    let p1, p2;
    try {
      p1 = map.latLngToContainerPoint([origin.lat, origin.lng]);
      p2 = map.latLngToContainerPoint([dest.lat,   dest.lng]);
    } catch(e) { return; }
    const dx = p2.x - p1.x, dy = p2.y - p1.y;
    const dist = Math.hypot(dx, dy);
    if (dist < 40) return; // skip trivial / offscreen

    // Curve upward (away from straight line) — bezier control point perpendicular
    const mx = (p1.x + p2.x) / 2, my = (p1.y + p2.y) / 2;
    const curve = Math.min(90, dist * 0.22);
    // Flip direction so arcs bulge toward the top of the map
    const sign = (my > (p1.y + p2.y) / 2) ? 1 : -1;
    const cx = mx + (-dy / dist) * curve * sign;
    const cy = my + ( dx / dist) * curve * sign - Math.min(30, dist * 0.08);

    const path = document.createElementNS(NS, 'path');
    path.setAttribute('d', `M${p1.x},${p1.y} Q${cx},${cy} ${p2.x},${p2.y}`);
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke', '#c8102e');
    path.setAttribute('stroke-width', '1.4');
    path.setAttribute('stroke-linecap', 'round');
    path.style.opacity = '0';
    svg.appendChild(path);
    let len;
    try { len = path.getTotalLength(); } catch(e) { path.remove(); return; }
    path.setAttribute('stroke-dasharray', len);
    path.setAttribute('stroke-dashoffset', len);

    const dot = document.createElementNS(NS, 'circle');
    dot.setAttribute('r', '3.2');
    dot.setAttribute('fill', '#c8102e');
    dot.style.filter = 'drop-shadow(0 0 5px rgba(200,16,46,0.7))';
    svg.appendChild(dot);

    const duration = 2100 + Math.random() * 900;
    const start = performance.now();
    function tick(now){
      const t = Math.min(1, (now - start) / duration);
      // easeInOutCubic
      const e = t < 0.5 ? 4*t*t*t : 1 - Math.pow(-2*t+2, 3) / 2;
      path.setAttribute('stroke-dashoffset', String(len * (1 - e)));
      const pt = path.getPointAtLength(len * e);
      dot.setAttribute('cx', pt.x);
      dot.setAttribute('cy', pt.y);
      // Line opacity: fade in, hold, fade out behind the dot
      let op;
      if (t < 0.15) op = t / 0.15 * 0.55;
      else if (t < 0.7) op = 0.55;
      else op = 0.55 * (1 - (t - 0.7) / 0.3);
      path.style.opacity = String(op);
      if (t < 1) requestAnimationFrame(tick);
      else {
        path.remove(); dot.remove();
        // Arrival ring
        const ring = document.createElementNS(NS, 'circle');
        ring.setAttribute('cx', p2.x); ring.setAttribute('cy', p2.y);
        ring.setAttribute('r', '4');
        ring.setAttribute('fill', 'none');
        ring.setAttribute('stroke', '#c8102e');
        ring.setAttribute('stroke-width', '1.5');
        svg.appendChild(ring);
        const rs = performance.now();
        (function ringTick(n){
          const tt = Math.min(1, (n - rs) / 800);
          ring.setAttribute('r', String(4 + tt * 22));
          ring.style.opacity = String(1 - tt);
          if (tt < 1) requestAnimationFrame(ringTick);
          else ring.remove();
        })(rs);
      }
    }
    requestAnimationFrame(tick);
  }

  // Clear in-flight pulses on map move so arcs don't desync
  map.on('movestart zoomstart', () => { while (svg.firstChild) svg.removeChild(svg.firstChild); });

  let loopTimer = null;
  function loop(){
    spawnPulse();
    loopTimer = setTimeout(loop, 850 + Math.random() * 1100);
  }
  function startAnim(){ if (!loopTimer) loop(); }
  function stopAnim(){ if (loopTimer) { clearTimeout(loopTimer); loopTimer = null; } }

  // Only animate while the map is on-screen
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver(entries => {
      entries.forEach(e => e.isIntersecting ? startAnim() : stopAnim());
    }, { threshold: 0.15 });
    io.observe(el);
  } else {
    startAnim();
  }
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) stopAnim();
    else startAnim();
  });
}

// ================================================
// BIND EVENTS
// ================================================
function bindEvents() {
  // Filters
  $('#filter-origin')?.addEventListener('change',  e => { state.filters.origin = e.target.value; applyFilters(); });
  $('#filter-process')?.addEventListener('change', e => { state.filters.process = e.target.value; applyFilters(); });
  $('#filter-cert')?.addEventListener('change',    e => { state.filters.certification = e.target.value; applyFilters(); });
  $('#filter-wh')?.addEventListener('change',      e => { state.filters.warehouse = e.target.value; applyFilters(); });
  $('#filter-special')?.addEventListener('change', e => { state.filters.special = e.target.value; applyFilters(); });

  let debounce;
  $('#filter-search')?.addEventListener('input', e => {
    clearTimeout(debounce);
    debounce = setTimeout(() => { state.filters.search = e.target.value; applyFilters(); }, 250);
  });

  $('#filter-reset')?.addEventListener('click', () => {
    state.filters = { origin:'', process:'', certification:'', warehouse:'', special:'', search:'' };
    $$('.search-select').forEach(s => s.value = '');
    const si = $('#filter-search'); if (si) si.value = '';
    applyFilters();
  });

  // Quote panel open
  const openPanelBtns = ['#nav-quote-btn','#hero-quote-btn','#quote-float','#mobile-quote-btn','#contact-quote-btn'];
  openPanelBtns.forEach(sel => $(sel)?.addEventListener('click', openPanel));
  $('#qp-close')?.addEventListener('click', closePanel);
  $('#quote-overlay')?.addEventListener('click', closePanel);

  // Form
  $('#quote-form')?.addEventListener('submit', handleSubmit);
  // Show/hide pickup location when the pickup checkbox is toggled
  $('#field-pickup')?.addEventListener('change', updatePickupLocationField);

  // Modal
  $('#modal-close')?.addEventListener('click', closeModal);
  $('#modal-overlay')?.addEventListener('click', e => { if (e.target === e.currentTarget) closeModal(); });

  // Keyboard
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') { closeModal(); closePanel(); }
  });

  // Smooth anchor scroll
  $$('a[href^="#"]').forEach(a => {
    a.addEventListener('click', e => {
      const target = document.querySelector(a.getAttribute('href'));
      if (target) { e.preventDefault(); target.scrollIntoView({ behavior: 'smooth' }); }
    });
  });

  // Mobile hamburger
  const ham = $('#nav-hamburger');
  const mob = $('#mobile-menu');
  if (ham && mob) ham.addEventListener('click', () => mob.classList.toggle('open'));
}
