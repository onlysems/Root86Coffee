/* ============================================================
   ROOT 86 COFFEE — Main Application
   ============================================================ */

// ── State ──────────────────────────────────────────────────
const state = {
  quote: [],
  filters: { origin: '', process: '', certification: '', warehouse: '', search: '' },
  filteredCoffees: [...COFFEES],
  activeCoffeeId: null
};

// ── Emoji flags ─────────────────────────────────────────────
const FLAGS = {
  'Brazil': '🇧🇷', 'Colombia': '🇨🇴', 'Costa Rica': '🇨🇷',
  'Ethiopia': '🇪🇹', 'Guatemala': '🇬🇹', 'Honduras': '🇭🇳',
  'Indonesia': '🇮🇩', 'Kenya': '🇰🇪', 'Mexico': '🇲🇽',
  'Peru': '🇵🇪', 'Rwanda': '🇷🇼', 'Tanzania': '🇹🇿',
  'Uganda': '🇺🇬', 'Blend': '🌍'
};

const CERT_CLASSES = {
  'Organic': 'organic', 'Fair Trade': 'fair-trade',
  'Rainforest Alliance': 'rfa', 'Women\'s Lot': 'womens', 'Decaf': 'decaf'
};

// ── DOM helpers ──────────────────────────────────────────────
const $ = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

// ── Initialise ───────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  buildFilters();
  renderCoffeeGrid();
  renderQuoteList();
  bindEvents();
  animateHeroNumbers();
});

// ── Build filter dropdowns ────────────────────────────────────
function buildFilters() {
  const populateSelect = (id, options) => {
    const sel = $(id);
    if (!sel) return;
    options.forEach(opt => {
      const el = document.createElement('option');
      el.value = opt; el.textContent = opt;
      sel.appendChild(el);
    });
  };
  populateSelect('#filter-origin',  FILTER_OPTIONS.origins);
  populateSelect('#filter-process', FILTER_OPTIONS.processes);
  populateSelect('#filter-cert',    FILTER_OPTIONS.certifications);
  populateSelect('#filter-wh',      FILTER_OPTIONS.warehouses);
}

// ── Apply filters ─────────────────────────────────────────────
function applyFilters() {
  const { origin, process, certification, warehouse, search } = state.filters;
  state.filteredCoffees = COFFEES.filter(c => {
    if (origin && c.origin !== origin) return false;
    if (process && c.process !== process) return false;
    if (certification && !c.certifications.includes(certification)) return false;
    if (warehouse && !c.warehouses.includes(warehouse)) return false;
    if (search) {
      const q = search.toLowerCase();
      if (
        !c.name.toLowerCase().includes(q) &&
        !c.origin.toLowerCase().includes(q) &&
        !c.region.toLowerCase().includes(q) &&
        !c.tastingNotes.toLowerCase().includes(q)
      ) return false;
    }
    return true;
  });
  renderCoffeeGrid();
}

// ── Render coffee grid ────────────────────────────────────────
function renderCoffeeGrid() {
  const grid = $('#coffee-grid');
  const countEl = $('#results-count');
  if (!grid) return;

  const count = state.filteredCoffees.length;
  if (countEl) countEl.innerHTML = `Showing <span>${count}</span> coffee${count !== 1 ? 's' : ''}`;

  if (count === 0) {
    grid.innerHTML = `
      <div class="no-results">
        <div class="no-results-icon">☕</div>
        <h3>No coffees match your filters</h3>
        <p style="color:var(--cream-muted);font-size:0.85rem;margin-top:0.5rem;">Try adjusting or resetting your filters</p>
      </div>`;
    return;
  }

  grid.innerHTML = state.filteredCoffees.map(c => coffeeCardHTML(c)).join('');

  // Bind card events
  $$('.coffee-info-btn', grid).forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      openModal(parseInt(btn.dataset.id));
    });
  });
  $$('.coffee-add-btn', grid).forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      const id = parseInt(btn.dataset.id);
      toggleQuoteItem(id);
    });
  });
  $$('.coffee-card', grid).forEach(card => {
    card.addEventListener('click', () => openModal(parseInt(card.dataset.id)));
  });

  updateAddButtons();
}

