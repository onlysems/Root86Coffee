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
});

// ================================================
// CURSOR
// ================================================
function initCursor() {
  const dot  = $('#cursor-dot');
  const ring = $('#cursor-ring');
  if (!dot || !ring) return;

  let mouseX = 0, mouseY = 0, ringX = 0, ringY = 0;

  document.addEventListener('mousemove', e => {
    mouseX = e.clientX; mouseY = e.clientY;
    dot.style.left = mouseX + 'px';
    dot.style.top  = mouseY + 'px';
  });

  // Smooth ring follow
  function animateRing() {
    ringX += (mouseX - ringX) * 0.12;
    ringY += (mouseY - ringY) * 0.12;
    ring.style.left = ringX + 'px';
    ring.style.top  = ringY + 'px';
    requestAnimationFrame(animateRing);
  }
  animateRing();

  // Hover expand
  document.querySelectorAll('a, button, [role="button"]').forEach(el => {
    el.addEventListener('mouseenter', () => ring.classList.add('hover'));
    el.addEventListener('mouseleave', () => ring.classList.remove('hover'));
  });
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
  const fallback = v => (v && String(v).trim()) ? v : '<span class="ccard-na">N/A</span>';
  const certFlags = c.certifications.map(cert =>
    `<span class="cflag ${CERT_CLASS[cert] || ''}">${cert}</span>`).join('');
  const specialBadges = [
    c.favourite ? `<span class="cflag cflag-fav">★ R86 Favourite</span>` : '',
    c.onSale ? `<span class="cflag cflag-sale">On Sale</span>` : ''
  ].join('');

  return `
    <div class="ccard${!c.available || c.soldOut ? ' sold-out' : ''}" data-id="${c.id}">
      <div class="ccard-flags">
        <span class="cflag cflag-origin">${c.origin}</span>
        ${specialBadges}
        ${certFlags}
      </div>
      <div class="ccard-name">${flag ? `<span class="ccard-flag">${flag}</span>` : ''}${c.name}</div>
      <div class="ccard-details">
        <div class="ccard-detail"><strong>Process:</strong> ${fallback(c.process)}</div>
        <div class="ccard-detail"><strong>Region:</strong> ${fallback(c.region)}</div>
        <div class="ccard-detail"><strong>Bag Weight:</strong> ${c.bagWeight ? c.bagWeight + ' lbs' : '<span class="ccard-na">N/A</span>'}</div>
        <div class="ccard-detail ccard-notes" data-notes="${(c.tastingNotes||'').replace(/"/g,'&quot;')}">${fallback(c.tastingNotes)}</div>
      </div>
      <div class="ccard-stock${c.available ? '' : ' out'}">
        ${c.available
          ? `<span class="stock-label">In stock</span>${(c.warehouses||[]).map(w => `<span class="stock-chip">${w.split(',')[0]}</span>`).join('')}`
          : `<span class="stock-label">Out of stock</span>`}
      </div>
      <div class="ccard-footer">
        <button class="more-info-btn" data-id="${c.id}">More Info</button>
        <button class="add-quote-btn${inQ ? ' added' : ''}${!c.available ? '' : ''}" data-id="${c.id}"
          ${!c.available ? 'disabled' : ''}>
          ${inQ ? 'Added' : 'Add to Quote'}
        </button>
      </div>
    </div>`;
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
      showToast(`Can't mix warehouses — your quote ships from ${currentLabel}, but this coffee is only at ${newLabel}.`, true);
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

  // Restore cursor behaviour inside the map (Leaflet sets cursor:grab)
  el.addEventListener('mouseenter', () => {
    const dot  = document.getElementById('cursor-dot');
    const ring = document.getElementById('cursor-ring');
    if (dot)  dot.style.opacity  = '0';
    if (ring) ring.style.opacity = '0';
  });
  el.addEventListener('mouseleave', () => {
    const dot  = document.getElementById('cursor-dot');
    const ring = document.getElementById('cursor-ring');
    if (dot)  dot.style.opacity  = '1';
    if (ring) ring.style.opacity = '0.5';
  });

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
