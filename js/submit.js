/* ============================================================
   Root 86 Coffee - Form submission helper
   Posts form data to the Cloudflare Worker which creates a
   GitHub Issue. Admin -> Inbox reads those issues back.
   Falls back to EmailJS (if configured) then mailto on error.
   ============================================================ */

async function submitForm(payload) {
  const settings = (typeof SITE_SETTINGS !== 'undefined') ? SITE_SETTINGS : {};
  const endpoint = settings.formEndpoint;

  // Preferred path: Cloudflare Worker -> GitHub Issue
  if (endpoint && /^https?:\/\//.test(endpoint)) {
    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        const data = await res.json().catch(() => ({}));
        return { ok: true, via: 'worker', issue: data.number };
      }
      console.warn('Form endpoint returned', res.status);
    } catch (err) {
      console.warn('Form endpoint failed:', err);
    }
  }

  // Fallback: EmailJS
  if (
    typeof emailjs !== 'undefined'
    && settings.emailjsPublicKey
    && settings.emailjsPublicKey !== 'YOUR_PUBLIC_KEY'
  ) {
    try {
      await emailjs.send(
        settings.emailjsServiceId,
        settings.emailjsTemplateId,
        flattenForEmailJS(payload)
      );
      return { ok: true, via: 'emailjs' };
    } catch (err) {
      console.warn('EmailJS failed:', err);
    }
  }

  // Last resort: open mail client
  const subject = encodeURIComponent(
    `Website ${payload.form_type || 'enquiry'} - ${payload.name || ''}`
  );
  const body = encodeURIComponent(buildMailtoBody(payload));
  const to = settings.email || 'root86coffee@gmail.com';
  window.location.href = `mailto:${to}?subject=${subject}&body=${body}`;
  return { ok: true, via: 'mailto' };
}

function flattenForEmailJS(p) {
  const out = {
    form_type: p.form_type || 'contact',
    name: p.name || '',
    company: p.company || 'N/A',
    email: p.email || '',
    phone: p.phone || 'N/A',
    message: p.message || '',
    address: p.address || '',
    notes: p.notes || '',
    submitted_at: new Date().toLocaleString('en-CA', { timeZone: 'America/Vancouver' })
  };
  if (Array.isArray(p.items)) {
    out.coffee_count = p.items.length;
    out.coffee_list  = p.items.map(it => `- ${it.name} x ${it.qty || 1}`).join('\n');
  }
  return out;
}

function buildMailtoBody(p) {
  const lines = [];
  lines.push(`Form: ${p.form_type || 'contact'}`);
  lines.push(`Name: ${p.name || ''}`);
  if (p.company) lines.push(`Company: ${p.company}`);
  if (p.email)   lines.push(`Email: ${p.email}`);
  if (p.phone)   lines.push(`Phone: ${p.phone}`);
  if (p.address) lines.push(`Address: ${p.address}`);
  lines.push('');
  if (p.message) lines.push(p.message);
  if (Array.isArray(p.items) && p.items.length) {
    lines.push('');
    lines.push(`Coffees (${p.items.length}):`);
    for (const it of p.items) lines.push(`- ${it.name} x ${it.qty || 1}`);
  }
  if (p.notes) { lines.push(''); lines.push(`Notes: ${p.notes}`); }
  return lines.join('\n');
}
