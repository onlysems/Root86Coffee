/**
 * Root 86 Coffee — Forms + Analytics Relay Worker
 *
 * Three endpoints:
 *   POST /         → form submission → creates a GitHub Issue
 *   POST /track    → first-party analytics event → increments KV counters
 *   GET  /stats    → returns aggregated stats (admin-only, requires X-Analytics-Key)
 *
 * ── Deploy ────────────────────────────────────────────────────────────────
 * Secrets (Worker → Settings → Variables → Secrets):
 *   GH_TOKEN        fine-grained PAT with Contents+Issues: R/W on the repo
 *   ANALYTICS_KEY   any random string (also paste into admin Analytics panel)
 *
 * Bindings (Worker → Settings → Variables → KV Namespace Bindings):
 *   STATS           → your KV namespace (create one called e.g. "r86-stats")
 *
 * ── KV setup (one-time) ──────────────────────────────────────────────────
 *   1. dash.cloudflare.com → Workers & Pages → KV → Create a namespace "r86-stats"
 *   2. Open the Worker → Settings → Variables → KV Namespace Bindings → Add
 *        Variable: STATS    Namespace: r86-stats    → Save
 *   3. Settings → Variables → Secrets → Add
 *        ANALYTICS_KEY = <any random string, 24+ chars>
 *   4. Paste the same ANALYTICS_KEY into admin → Analytics tab (one-time per browser)
 */

const GH_OWNER = 'onlysems';
const GH_REPO  = 'Root86Coffee';

const ALLOWED_ORIGINS = [
  'https://root86coffee.com',
  'https://www.root86coffee.com',
  'https://onlysems.github.io',
  'https://root86coffee.pages.dev',
];

export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin') || '';
    const corsOrigin = ALLOWED_ORIGINS.includes(origin) ? origin : '';
    const cors = {
      'Access-Control-Allow-Origin': corsOrigin || 'null',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, X-Analytics-Key',
      'Access-Control-Max-Age': '86400',
      'Vary': 'Origin',
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: cors });
    }

    const url = new URL(request.url);
    const path = url.pathname;

    if (path === '/track' && request.method === 'POST') {
      return handleTrack(request, env, cors, corsOrigin);
    }
    if (path === '/stats' && request.method === 'GET') {
      return handleStats(request, env, cors);
    }
    // Default: form submission (root path)
    if (request.method === 'POST') {
      return handleForm(request, env, cors, corsOrigin);
    }
    return json({ error: 'Method not allowed' }, 405, cors);
  },
};