function coffeeCardHTML(c) {
  const flag = FLAGS[c.origin] || '☕';
  const inQuote = state.quote.some(q => q.id === c.id);
  return `
    <div class="coffee-card${!c.available ? ' unavailable' : ''}" data-id="${c.id}">
      <div class="coffee-card-top">
        <span class="coffee-origin-flag">${flag}</span>
        <span class="coffee-available-dot${!c.available ? ' unavailable' : ''}" title="${c.available ? 'In stock' : 'Out of stock'}"></span>
      </div>
      <h3 class="coffee-name">${c.name}</h3>
      <p class="coffee-region">${c.region} · ${c.origin}</p>
      <div class="coffee-badges">
        <span class="badge badge-process">${c.process}</span>
        ${c.certifications.map(cert => `<span class="badge badge-cert ${CERT_CLASSES[cert] || ''}">${cert}</span>`).join('')}
      </div>
      <p class="coffee-weight">Bag: <span>${c.bagWeight} lbs</span></p>
      <p class="coffee-tasting">${c.tastingNotes}</p>
      <div class="coffee-actions">
        <button class="coffee-info-btn" data-id="${c.id}">More Info</button>
        <button class="coffee-add-btn ${inQuote ? 'added' : ''}" data-id="${c.id}">
          ${inQuote ? '✓ Added — Remove' : '+ Add to Quote'}
        </button>
      </div>
    </div>`;
}

// ── Toggle quote item ─────────────────────────────────────────
function toggleQuoteItem(id) {
  const coffee = COFFEES.find(c => c.id === id);
  if (!coffee) return;
  const idx = state.quote.findIndex(q => q.id === id);
  if (idx === -1) {
    state.quote.push(coffee);
    showToast(`${coffee.name.split(' ').slice(0,3).join(' ')} added to quote`, 'success');
  } else {
    state.quote.splice(idx, 1);
    showToast(`Removed from quote`, 'removed');
  }
  renderQuoteList();
  updateAddButtons();
  updateQuoteBar();
  updateNavCount();
}

function updateAddButtons() {
  $$('.coffee-add-btn').forEach(btn => {
    const id = parseInt(btn.dataset.id);
    const inQuote = state.quote.some(q => q.id === id);
    btn.className = `coffee-add-btn ${inQuote ? 'added' : ''}`;
    btn.textContent = inQuote ? '✓ Added — Remove' : '+ Add to Quote';
  });
  // Also update modal button
  const modalBtn = $('#modal-add-btn');
  if (modalBtn && state.activeCoffeeId) {
    const inQuote = state.quote.some(q => q.id === state.activeCoffeeId);
    modalBtn.className = `modal-add-btn${inQuote ? ' added' : ''}`;
    modalBtn.textContent = inQuote ? '✓ In Quote — Remove' : '+ Add to Quote';
  }
}

// ── Render quote list ─────────────────────────────────────────
function renderQuoteList() {
  const list = $('#quote-items');
  const countEl = $('#quote-count');
  if (!list) return;

  if (countEl) countEl.textContent = `${state.quote.length} item${state.quote.length !== 1 ? 's' : ''}`;

  if (state.quote.length === 0) {
    list.innerHTML = `
      <div class="quote-empty">
        <div class="quote-empty-icon">📋</div>
        <p>Your quote is empty.<br>Browse coffees above and add them here.</p>
      </div>`;
    return;
  }

  list.innerHTML = state.quote.map(c => `
    <div class="quote-item">
      <div class="quote-item-info">
        <div class="quote-item-name">${c.name}</div>
        <div class="quote-item-detail">${c.origin} · ${c.process} · ${c.bagWeight} lbs</div>
      </div>
      <button class="quote-item-remove" data-id="${c.id}" title="Remove">✕</button>
    </div>`).join('');

  $$('.quote-item-remove', list).forEach(btn => {
    btn.addEventListener('click', () => toggleQuoteItem(parseInt(btn.dataset.id)));
  });
}

// ── Quote sticky bar ──────────────────────────────────────────
function updateQuoteBar() {
  const bar = $('#quote-bar');
  const countEl = $('#quote-bar-count');
  const textEl = $('#quote-bar-text');
  if (!bar) return;
  if (state.quote.length > 0) {
    bar.classList.add('visible');
    if (countEl) countEl.textContent = state.quote.length;
    if (textEl) textEl.innerHTML = `<strong>${state.quote.length} coffee${state.quote.length !== 1 ? 's' : ''}</strong> in your quote`;
  } else {
    bar.classList.remove('visible');
  }
}

function updateNavCount() {
  const el = $('#nav-quote-count');
  if (!el) return;
  el.textContent = state.quote.length;
  el.style.display = state.quote.length > 0 ? 'inline-flex' : 'none';
}

