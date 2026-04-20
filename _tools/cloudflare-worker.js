/**
 * Root 86 Coffee — Forms Relay Worker
 *
 * Receives form POSTs from the Root 86 website and creates a GitHub Issue
 * in onlysems/Root86Coffee for each submission. The admin "Inbox" tab reads
 * those issues back via the GitHub API.
 *
 * ── Deploy ────────────────────────────────────────────────────────────────
 * 1. https://dash.cloudflare.com → Workers & Pages → Create → Start with template → "Hello World"
 * 2. Name it e.g. "r86-forms" → Deploy
 * 3. Click into the Worker → Edit Code → paste this entire file → Save & Deploy
 * 4. Settings → Variables → "Add variable" under **Secrets**:
 *      Name:  GH_TOKEN
 *      Value: (fine-grained PAT with Contents: write + Issues: write on onlysems/Root86Coffee)
 *    Click Encrypt → Save
 * 5. Copy the Worker URL (looks like https://r86-forms.<yourname>.workers.dev)
 * 6. Paste that URL into js/coffees.js SITE_SETTINGS.formEndpoint
 *
 * ── PAT permissions needed ────────────────────────────────────────────────
 * Fine-grained PAT, single repo (onlysems/Root86Coffee):
 *   - Contents: Read and write  (already have)
 *   - Issues:   Read and write  (NEW - needed to create/list/close issues)
 *   - Metadata: Read-only       (auto)
 *
 * If your existing admin PAT doesn't have Issues permission, create a second
 * token just for the Worker, or update the existing token.
 */

const GH_OWNER = 'onlysems';
const GH_REPO  = 'Root86Coffee';

// Only accept submissions from these origins. Reject everything else so
// randos can't spam your inbox by POSTing directly to the Worker.
const ALLOWED_ORIGINS = [
  'https://root86coffee.com',
  'https://www.root86coffee.com',
  'https://onlysems.github.io',
  'https://root86coffee.pages.dev',
  // Add your local dev origin here if you need to test locally, e.g.:
  // 'http://localhost:8080',
];

export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin') || '';
    const corsOrigin = ALLOWED_ORIGINS.includes(origin) ? origin : '';
    const cors = {
      'Access-Control-Allow-Origin': corsOrigin || 'null',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
      'Access-Control-Max-Age': '86400',
      'Vary': 'Origin',
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: cors });
    }
    if (request.method !== 'POST') {
      return json({ error: 'Method not allowed' }, 405, cors);
    }
    if (!corsOrigin) {
      return json({ error: 'Origin not allowed' }, 403, cors);
    }
    if (!env.GH_TOKEN) {
      return json({ error: 'Worker not configured (missing GH_TOKEN secret)' }, 500, cors);
    }

    let data;
    try {
      data = await request.json();
    } catch {
      return json({ error: 'Invalid JSON' }, 400, cors);
    }

    // Honeypot: if a bot filled the hidden "website" field, pretend success
    // and drop the submission.
    if (data.website) {
      return json({ ok: true }, 200, cors);
    }

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
    if (message) {
      lines.push('---');
      lines.push('');
      lines.push(md(message));
      lines.push('');
    }
    if (notes) {
      lines.push('**Notes:**');
      lines.push('');
      lines.push(md(notes));
      lines.push('');
    }
    if (items.length) {
      lines.push('---');
      lines.push('');
      lines.push(`**Quote items (${items.length}):**`);
      lines.push('');
      for (const it of items) {
        const nm = md(cap(it.name, 200));
        const qty = Number(it.qty) || 1;
        const origin = md(cap(it.origin, 80));
        lines.push(`- ${nm} ${origin ? `(${origin})` : ''} × ${qty}`);
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
        body: JSON.stringify({
          title,
          body,
          labels: ['submission', kindLabel],
        }),
      }
    );

    if (!ghRes.ok) {
      const txt = await ghRes.text();
      console.error('GitHub API', ghRes.status, txt);
      return json({ error: 'Upstream failed', status: ghRes.status }, 502, cors);
    }

    const issue = await ghRes.json();
    return json({ ok: true, number: issue.number, url: issue.html_url }, 200, cors);
  },
};

function json(obj, status, cors) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { ...cors, 'Content-Type': 'application/json' },
  });
}

function md(s) {
  // Escape < > so raw HTML can't sneak into issue markdown
  return String(s).replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