// ────────────────────────────────────────────────────────────
// Forms → GitHub Issue (unchanged behavior)
// ────────────────────────────────────────────────────────────
async function handleForm(request, env, cors, corsOrigin) {
  if (!corsOrigin) return json({ error: 'Origin not allowed' }, 403, cors);
  if (!env.GH_TOKEN) return json({ error: 'Worker not configured (missing GH_TOKEN)' }, 500, cors);

  let data;
  try { data = await request.json(); }
  catch { return json({ error: 'Invalid JSON' }, 400, cors); }

  if (data.website) return json({ ok: true }, 200, cors); // honeypot

  const formType = (data.form_type || 'contact').toString().toLowerCase();
  const kindLabel = formType === 'quote' ? 'quote' : 'contact';

  const cap = (v, n) => String(v == null ? '' : v).slice(0, n);
  const name    = cap(data.name, 120) || 'Anonymous';
  const company = cap(data.company, 120);
  const email   = cap(data.email, 200);
  const phone   = cap(data.phone, 60);
  const message = cap(data.message, 5000);
  const address = cap(data.address, 300);
  const notes   = cap(data.notes, 2000);
  const residential = cap(data.residential, 40);
  const payment     = cap(data.payment, 40);
  const pickup      = !!data.pickup;
  const tailgate    = !!data.tailgate;
  const items       = Array.isArray(data.items) ? data.items.slice(0, 200) : [];

  const title = `[${kindLabel}] ${name}${company ? ' — ' + company : ''}`;
  const lines = [];
  lines.push(`**Form:** ${formType}`);
  lines.push(`**Name:** ${md(name)}`);
  if (company) lines.push(`**Company:** ${md(company)}`);
  if (email)   lines.push(`**Email:** ${md(email)}`);
  if (phone)   lines.push(`**Phone:** ${md(phone)}`);
  if (address) lines.push(`**Address:** ${md(address)}`);
  if (residential) lines.push(`**Type:** ${md(residential)}`);
  if (payment)     lines.push(`**Payment:** ${md(payment)}`);
  if (formType === 'quote') {
    lines.push(`**Pickup:** ${pickup ? 'Yes' : 'No'}`);
    lines.push(`**Tailgate:** ${tailgate ? 'Yes' : 'No'}`);
  }
  lines.push(`**Submitted:** ${new Date().toISOString()}`);
  lines.push('');
  if (message) { lines.push('---',''); lines.push(md(message),''); }
  if (notes)   { lines.push('**Notes:**',''); lines.push(md(notes),''); }
  if (items.length) {
    lines.push('---','');
    lines.push(`**Quote items (${items.length}):**`,'');
    for (const it of items) {
      const nm = md(cap(it.name, 200));
      const qty = Number(it.qty) || 1;
      const originStr = md(cap(it.origin, 80));
      const originPart = originStr ? ' (' + originStr + ')' : '';
      lines.push('- ' + nm + originPart + ' x ' + qty);
    }
  }

  const body = lines.join('\n');
  const ghRes = await fetch(
    `https://api.github.com/repos/${GH_OWNER}/${GH_REPO}/issues`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.GH_TOKEN}`,
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'Content-Type': 'application/json',
        'User-Agent': 'r86-forms-worker',
      },
      body: JSON.stringify({ title, body, labels: ['submission', kindLabel] }),
    }
  );
  if (!ghRes.ok) {
    const txt = await ghRes.text();
    console.error('GitHub API', ghRes.status, txt);
    return json({ error: 'Upstream failed', status: ghRes.status }, 502, cors);
  }
  const issue = await ghRes.json();
  try {
    await fetch(
      `https://api.github.com/repos/${GH_OWNER}/${GH_REPO}/issues/${issue.number}/labels`,
      { method: 'POST',
        headers: {
          'Authorization': `Bearer ${env.GH_TOKEN}`,
          'Accept': 'application/vnd.github+json',
          'X-GitHub-Api-Version': '2022-11-28',
          'Content-Type': 'application/json',
          'User-Agent': 'r86-forms-worker',
        },
        body: JSON.stringify({ labels: ['submission', kindLabel] }),
      }
    );
  } catch(e) { console.error('Label apply threw', e); }

  // Fire-and-forget: track the form submission as an event too
  if (env.STATS) {
    try { await bumpEvent(env, kindLabel + '_submit'); } catch(e) {}
  }
  return json({ ok: true, number: issue.number, url: issue.html_url }, 200, cors);
}

// ────────────────────────────────────────────────────────────
// /track  — first-party analytics ingest
// ────────────────────────────────────────────────────────────
async function handleTrack(request, env, cors, corsOrigin) {
  if (!corsOrigin) return json({ error: 'Origin not allowed' }, 403, cors);
  if (!env.STATS)  return json({ ok: true, noop: 'STATS not bound' }, 200, cors);

  let data;
  try { data = await request.json(); }
  catch { return json({ error: 'Invalid JSON' }, 400, cors); }

  const type = String(data.type || '').toLowerCase().slice(0, 32);
  const today = isoDay();

  const writes = [];
  if (type === 'pageview') {
    const path = cleanPath(data.path || '/');
    writes.push(bumpKey(env, 'pv:' + today));                  // total/day
    writes.push(bumpKey(env, 'pv:' + today + ':' + path));     // path/day
    const ref = cleanHost(data.referrer || '');
    if (ref) writes.push(bumpKey(env, 'ref:' + today + ':' + ref));
  } else if (type === 'coffee_view') {
    const id = String(parseInt(data.coffeeId) || 0);
    if (id !== '0') {
      writes.push(bumpKey(env, 'coffee:' + id));               // all-time
      writes.push(bumpKey(env, 'coffee:' + id + ':' + today)); // per-day
    }
  } else if (type === 'quote_submit' || type === 'contact_submit') {
    writes.push(bumpEvent(env, type));
  } else {
    return json({ error: 'Unknown type' }, 400, cors);
  }
  try { await Promise.all(writes); } catch(e) { console.error('KV write', e); }
  return new Response(null, { status: 204, headers: cors });
}

