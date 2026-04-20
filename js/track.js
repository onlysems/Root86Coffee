/* ============================================================
   Root 86 Coffee — First-party analytics pinger
   Sends events to the Cloudflare Worker /track endpoint.
   Silently no-ops if the endpoint is not configured.
   ============================================================ */
(function(){
  var base = (window.SITE_SETTINGS && window.SITE_SETTINGS.formEndpoint) || '';
  if (!base) return;
  // Strip trailing slash for safe concat
  base = base.replace(/\/+$/, '');

  function send(payload){
    try {
      var blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
      // sendBeacon survives page unloads and doesn't block
      if (navigator.sendBeacon && navigator.sendBeacon(base + '/track', blob)) return;
      fetch(base + '/track', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        keepalive: true,
      }).catch(function(){});
    } catch(e) {}
  }

  // Pageview on load
  try {
    send({
      type: 'pageview',
      path: location.pathname,
      referrer: document.referrer || ''
    });
  } catch(e) {}

  // Expose for in-page tracking (modal opens, quote submits)
  window.r86Track = function(type, data){
    var p = Object.assign({ type: type }, data || {});
    send(p);
  };
})();
