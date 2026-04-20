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
const FLAGS = {
  'Brazil':'🇧🇷','Colombia':'🇨🇴','Costa Rica':'🇨🇷','Ethiopia':'🇪🇹',
  'Guatemala':'🇬🇹','Honduras':'🇭🇳','Indonesia':'🇮🇩','Kenya':'🇰🇪',
  'Mexico':'🇲🇽','Nicaragua':'🇳🇮','Panama':'🇵🇦','Papua New Guinea':'🇵🇬',
  'Peru':'🇵🇪','Rwanda':'🇷🇼','Tanzania':'🇹🇿',
  'Uganda':'🇺🇬','Blend':'🌍'
};

const CERT_CLASS = {
  'Organic':'cflag-organic','Fair Trade':'cflag-ft',
  'Rainforest Alliance':'cflag-rfa',"Women's Lot":'cflag-womens','Decaf':'cflag-decaf'
};

// ── DOM ────────────────────────────────────────────────────
const $ = (s,c=document) => c.querySelector(s);
const $$ = (s,c=document) => [...c.querySelectorAll(s)];

// ── Init ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initCursor();
  initHeroCanvas();
  initNav();
  buildFilters();
  renderGrid();
  renderQuoteItems();
  bindEvents();
  animateNumbers();
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
  const add = (id, opts) => {
    const sel = $(id); if (!sel) return;
    opts.forEach(o => { const el = document.createElement('option'); el.value = o; el.textContent = o; sel.appendChild(el); });
  };
  add('#filter-origin',  FILTER_OPTIONS.origins);
  add('#filter-process', FILTER_OPTIONS.processes);
  add('#filter-cert',    FILTER_OPTIONS.certifications);
  add('#filter-wh',      FILTER_OPTIONS.warehouses);
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
    btn.addEventListener('click', e => { e.stopPropagation(); toggleQuote(parseInt(btn.dataset.id)); }));
  $$('.ccard', grid).forEach(card =>
    card.addEventListener('click', e => {
      // Don't open the modal if the user clicked a button inside the card
      if (e.target.closest('button')) return;
      openModal(parseInt(card.dataset.id));
    }));

  updateGridButtons();
}

function cardHTML(c) {
  const flag = FLAGS[c.origin] || '';
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
        <div class="ccard-detail ccard-notes" title="${(c.tastingNotes||'').replace(/"/g,'&quot;')}">${fallback(c.tastingNotes)}</div>
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
  $$('.add-quote-btn').forEach(btn => {
    const id = parseInt(btn.dataset.id);
    const inQ = state.quote.some(q => q.id === id);
    btn.classList.toggle('added', inQ);
    btn.textContent = inQ ? 'Added' : 'Add to Quote';
  });
  // Modal button
  const mb = $('#modal-add-btn');
  if (mb && state.activeCoffeeId) {
    const inQ = state.quote.some(q => q.id === state.activeCoffeeId);
    mb.classList.toggle('added', inQ);
    mb.textContent = inQ ? 'In Quote - Remove' : 'Add to Quote';
  }
}

// ================================================
// QUOTE
// ================================================
function toggleQuote(id) {
  const coffee = COFFEES.find(c => c.id === id);
  if (!coffee) return;
  const idx = state.quote.findIndex(q => q.id === id);
  if (idx === -1) {
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
  const flag = FLAGS[c.origin] || '';
  const inQ  = state.quote.some(q => q.id === id);

  $('#modal-flag').textContent  = flag;
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
  addBtn.onclick = () => { toggleQuote(id); };

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
function animateNumbers() {
  $$('[data-target]').forEach(el => {
    const target = parseInt(el.dataset.target);
    const suffix = el.dataset.suffix || '';
    if (isNaN(target)) return;
    let cur = 0;
    const step = Math.ceil(target / 40);
    const timer = setInterval(() => {
      cur = Math.min(cur + step, target);
      el.textContent = cur + suffix;
      if (cur >= target) clearInterval(timer);
    }, 35);
  });
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
    marker.bindTooltip(loc.city, {
      permanent: true,
      direction: 'right',
      offset: [10, 0],
      className: 'r86-map-label'
    });
  });

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