// ── Modal ─────────────────────────────────────────────────────
function openModal(id) {
  const coffee = COFFEES.find(c => c.id === id);
  if (!coffee) return;
  state.activeCoffeeId = id;
  const overlay = $('#modal-overlay');
  const flag = FLAGS[coffee.origin] || '☕';
  const inQuote = state.quote.some(q => q.id === id);

  $('#modal-flag').textContent = flag;
  $('#modal-name').textContent = coffee.name;
  $('#modal-region').textContent = `${coffee.region} · ${coffee.origin}`;
  $('#modal-process').textContent = coffee.process;
  $('#modal-altitude').textContent = coffee.altitude;
  $('#modal-variety').textContent = coffee.variety;
  $('#modal-grade').textContent = coffee.grade;
  $('#modal-weight').textContent = `${coffee.bagWeight} lbs`;
  $('#modal-desc').textContent = coffee.description;

  const badgesEl = $('#modal-badges');
  badgesEl.innerHTML = [
    `<span class="badge badge-process">${coffee.process}</span>`,
    ...coffee.certifications.map(cert => `<span class="badge badge-cert ${CERT_CLASSES[cert] || ''}">${cert}</span>`)
  ].join('');

  const notesEl = $('#modal-tasting-notes');
  notesEl.innerHTML = coffee.tastingNotes.split(',').map(n =>
    `<span class="tasting-note">${n.trim()}</span>`).join('');

  const whEl = $('#modal-warehouses');
  whEl.innerHTML = coffee.warehouses.map(w =>
    `<span class="warehouse-badge"><span class="warehouse-dot"></span>${w}</span>`).join('');

  const addBtn = $('#modal-add-btn');
  addBtn.className = `modal-add-btn${inQuote ? ' added' : ''}`;
  addBtn.textContent = inQuote ? '✓ In Quote — Remove' : '+ Add to Quote';
  addBtn.onclick = () => { toggleQuoteItem(id); };

  overlay.classList.add('active');
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  const overlay = $('#modal-overlay');
  overlay.classList.remove('active');
  document.body.style.overflow = '';
  state.activeCoffeeId = null;
}