// ────────────────────────────────────────────────────────────
// /stats  — admin reader
// ────────────────────────────────────────────────────────────
async function handleStats(request, env, cors) {
  const key = request.headers.get('X-Analytics-Key') || '';
  if (!env.ANALYTICS_KEY || key !== env.ANALYTICS_KEY) {
    return json({ error: 'Unauthorized' }, 401, cors);
  }
  if (!env.STATS) return json({ error: 'STATS not bound' }, 500, cors);

  const url = new URL(request.url);
  const days = Math.min(90, Math.max(1, parseInt(url.searchParams.get('days')) || 30));

  const dayList = lastNDays(days);

  // 1. Daily pageview totals
  const pvKeys = dayList.map(d => 'pv:' + d);
  const pvVals = await Promise.all(pvKeys.map(k => env.STATS.get(k)));
  const daily = dayList.map((d, i) => ({ day: d, pv: parseInt(pvVals[i]) || 0 }));

  // 2. Path breakdown (top paths in range) — list per-day path keys
  const pathCounts = {};
  for (const d of dayList) {
    const list = await env.STATS.list({ prefix: 'pv:' + d + ':' });
    await Promise.all(list.keys.map(async k => {
      const p = k.name.slice(('pv:' + d + ':').length);
      const v = parseInt(await env.STATS.get(k.name)) || 0;
      pathCounts[p] = (pathCounts[p] || 0) + v;
    }));
  }

  // 3. Referrer breakdown
  const refCounts = {};
  for (const d of dayList) {
    const list = await env.STATS.list({ prefix: 'ref:' + d + ':' });
    await Promise.all(list.keys.map(async k => {
      const r = k.name.slice(('ref:' + d + ':').length);
      const v = parseInt(await env.STATS.get(k.name)) || 0;
      refCounts[r] = (refCounts[r] || 0) + v;
    }));
  }

  // 4. Coffee views (all-time)
  const coffeeList = await env.STATS.list({ prefix: 'coffee:' });
  const coffeeCounts = {};
  await Promise.all(coffeeList.keys.map(async k => {
    // only accept 'coffee:<id>' (no extra colon → all-time)
    const rest = k.name.slice('coffee:'.length);
    if (rest.indexOf(':') !== -1) return;
    coffeeCounts[rest] = parseInt(await env.STATS.get(k.name)) || 0;
  }));

  // 5. Events (range)
  const events = { quote_submit: 0, contact_submit: 0 };
  for (const d of dayList) {
    for (const ev of Object.keys(events)) {
      const v = parseInt(await env.STATS.get('event:' + ev + ':' + d)) || 0;
      events[ev] += v;
    }
  }

  return json({
    ok: true,
    range_days: days,
    daily,
    total_pageviews: daily.reduce((a, x) => a + x.pv, 0),
    paths: pathCounts,
    referrers: refCounts,
    coffees: coffeeCounts,
    events,
  }, 200, cors);
}

// ────────────────────────────────────────────────────────────
// Helpers
// ────────────────────────────────────────────────────────────
async function bumpKey(env, key) {
  const cur = parseInt(await env.STATS.get(key)) || 0;
  await env.STATS.put(key, String(cur + 1));
}
async function bumpEvent(env, name) {
  await bumpKey(env, 'event:' + name + ':' + isoDay());
}
function isoDay(d) {
  d = d || new Date();
  return d.toISOString().slice(0, 10);
}
function lastNDays(n) {
  const out = [];
  const now = new Date();
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(now); d.setUTCDate(d.getUTCDate() - i);
    out.push(isoDay(d));
  }
  return out;
}
function cleanPath(p) {
  try {
    p = String(p).slice(0, 120);
    const u = new URL(p, 'https://x');
    return u.pathname;
  } catch { return '/'; }
}
function cleanHost(r) {
  try {
    if (!r) return '';
    const u = new URL(r);
    return u.host.toLowerCase().slice(0, 80);
  } catch { return ''; }
}
function json(obj, status, cors) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { ...cors, 'Content-Type': 'application/json' },
  });
}
function md(s) {
  return String(s).replace(/[<]/g, '&lt;').replace(/[>]/g, '&gt;');
}