// ── Toast ─────────────────────────────────────────────────────
function showToast(message, type = 'success') {
  const container = $('#toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span class="toast-icon"></span><span>${message}</span>`;
  container.appendChild(toast);
  requestAnimationFrame(() => { toast.classList.add('visible'); });
  setTimeout(() => {
    toast.classList.remove('visible');
    setTimeout(() => toast.remove(), 400);
  }, 3000);
}

// ── Quote form submit ─────────────────────────────────────────
async function handleQuoteSubmit(e) {
  e.preventDefault();
  if (state.quote.length === 0) {
    showToast('Please add at least one coffee to your quote', 'removed');
    return;
  }

  const btn = $('#form-submit');
  btn.disabled = true;
  btn.textContent = 'Sending...';
  btn.classList.add('loading');

  const coffeeList = state.quote.map(c =>
    `• ${c.name} (${c.bagWeight} lbs, ${c.process})`).join('\n');

  const data = {
    company: $('#field-company').value,
    contact: $('#field-contact').value,
    phone: $('#field-phone').value,
    email: $('#field-email').value,
    address: $('#field-address').value,
    residential: $('#field-residential').value,
    payment: $('#field-payment').value,
    pickup: $('#field-pickup').checked,
    tailgate: $('#field-tailgate').checked,
    notes: $('#field-notes').value,
    coffees: coffeeList,
    coffeeCount: state.quote.length
  };

  // ── Try EmailJS first, fall back to mailto ──
  try {
    if (typeof emailjs !== 'undefined' &&
        SITE_SETTINGS.emailjsServiceId !== 'YOUR_SERVICE_ID') {
      await emailjs.send(
        SITE_SETTINGS.emailjsServiceId,
        SITE_SETTINGS.emailjsTemplateId,
        {
          to_email: SITE_SETTINGS.email,
          from_name: data.contact,
          from_company: data.company,
          from_email: data.email,
          from_phone: data.phone,
          address: data.address,
          residential: data.residential,
          payment: data.payment,
          pickup: data.pickup ? 'Yes' : 'No',
          tailgate: data.tailgate ? 'Yes' : 'No',
          notes: data.notes || 'None',
          coffee_list: data.coffees,
          coffee_count: data.coffeeCount
        },
        SITE_SETTINGS.emailjsPublicKey
      );
      showSuccess();
    } else {
      // Fallback: mailto
      const subject = encodeURIComponent(`Quote Request — Root 86 Coffee (${data.coffeeCount} coffees)`);
      const body = encodeURIComponent(
        `QUOTE REQUEST — ROOT 86 COFFEE\n` +
        `${'─'.repeat(40)}\n\n` +
        `Company: ${data.company}\n` +
        `Contact: ${data.contact}\n` +
        `Phone: ${data.phone}\n` +
        `Email: ${data.email}\n` +
        `Address: ${data.address}\n` +
        `Residential/Commercial: ${data.residential}\n` +
        `Payment Method: ${data.payment}\n` +
        `Pickup: ${data.pickup ? 'Yes' : 'No'}\n` +
        `Power Tailgate: ${data.tailgate ? 'Yes' : 'No'}\n` +
        `Notes: ${data.notes || 'None'}\n\n` +
        `COFFEES REQUESTED (${data.coffeeCount}):\n` +
        `${'─'.repeat(40)}\n` +
        `${data.coffees}`
      );
      window.location.href = `mailto:${SITE_SETTINGS.email}?subject=${subject}&body=${body}`;
      showSuccess();
    }
  } catch (err) {
    console.error(err);
    btn.disabled = false;
    btn.textContent = 'Send Quote Request';
    btn.classList.remove('loading');
    showToast('Something went wrong. Please try again or email us directly.', 'removed');
  }
}

function showSuccess() {
  $('#quote-form').style.display = 'none';
  $('#form-success').style.display = 'block';
  state.quote = [];
  renderQuoteList();
  updateQuoteBar();
  updateNavCount();
  updateAddButtons();
}

// ── Hero counter animation ─────────────────────────────────────
function animateHeroNumbers() {
  $$('.hero-stat-num').forEach(el => {
    const target = parseInt(el.dataset.target);
    if (isNaN(target)) return;
    let current = 0;
    const step = Math.ceil(target / 50);
    const timer = setInterval(() => {
      current = Math.min(current + step, target);
      el.textContent = current + (el.dataset.suffix || '');
      if (current >= target) clearInterval(timer);
    }, 30);
  });
}

// ── Navbar scroll behaviour ─────────────────────────────────────
function handleNavScroll() {
  const nav = $('#main-nav');
  if (nav) nav.classList.toggle('scrolled', window.scrollY > 60);
}

// ── Bind all events ────────────────────────────────────────────
function bindEvents() {
  // Nav scroll
  window.addEventListener('scroll', handleNavScroll, { passive: true });

  // Filters
  $('#filter-origin')?.addEventListener('change', e => { state.filters.origin = e.target.value; applyFilters(); });
  $('#filter-process')?.addEventListener('change', e => { state.filters.process = e.target.value; applyFilters(); });
  $('#filter-cert')?.addEventListener('change', e => { state.filters.certification = e.target.value; applyFilters(); });
  $('#filter-wh')?.addEventListener('change', e => { state.filters.warehouse = e.target.value; applyFilters(); });

  const searchInput = $('#filter-search');
  if (searchInput) {
    let debounceTimer;
    searchInput.addEventListener('input', e => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        state.filters.search = e.target.value;
        applyFilters();
      }, 250);
    });
  }

  // Filter reset
  $('#filter-reset')?.addEventListener('click', () => {
    state.filters = { origin: '', process: '', certification: '', warehouse: '', search: '' };
    $$('.filter-select').forEach(s => s.value = '');
    const searchEl = $('#filter-search');
    if (searchEl) searchEl.value = '';
    applyFilters();
  });

  // Modal close
  $('#modal-close')?.addEventListener('click', closeModal);
  $('#modal-overlay')?.addEventListener('click', e => { if (e.target === e.currentTarget) closeModal(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

  // Quote form
  $('#quote-form')?.addEventListener('submit', handleQuoteSubmit);

  // Quote bar buttons
  $('#quote-bar-go')?.addEventListener('click', () => {
    document.querySelector('#quote-section')?.scrollIntoView({ behavior: 'smooth' });
  });
  $('#quote-bar-clear')?.addEventListener('click', () => {
    state.quote = [];
    renderQuoteList(); updateQuoteBar(); updateNavCount(); updateAddButtons();
    showToast('Quote cleared', 'removed');
  });

  // Nav CTA scroll
  $('#nav-quote-btn')?.addEventListener('click', () => {
    document.querySelector('#quote-section')?.scrollIntoView({ behavior: 'smooth' });
  });

  // Smooth scroll for all anchor links
  $$('a[href^="#"]').forEach(a => {
    a.addEventListener('click', e => {
      const target = document.querySelector(a.getAttribute('href'));
      if (target) { e.preventDefault(); target.scrollIntoView({ behavior: 'smooth' }); }
    });
  });

  // Mobile hamburger (simple toggle)
  const hamburger = $('#nav-hamburger');
  const mobileMenu = $('#mobile-menu');
  if (hamburger && mobileMenu) {
    hamburger.addEventListener('click', () => {
      const open = mobileMenu.classList.toggle('open');
      hamburger.setAttribute('aria-expanded', open);
    });
  }
}
