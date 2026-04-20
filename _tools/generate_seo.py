#!/usr/bin/env python3
"""
Generate all SEO-friendly static pages + sitemap for Root 86 Coffee.

Produces:
  - coffees/<slug>.html   (one per visible coffee, Product schema)
  - origins/<slug>.html   (one per origin hub)
  - green-coffee-canada.html, green-coffee-quebec.html, green-coffee-vancouver-island.html
  - sitemap.xml           (all public pages)

Re-run after editing js/coffees.js to refresh all pages.
Usage: python _tools/generate_seo.py
"""
import re, json, os, sys, pathlib, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE_URL = "https://root86coffee.com"

# ── Load COFFEES from js/coffees.js (regex extract the JSON array) ──
def load_coffees():
    src = (ROOT / "js" / "coffees.js").read_text(encoding="utf-8")
    # Extract the array between "const COFFEES = [" and the matching "];"
    m = re.search(r"const COFFEES\s*=\s*(\[.*?\n\]);", src, re.S)
    if not m:
        print("Could not locate COFFEES array", file=sys.stderr); sys.exit(1)
    text = m.group(1)
    # Convert JS-style keys to JSON-compatible keys
    # Each line like `    name: "..."` -> `    "name": "..."`
    text = re.sub(r"^(\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:", r'\1"\2":', text, flags=re.M)
    # Remove trailing commas before ] or }
    text = re.sub(r",(\s*[\]}])", r"\1", text)
    return json.loads(text)

def slugify(s):
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")

def html_escape(s):
    if s is None: return ""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))

# ── Origin descriptions (hand-written for SEO depth) ──
ORIGIN_COPY = {
    "Ethiopia": {
        "headline": "Ethiopian green coffee - the birthplace of Arabica",
        "intro": "Ethiopia is the ancestral home of Coffea arabica. Ancient heirloom varieties grow wild in the highland forests of Yirgacheffe, Sidama, Guji, and Harar, producing some of the most aromatic, tea-like, and floral coffees in the world. Ethiopian green coffee is a cornerstone of specialty roasting programs across Canada.",
        "context": "Root 86 Coffee imports both washed and natural process Ethiopian lots, including Grade 1 and Grade 2 selections from Yirgacheffe washing stations (Konga, Gersi, Koke) and the fruit-forward naturals of Guji and Sidama. All our Ethiopian lots are specialty grade and available to Canadian roasters from our Vancouver, Parksville, and Lévis warehouses.",
        "flavour": "Expect jasmine, bergamot, peach, blueberry, lemon, black tea, and honey.",
    },
    "Colombia": {
        "headline": "Colombian green coffee - balanced, bright, consistently excellent",
        "intro": "Colombia is Canada's most-sourced specialty origin for good reason. Diverse microclimates across Huila, Nariño, Tolima, Quindío, Cundinamarca, and Antioquia produce consistently clean, sweet, and well-structured coffees that excel in every brew method.",
        "context": "We import Colombian Excelso EP, Excelso GP, organic, Rainforest Alliance, and Women's Producer lots - including our Terra Rosa Women's Lot from Huila and EcoTerra Women's Lot from Nariño. Whether you need a dependable blend base or a distinctive single-origin, our Colombian catalogue has you covered.",
        "flavour": "Expect milk chocolate, caramel, red apple, peach, honey, citrus, and brown sugar.",
    },
    "Brazil": {
        "headline": "Brazilian green coffee - espresso's classic foundation",
        "intro": "Brazil produces roughly a third of the world's coffee and is the backbone of countless espresso blends. The volcanic soils of Alta Mogiana, Sul de Minas Gerais, and Cerrado produce the smooth, low-acid, chocolate-and-nut profile that defines approachable coffee.",
        "context": "Root 86 stocks natural-process Brazilian lots from Alta Mogiana 17/18, Poços de Caldas, and Sul de Minas, plus Swiss Water Process Brazilian decaf. These are workhorses - reliable, sweet, and roast-flexible for espresso or drip.",
        "flavour": "Expect dark chocolate, hazelnut, caramel, brown sugar, almond, and dried fruit.",
    },
    "Guatemala": {
        "headline": "Guatemalan green coffee - SHB intensity, volcanic complexity",
        "intro": "Guatemala's eight coffee regions each offer distinct character, from the bright, fruited Huehuetenango highlands to the rich, chocolatey lots around Lake Atitlán. SHB (Strictly Hard Bean) grading guarantees beans grown above 1,350 meters - dense, complex, and roast-tolerant.",
        "context": "Our Guatemalan catalogue includes washed SHB EP GP selections from Huehuetenango, Santa Rosa, and San Marcos, plus certified organic lots from Lake Atitlán. These coffees shine across the roast spectrum.",
        "flavour": "Expect milk chocolate, toffee, orange peel, apple, walnut, and dark cherry.",
    },
    "Costa Rica": {
        "headline": "Costa Rican green coffee - micromill precision",
        "intro": "Costa Rica's small-producer micromill movement transformed the country's specialty coffee in the 2000s. Today, growers in the West and Central Valleys, Tarrazú, and Tres Ríos produce honey-processed and washed lots of exceptional cleanliness and clarity.",
        "context": "Root 86 offers honey-processed microlots from Hacienda San Ignacio (Marsellesa hybrid), V&G Estate natural process lots, and classic washed Tarrazú SHB. These are Central American benchmarks.",
        "flavour": "Expect peach jam, raisin, brown sugar, vanilla, citrus, and milk chocolate.",
    },
    "Kenya": {
        "headline": "Kenyan green coffee - wine-like, savoury, unmistakable",
        "intro": "Kenya is the connoisseur's origin. Double-washed fermentation and meticulous sorting (AA, AB Plus grades) produce the distinctive blackcurrant-and-tomato-juice profile that Kenyan SL28 and SL34 varieties are famous for.",
        "context": "Our Kenya AB Plus Sondhi delivers that wine-like complexity at specialty-grade quality. A roaster's coffee - bold, bright, uncompromising.",
        "flavour": "Expect blackcurrant, tomato, grapefruit, dark berry, and bright acidity.",
    },
    "Honduras": {
        "headline": "Honduran green coffee - approachable Central American sweetness",
        "intro": "Honduras is Central America's largest coffee producer and a reliable source of well-priced specialty lots. The highland regions of Copán, Marcala, and the western cordilleras produce soft, sweetly balanced coffees ideal for everyday blends.",
        "context": "We carry SHG (Strictly High Grown) Copán organic, Lempira SHG Tierra Lenca, and Swiss Water Process Honduras decaf. Gentle, approachable, and roast-flexible.",
        "flavour": "Expect peach, caramel, toasted nuts, apple, and milk chocolate.",
    },
    "Mexico": {
        "headline": "Mexican green coffee - organic specialty from Chiapas and Oaxaca",
        "intro": "Mexico is North America's closest specialty origin and a leader in certified organic production. Chiapas and Oaxaca dominate Mexico's fine coffee output, with indigenous smallholder cooperatives producing some of the world's most consistently organic-certified lots.",
        "context": "Root 86 imports SHG organic selections from Chiapas (including producer-named Angel Diaz) and Oaxaca Pluma. We also offer Mexican Mountain Water Process decaf - the gold standard of chemical-free decaffeination.",
        "flavour": "Expect hazelnut, milk chocolate, caramel, orange, dried apricot, and honey.",
    },
    "Peru": {
        "headline": "Peruvian green coffee - Andean organic specialty",
        "intro": "Peru produces more certified organic coffee than almost any other country. The cloud forests of Cajamarca, Amazonas, and San Martín grow Bourbon, Typica, and Caturra varieties at extreme altitude on small indigenous farms.",
        "context": "Our El Gran Mirador certified organic lot is a standout - bright, floral, sweetly balanced. We also carry Swiss Water Process Peru decaf organic.",
        "flavour": "Expect peach, caramel, milk chocolate, floral, almond, and dried fruit.",
    },
    "Rwanda": {
        "headline": "Rwandan green coffee - Bourbon on volcanic soil",
        "intro": "Rwanda's specialty revival, led by women's producer cooperatives, has made it one of East Africa's most exciting specialty origins. The country grows almost exclusively Red Bourbon on volcanic soils at 1,700-2,000 meters.",
        "context": "Our Nyampinga Organic Women's COOP represents the best of Rwanda - Kinyarwanda for 'beautiful girl', the lot supports the cooperative's female members directly. Deeply fruited, floral, and clean.",
        "flavour": "Expect raspberry, plum, caramel, rose, and bright acidity.",
    },
    "Tanzania": {
        "headline": "Tanzanian green coffee - Kilimanjaro sweetness, Southern brightness",
        "intro": "Tanzania produces two distinct coffee styles: the classic Northern lots from the slopes of Mount Kilimanjaro (Kent, Bourbon, Blue Mountain varieties) and the emerging Southern Highlands offering.",
        "context": "We stock PB Plus (Peaberry) from both Northern Kilimanjaro and Southern estates. Peaberry beans are the naturally-occurring single-bean cherry - concentrated sweetness and flavour.",
        "flavour": "Expect blackberry, citrus, dark chocolate, plum, and mandarin.",
    },
    "Uganda": {
        "headline": "Ugandan green coffee - Mt. Elgon AA, Kenya-adjacent complexity",
        "intro": "Uganda's Mt. Elgon region shares terroir with Kenya across the border - high altitude, rich volcanic soils, and SL14/SL28 varieties. The result is a Kenyan-style cup at an accessible price point.",
        "context": "Our Mt. Elgon AA Rainforest Alliance certified lot delivers exactly that: complex, fruit-forward, bold.",
        "flavour": "Expect apricot, dark berry, dark chocolate, cedar, and bright acidity.",
    },
    "Indonesia": {
        "headline": "Indonesian green coffee - Sumatra Mandheling and beyond",
        "intro": "Indonesia produces some of the most distinctive coffees in the world. Sumatra's Giling Basah (wet-hulling) process creates the iconic low-acid, full-body, earthy-herbal Mandheling profile. Sulawesi, Java, and Flores offer their own terroir stories.",
        "context": "Root 86 imports Sumatra Mandheling Grade 1 (both standard and Women's Producer Organic) and Indonesia Flores Rainforest Alliance Organic. Deep, bold, and complex - the cornerstone of many espresso blends.",
        "flavour": "Expect dark chocolate, tobacco, earth, cedar, molasses, and clove.",
    },
    "Panama": {
        "headline": "Panamanian green coffee - Boquete refinement",
        "intro": "Panama's Boquete region, nestled in Chiriquí province, produces some of the world's most refined coffees. Volcanic soils, cool nights, and careful micromill processing create cups of exceptional elegance.",
        "context": "Our Boquete Finca La Santa Catuai single-variety lot showcases Panama's best: floral, nuanced, beautifully balanced.",
        "flavour": "Expect honey, orange blossom, stone fruit, brown sugar, and creamy body.",
    },
    "Nicaragua": {
        "headline": "Nicaraguan green coffee - Jinotega shade-grown organic",
        "intro": "Nicaragua's northern highlands - especially Jinotega, Matagalpa, and Nueva Segovia - produce reliable specialty coffee under native shade canopy. Small cooperative producers dominate Nicaraguan specialty output.",
        "context": "Our Jinotega FT Organic is a clean, sweetly balanced certified Fair Trade and Organic lot from highland Jinotega cooperatives.",
        "flavour": "Expect milk chocolate, almond, apple, and caramel.",
    },
    "Papua New Guinea": {
        "headline": "Papua New Guinea green coffee - heritage Arabica from Simbu Highlands",
        "intro": "Papua New Guinea's remote highlands grow some of the world's most isolated and traditionally-farmed Arabica. Smallholder gardens of Arusha, Bourbon, and Typica thrive at 1,500-1,800 meters in the Simbu province.",
        "context": "Our PSC (Premium Smallholder Coffee) Simbu lot is uniquely complex - tropical fruit, cocoa, and gentle spice with lingering sweetness.",
        "flavour": "Expect tropical fruit, cocoa, black tea, and sweet spice.",
    },
    "Blend": {
        "headline": "Blended green coffee - espresso-ready selections",
        "intro": "Our purpose-crafted blends give you consistent, roast-ready foundations for specialty espresso programs.",
        "context": "Root 86's blended offerings include the SWP Premium Espresso Blend Decaf - engineered for thick crema, deep body, and rich chocolatey sweetness, all without caffeine.",
        "flavour": "Expect dark chocolate, toffee, clean crema body.",
    },
    "El Salvador": {
        "headline": "Salvadoran green coffee - specialty from Santa Ana",
        "intro": "El Salvador's highland Santa Ana region produces some of Central America's most refined Bourbon and Pacamara lots - silky body, honeyed sweetness, clean cup.",
        "context": "We feature traceable Salvadoran specialty lots when available.",
        "flavour": "Expect hazelnut, sweet chocolate, dark honey, silky body.",
    },
}

# ── Shared HTML helpers ──
NAV_HTML = '''<nav style="padding:18px 24px; display:flex; justify-content:space-between; align-items:center; position:fixed; top:0; left:0; right:0; background:rgba(61,0,8,0.95); backdrop-filter:blur(8px); z-index:100;">
  <a href="/" style="font-family:var(--font-serif); color:#fff; font-size:1.1rem; text-decoration:none; letter-spacing:.05em;">ROOT 86</a>
  <div style="display:flex; gap:24px; font-size:.78rem; letter-spacing:.15em; text-transform:uppercase;">
    <a href="/#finder" style="color:rgba(255,255,255,0.7); text-decoration:none;">Find Coffee</a>
    <a href="/contact.html" style="color:rgba(255,255,255,0.7); text-decoration:none;">Contact</a>
    <a href="tel:18559080086" style="color:var(--red); text-decoration:none;">1-855-908-0086</a>
  </div>
</nav>'''

FOOTER_HTML = '''<footer class="lp-footer">
  <p>
    <a href="/">Home</a> &middot;
    <a href="/#finder">Find Coffee</a> &middot;
    <a href="/contact.html">Contact</a> &middot;
    <a href="/roasters.html">Find a Roaster</a> &middot;
    <a href="/green-coffee-vancouver.html">Vancouver</a> &middot;
    <a href="/green-coffee-canada.html">Canada</a> &middot;
    <a href="/green-coffee-quebec.html">Québec</a> &middot;
    <a href="/green-coffee-vancouver-island.html">Vancouver Island</a>
  </p>
  <p style="margin-top:10px;">&copy; Root 86 Coffee &middot; Canadian Green Coffee Importer &middot; <a href="tel:18559080086">1-855-908-0086</a></p>
</footer>'''

LP_STYLE = '''<style>
  .lp-hero { padding: 40px 24px 80px; background: var(--red-deep); color: var(--white); }
  .lp-container { max-width: 960px; margin: 0 auto; }
  .lp-eyebrow { font-size:.7rem; letter-spacing:.3em; text-transform:uppercase; color: rgba(200,16,46,0.85); margin-bottom:18px; }
  .lp-hero h1 { font-family: var(--font-serif); font-size: clamp(36px, 5vw, 68px); font-weight:300; line-height:1.05; margin-bottom: 24px; }
  .lp-hero h1 em { color: var(--red); font-style: italic; }
  .lp-hero p.lead { font-size: 1.05rem; line-height:1.7; color: rgba(255,255,255,0.75); max-width: 640px; }
  .lp-hero .cta-row { margin-top: 34px; display:flex; gap:14px; flex-wrap:wrap; }
  .lp-cta { display:inline-flex; align-items:center; gap:10px; padding:14px 28px; font-size:.75rem; letter-spacing:.2em; text-transform:uppercase; font-weight:500; text-decoration:none; transition: background .2s; }
  .lp-cta-primary { background: var(--red); color: var(--white); }
  .lp-cta-primary:hover { background: var(--red-dark); }
  .lp-cta-ghost { border: 1px solid rgba(255,255,255,0.25); color: var(--white); }
  .lp-cta-ghost:hover { background: rgba(255,255,255,0.05); }
  .lp-section { padding: 80px 24px; }
  .lp-section.alt { background: #FAF8F6; }
  .lp-section h2 { font-family: var(--font-serif); font-size: clamp(28px, 3vw, 44px); font-weight: 300; line-height:1.15; margin-bottom: 24px; color: var(--ink); }
  .lp-section h2 em { color: var(--red); font-style: italic; }
  .lp-section h3 { font-family: var(--font-serif); font-size: 1.5rem; font-weight: 400; margin-top:36px; margin-bottom:14px; color: var(--ink); }
  .lp-section p { color: var(--muted); line-height:1.85; margin-bottom:18px; font-size:.98rem; }
  .lp-section ul, .lp-section ol { padding-left: 22px; margin-bottom: 22px; color: var(--muted); line-height:1.85; }
  .lp-section ul li, .lp-section ol li { margin-bottom: 8px; }
  .lp-section a { color: var(--red); text-decoration: underline; text-underline-offset: 3px; }
  .lp-breadcrumb { padding: 90px 24px 0; font-size:.75rem; color: var(--muted); }
  .lp-breadcrumb a { color: var(--muted); text-decoration:none; }
  .lp-breadcrumb a:hover { color: var(--red); }
  .lp-contact-band { padding: 60px 24px; background: var(--ink); color: var(--white); text-align:center; }
  .lp-contact-band h2 { color: var(--white); margin-bottom: 14px; }
  .lp-contact-band p { color: rgba(255,255,255,0.6); max-width: 520px; margin: 0 auto 24px; }
  .lp-footer { padding: 32px 24px; text-align:center; color: var(--muted); font-size:.78rem; border-top: 1px solid rgba(0,0,0,0.08); }
  .lp-footer a { color: var(--muted); margin: 0 10px; text-decoration:none; }
  .lp-footer a:hover { color: var(--red); }
  .coffee-grid-sm { display:grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; margin-top: 24px; }
  .cg-card { padding: 18px; border: 1px solid rgba(0,0,0,0.08); background: var(--white); text-decoration:none !important; color: inherit; transition: border-color .2s, transform .15s; display:block; }
  .cg-card:hover { border-color: var(--red); transform: translateY(-2px); }
  .cg-origin { font-size:.65rem; letter-spacing:.2em; text-transform:uppercase; color: var(--red); margin-bottom: 6px; }
  .cg-name { font-family: var(--font-serif); font-size: 1.1rem; color: var(--ink); line-height:1.3; margin-bottom: 6px; }
  .cg-notes { font-size:.78rem; color: var(--muted); line-height:1.55; font-style: italic; }
  body { overflow-x:hidden; }
  * { cursor: auto !important; }
  a[href], button { cursor: pointer !important; }
</style>'''

# ── Coffee page template ──
def build_coffee_page(c, all_coffees):
    name = c["name"]
    slug = slugify(name)
    origin = c["origin"]
    region = c.get("region", "")
    process = c.get("process", "")
    variety = c.get("variety", "")
    altitude = c.get("altitude", "")
    bag = c.get("bagWeight", 152)
    certs = c.get("certifications", [])
    whs = c.get("warehouses", [])
    notes = c.get("tastingNotes", "")
    desc = c.get("description", "")
    image = c.get("image", "")
    available = c.get("available", True) and not c.get("soldOut")

    url = f"{SITE_URL}/coffees/{slug}.html"

    # Title: include origin + "Green Coffee" + location framing
    title = f"{name} | Green Coffee from {origin} | Root 86 Coffee Canada"
    meta_desc = (f"{name} - {origin} green coffee from {region or origin}. "
                 f"{notes[:100]}. Available from Root 86 Coffee Canada. "
                 f"Bag size {bag} lbs. Stocked in {', '.join(whs) if whs else 'Canada'}.")
    meta_desc = meta_desc[:158]

    # Product schema
    offer = ""
    if available:
        offer = f'''
    "offers": {{
      "@type": "Offer",
      "availability": "https://schema.org/InStock",
      "priceCurrency": "CAD",
      "url": "{url}",
      "seller": {{ "@type": "Organization", "name": "Root 86 Coffee" }}
    }},'''
    else:
        offer = f'''
    "offers": {{
      "@type": "Offer",
      "availability": "https://schema.org/OutOfStock",
      "priceCurrency": "CAD",
      "url": "{url}"
    }},'''

    product_schema = f'''{{
    "@context": "https://schema.org",
    "@type": "Product",
    "name": {json.dumps(name)},
    "description": {json.dumps(desc[:300] or notes)},
    "image": {json.dumps(image) if image else '""'},
    "brand": {{ "@type": "Brand", "name": "Root 86 Coffee" }},
    "category": "Green Coffee",
    "additionalProperty": [
      {{ "@type": "PropertyValue", "name": "Origin", "value": {json.dumps(origin)} }},
      {{ "@type": "PropertyValue", "name": "Region", "value": {json.dumps(region)} }},
      {{ "@type": "PropertyValue", "name": "Process", "value": {json.dumps(process)} }},
      {{ "@type": "PropertyValue", "name": "Variety", "value": {json.dumps(variety)} }},
      {{ "@type": "PropertyValue", "name": "Altitude", "value": {json.dumps(altitude)} }},
      {{ "@type": "PropertyValue", "name": "Bag Weight", "value": "{bag} lbs" }}
    ],{offer}
    "url": "{url}"
  }}'''

    breadcrumb = f'''{{
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      {{ "@type": "ListItem", "position": 1, "name": "Home", "item": "{SITE_URL}/" }},
      {{ "@type": "ListItem", "position": 2, "name": "Coffees", "item": "{SITE_URL}/#finder" }},
      {{ "@type": "ListItem", "position": 3, "name": {json.dumps(origin)}, "item": "{SITE_URL}/origins/{slugify(origin)}.html" }},
      {{ "@type": "ListItem", "position": 4, "name": {json.dumps(name)}, "item": "{url}" }}
    ]
  }}'''

    # Related coffees (same origin, not this one)
    related = [x for x in all_coffees if x["origin"] == origin and x["id"] != c["id"] and not x.get("hidden")][:3]
    related_html = ""
    if related:
        cards = []
        for r in related:
            r_slug = slugify(r["name"])
            cards.append(f'''<a href="/coffees/{r_slug}.html" class="cg-card">
              <div class="cg-origin">{html_escape(r["origin"])}</div>
              <div class="cg-name">{html_escape(r["name"])}</div>
              <div class="cg-notes">{html_escape((r.get("tastingNotes") or "")[:90])}</div>
            </a>''')
        related_html = f'''<section class="lp-section alt">
          <div class="lp-container">
            <h2>More <em>{html_escape(origin)}</em> green coffee</h2>
            <div class="coffee-grid-sm">{''.join(cards)}</div>
          </div>
        </section>'''

    certs_html = " &middot; ".join(f"<strong>{html_escape(x)}</strong>" for x in certs) if certs else "None listed"
    whs_html = ", ".join(html_escape(w) for w in whs) if whs else "Contact us for current availability"

    image_html = (f'<img src="{html_escape(image)}" alt="{html_escape(name)} green coffee" '
                  'loading="lazy" style="max-width:280px; height:auto; margin-bottom:24px;" '
                  'onerror="this.style.display=\'none\'" />' if image else "")

    status = "In stock" if available else "Currently out of stock - contact us for similar lots"

    # Split description into paragraphs, skip if empty
    desc_html = ""
    if desc:
        paras = [p.strip() for p in desc.split("\n\n") if p.strip()]
        desc_html = "\n".join(f"<p>{html_escape(p)}</p>" for p in paras)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html_escape(title)}</title>
  <meta name="description" content="{html_escape(meta_desc)}" />
  <meta name="robots" content="index, follow, max-image-preview:large" />
  <link rel="canonical" href="{url}" />
  <meta property="og:type" content="product" />
  <meta property="og:site_name" content="Root 86 Coffee" />
  <meta property="og:title" content="{html_escape(name)} | Root 86 Coffee" />
  <meta property="og:description" content="{html_escape(meta_desc)}" />
  <meta property="og:url" content="{url}" />
  {'<meta property="og:image" content="' + html_escape(image) + '" />' if image else ''}
  <meta name="twitter:card" content="summary_large_image" />
  <link rel="preconnect" href="https://static.wixstatic.com" />
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>&#9749;</text></svg>" />
  <link rel="stylesheet" href="/css/styles.css" />
  <script type="application/ld+json">{product_schema}</script>
  <script type="application/ld+json">{breadcrumb}</script>
  {LP_STYLE}
</head>
<body>
{NAV_HTML}
<nav class="lp-breadcrumb">
  <a href="/">Home</a> &rsaquo; <a href="/#finder">Coffees</a> &rsaquo; <a href="/origins/{slugify(origin)}.html">{html_escape(origin)}</a> &rsaquo; <span>{html_escape(name)}</span>
</nav>
<section class="lp-hero">
  <div class="lp-container">
    <span class="lp-eyebrow">{html_escape(origin)}{" &middot; " + html_escape(region) if region else ""}</span>
    <h1>{html_escape(name)}</h1>
    <p class="lead">{html_escape(notes)}</p>
    <div class="cta-row">
      <a href="/#finder" class="lp-cta lp-cta-primary">Add to Quote &rarr;</a>
      <a href="/contact.html" class="lp-cta lp-cta-ghost">Request a Sample</a>
    </div>
  </div>
</section>
<section class="lp-section">
  <div class="lp-container">
    {image_html}
    <h2>About this <em>{html_escape(origin)}</em> green coffee</h2>
    {desc_html or f"<p>{html_escape(notes)}</p>"}
    <h3>Specifications</h3>
    <ul>
      <li><strong>Origin:</strong> {html_escape(origin)}{" &middot; " + html_escape(region) if region else ""}</li>
      <li><strong>Process:</strong> {html_escape(process)}</li>
      {f"<li><strong>Variety:</strong> {html_escape(variety)}</li>" if variety else ""}
      {f"<li><strong>Altitude:</strong> {html_escape(altitude)}</li>" if altitude else ""}
      <li><strong>Bag weight:</strong> {bag} lbs</li>
      <li><strong>Certifications:</strong> {certs_html}</li>
      <li><strong>Warehouses:</strong> {whs_html}</li>
      <li><strong>Availability:</strong> {status}</li>
    </ul>
    <h3>Cupping notes</h3>
    <p>{html_escape(notes)}</p>
  </div>
</section>
{related_html}
<section class="lp-contact-band">
  <div class="lp-container">
    <h2>Interested in <em style="color:var(--red);">{html_escape(name.split(',')[0])}</em>?</h2>
    <p>Request pricing, a sample, or current availability. We respond the same business day.</p>
    <div style="display:flex; gap:12px; justify-content:center; flex-wrap:wrap;">
      <a href="/#finder" class="lp-cta lp-cta-primary">Browse All Coffees</a>
      <a href="/contact.html" class="lp-cta lp-cta-ghost">Request a Sample</a>
    </div>
  </div>
</section>
{FOOTER_HTML}
</body>
</html>'''
    return html

# ── Origin hub page ──
def build_origin_page(origin, coffees):
    slug = slugify(origin)
    url = f"{SITE_URL}/origins/{slug}.html"
    copy = ORIGIN_COPY.get(origin, {
        "headline": f"{origin} green coffee",
        "intro": f"Root 86 Coffee imports specialty green coffee from {origin} to roasters across Canada.",
        "context": f"Browse our {origin} catalogue below.",
        "flavour": "",
    })
    title = f"{origin} Green Coffee Canada | Root 86 Coffee Importer"
    meta_desc = f"{origin} green coffee for Canadian roasters. {copy['intro'][:100]} Stocked in Vancouver, Parksville, and Lévis warehouses."
    meta_desc = meta_desc[:158]

    visible = [c for c in coffees if c["origin"] == origin and not c.get("hidden")]
    cards = []
    for r in visible:
        r_slug = slugify(r["name"])
        cards.append(f'''<a href="/coffees/{r_slug}.html" class="cg-card">
          <div class="cg-origin">{html_escape(r.get("process",""))}</div>
          <div class="cg-name">{html_escape(r["name"])}</div>
          <div class="cg-notes">{html_escape((r.get("tastingNotes") or "")[:90])}</div>
        </a>''')

    breadcrumb = f'''{{
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      {{ "@type": "ListItem", "position": 1, "name": "Home", "item": "{SITE_URL}/" }},
      {{ "@type": "ListItem", "position": 2, "name": "Origins", "item": "{SITE_URL}/#finder" }},
      {{ "@type": "ListItem", "position": 3, "name": {json.dumps(origin)}, "item": "{url}" }}
    ]
  }}'''

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html_escape(title)}</title>
  <meta name="description" content="{html_escape(meta_desc)}" />
  <meta name="robots" content="index, follow, max-image-preview:large" />
  <link rel="canonical" href="{url}" />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="Root 86 Coffee" />
  <meta property="og:title" content="{html_escape(title)}" />
  <meta property="og:description" content="{html_escape(meta_desc)}" />
  <meta property="og:url" content="{url}" />
  <link rel="preconnect" href="https://static.wixstatic.com" />
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>&#9749;</text></svg>" />
  <link rel="stylesheet" href="/css/styles.css" />
  <script type="application/ld+json">{breadcrumb}</script>
  {LP_STYLE}
</head>
<body>
{NAV_HTML}
<nav class="lp-breadcrumb">
  <a href="/">Home</a> &rsaquo; <a href="/#finder">Coffees</a> &rsaquo; <span>{html_escape(origin)}</span>
</nav>
<section class="lp-hero">
  <div class="lp-container">
    <span class="lp-eyebrow">{html_escape(origin)}</span>
    <h1>{html_escape(copy["headline"])}</h1>
    <p class="lead">{html_escape(copy["intro"])}</p>
    <div class="cta-row">
      <a href="/#finder" class="lp-cta lp-cta-primary">Browse All Coffees &rarr;</a>
      <a href="/contact.html" class="lp-cta lp-cta-ghost">Request Samples</a>
    </div>
  </div>
</section>
<section class="lp-section">
  <div class="lp-container">
    <h2>About our <em>{html_escape(origin)}</em> green coffee selection</h2>
    <p>{html_escape(copy["context"])}</p>
    {f"<h3>Flavour profile</h3><p>{html_escape(copy['flavour'])}</p>" if copy.get("flavour") else ""}
    <h3>Available {html_escape(origin)} coffees at Root 86</h3>
    <div class="coffee-grid-sm">{''.join(cards) if cards else '<p>No lots currently visible. Contact us for availability.</p>'}</div>
  </div>
</section>
<section class="lp-contact-band">
  <div class="lp-container">
    <h2>Source <em style="color:var(--red);">{html_escape(origin)}</em> green coffee in Canada</h2>
    <p>Talk to us about current lot availability, samples, and pricing. All origins stocked in Vancouver BC, Parksville BC, and Lévis QC.</p>
    <div style="display:flex; gap:12px; justify-content:center; flex-wrap:wrap;">
      <a href="/#finder" class="lp-cta lp-cta-primary">Browse Catalogue</a>
      <a href="/contact.html" class="lp-cta lp-cta-ghost">Contact Us</a>
    </div>
  </div>
</section>
{FOOTER_HTML}
</body>
</html>'''
    return html

# ── Additional landing pages ──
def build_canada_page():
    url = f"{SITE_URL}/green-coffee-canada.html"
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Green Coffee Canada | Nationwide Importer | Root 86 Coffee</title>
  <meta name="description" content="Green coffee importer serving roasters across Canada. Root 86 Coffee stocks 50+ origins in Vancouver BC, Parksville BC, and Lévis QC with fast domestic delivery. Organic, Fair Trade, and specialty lots." />
  <meta name="robots" content="index, follow, max-image-preview:large" />
  <link rel="canonical" href="{url}" />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="Root 86 Coffee" />
  <meta property="og:title" content="Green Coffee Canada | Root 86 Coffee" />
  <meta property="og:description" content="Canada's trusted green coffee importer. 50+ origins, 3 warehouses, nationwide delivery." />
  <meta property="og:url" content="{url}" />
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>&#9749;</text></svg>" />
  <link rel="stylesheet" href="/css/styles.css" />
  {LP_STYLE}
</head>
<body>
{NAV_HTML}
<nav class="lp-breadcrumb"><a href="/">Home</a> &rsaquo; <span>Green Coffee Canada</span></nav>
<section class="lp-hero">
  <div class="lp-container">
    <span class="lp-eyebrow">Canadian Green Coffee Importer</span>
    <h1>Green Coffee for <em>Canadian</em> Roasters</h1>
    <p class="lead">Root 86 Coffee is a fully Canadian green coffee importer serving micro-roasters, cafes, and wholesale buyers across every province. 50+ origins stocked at three Canadian warehouses - no cross-border shipping, no currency surprises.</p>
    <div class="cta-row">
      <a href="/#finder" class="lp-cta lp-cta-primary">Browse Catalogue &rarr;</a>
      <a href="/contact.html" class="lp-cta lp-cta-ghost">Get a Quote</a>
    </div>
  </div>
</section>
<section class="lp-section">
  <div class="lp-container">
    <h2>Canada's green coffee importer, <em>serving coast to coast</em></h2>
    <p>Canada's specialty coffee scene has exploded over the past decade. From the craft cafes of Vancouver and Toronto to the roasteries of Montreal, Halifax, and Calgary, independent roasters have raised the bar for what Canadian coffee can be.</p>
    <p>Root 86 Coffee exists to supply that community. We import green coffee from every major producing region and stock it at three Canadian warehouses: <a href="/green-coffee-vancouver.html">Vancouver, BC</a>; <a href="/green-coffee-vancouver-island.html">Parksville, BC</a>; and <a href="/green-coffee-quebec.html">Lévis, QC</a>. No Canadian roaster is more than a reasonable freight quote away from a bag of specialty-grade green coffee.</p>
    <h3>Three warehouses, nationwide coverage</h3>
    <ul>
      <li><strong>Vancouver, British Columbia</strong> - serves the Lower Mainland, BC Interior, Alberta, and Western Canada</li>
      <li><strong>Parksville, British Columbia</strong> - serves Vancouver Island and Gulf Islands roasters directly</li>
      <li><strong>Lévis, Québec</strong> - serves Quebec, Ontario, the Maritimes, and Atlantic Canada</li>
    </ul>
    <h3>50+ origins in stock across Canada</h3>
    <p>Our Canadian green coffee catalogue spans every major producing region:</p>
    <ul>
      <li><a href="/origins/ethiopia.html">Ethiopia</a> - Yirgacheffe, Sidama, Guji (washed &amp; natural, G1 &amp; G2)</li>
      <li><a href="/origins/colombia.html">Colombia</a> - Huila, Nariño, Tolima, Quindío, Cundinamarca</li>
      <li><a href="/origins/brazil.html">Brazil</a> - Alta Mogiana, Sul de Minas, Poços de Caldas</li>
      <li><a href="/origins/guatemala.html">Guatemala</a> - Huehuetenango, Santa Rosa, San Marcos, Lake Atitlán</li>
      <li><a href="/origins/costa-rica.html">Costa Rica</a> - West Valley, Central Valley, Tarrazú</li>
      <li><a href="/origins/kenya.html">Kenya</a>, <a href="/origins/tanzania.html">Tanzania</a>, <a href="/origins/uganda.html">Uganda</a>, <a href="/origins/rwanda.html">Rwanda</a></li>
      <li><a href="/origins/mexico.html">Mexico</a>, <a href="/origins/honduras.html">Honduras</a>, <a href="/origins/peru.html">Peru</a>, <a href="/origins/nicaragua.html">Nicaragua</a>, <a href="/origins/panama.html">Panama</a></li>
      <li><a href="/origins/indonesia.html">Indonesia</a>, <a href="/origins/papua-new-guinea.html">Papua New Guinea</a></li>
      <li>Decaf options - Swiss Water Process and Mountain Water Process</li>
    </ul>
    <h3>Why Canadian roasters choose Root 86 Coffee</h3>
    <ol>
      <li><strong>Canadian-owned, Canadian-stocked.</strong> Every bag is already in Canada when you order it.</li>
      <li><strong>CAD pricing.</strong> No exchange rate guessing, no unexpected USD-to-CAD swings.</li>
      <li><strong>Domestic freight only.</strong> Your order never crosses a border.</li>
      <li><strong>Three strategic warehouses.</strong> Closest-warehouse shipping minimizes freight cost and time.</li>
      <li><strong>Specialty focus.</strong> We curate rather than stocking everything - only lots we'd roast ourselves.</li>
      <li><strong>Direct relationships with importers.</strong> Most of our lots come from long-term trusted supply chains.</li>
    </ol>
  </div>
</section>
<section class="lp-section alt">
  <div class="lp-container">
    <h2>Organic, Fair Trade, <em>and certified green coffee</em> across Canada</h2>
    <p>Sustainability and traceability aren't marketing - they're core to how Canadian specialty coffee is roasted and sold. Our Canadian catalogue includes:</p>
    <ul>
      <li><strong>Certified Organic</strong> lots from Mexico, Peru, Ethiopia, Colombia, Honduras, Indonesia, and more</li>
      <li><strong>Fair Trade</strong> cooperative lots from Nicaragua, Colombia, and Ethiopia</li>
      <li><strong>Rainforest Alliance</strong> certified lots from Colombia, Uganda, and Indonesia</li>
      <li><strong>Women's Producer</strong> lots from Colombia, Rwanda, Indonesia</li>
      <li><strong>Swiss Water Process &amp; Mountain Water Process decaf</strong> - chemical-free decaffeination</li>
    </ul>
    <p>Every certification is verifiable. Request documentation for any lot.</p>
  </div>
</section>
<section class="lp-contact-band">
  <div class="lp-container">
    <h2>Source green coffee <em style="color:var(--red);">anywhere in Canada</em></h2>
    <p>Browse the catalogue, add coffees to your quote, or contact us directly. We respond the same business day and ship from the closest of our three warehouses.</p>
    <div style="display:flex; gap:12px; justify-content:center; flex-wrap:wrap;">
      <a href="/#finder" class="lp-cta lp-cta-primary">Browse Coffees</a>
      <a href="/contact.html" class="lp-cta lp-cta-ghost">Contact Us</a>
    </div>
  </div>
</section>
{FOOTER_HTML}
</body>
</html>'''

def build_quebec_page():
    url = f"{SITE_URL}/green-coffee-quebec.html"
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Green Coffee Québec | Café Vert Lévis QC | Root 86 Coffee</title>
  <meta name="description" content="Green coffee (café vert) importer serving Québec roasters from our Lévis QC warehouse. 50+ origins, organic, Fair Trade, and specialty-grade lots. Fast delivery across Québec, Ontario, and Atlantic Canada." />
  <meta name="robots" content="index, follow" />
  <link rel="canonical" href="{url}" />
  <meta property="og:type" content="website" />
  <meta property="og:title" content="Green Coffee Québec | Root 86 Coffee" />
  <meta property="og:description" content="Green coffee importer serving Québec from Lévis warehouse. 50+ origins for Québec roasters." />
  <meta property="og:url" content="{url}" />
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>&#9749;</text></svg>" />
  <link rel="stylesheet" href="/css/styles.css" />
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "LocalBusiness",
    "name": "Root 86 Coffee - Lévis Warehouse",
    "url": "{url}",
    "telephone": "+1-855-908-0086",
    "address": {{ "@type": "PostalAddress", "addressLocality": "Lévis", "addressRegion": "QC", "addressCountry": "CA" }},
    "geo": {{ "@type": "GeoCoordinates", "latitude": 46.8090, "longitude": -71.1804 }},
    "areaServed": ["Québec", "Montréal", "Québec City", "Lévis", "Sherbrooke", "Trois-Rivières", "Ontario", "New Brunswick", "Nova Scotia"]
  }}
  </script>
  {LP_STYLE}
</head>
<body>
{NAV_HTML}
<nav class="lp-breadcrumb"><a href="/">Home</a> &rsaquo; <span>Green Coffee Québec</span></nav>
<section class="lp-hero">
  <div class="lp-container">
    <span class="lp-eyebrow">Lévis, Québec</span>
    <h1>Green Coffee in <em>Québec</em></h1>
    <p class="lead">Root 86 Coffee supplies café vert (green coffee) to Québec micro-roasters from our Lévis, QC warehouse. 50+ origins stocked locally, serving Montréal, Québec City, Sherbrooke, Trois-Rivières, and roasters throughout Québec, Ontario, and Atlantic Canada.</p>
    <div class="cta-row">
      <a href="/#finder" class="lp-cta lp-cta-primary">Browse Catalogue &rarr;</a>
      <a href="/contact.html" class="lp-cta lp-cta-ghost">Request a Sample</a>
    </div>
  </div>
</section>
<section class="lp-section">
  <div class="lp-container">
    <h2>Our <em>Lévis warehouse</em> serves Eastern Canada</h2>
    <p>Québec has one of the most vibrant specialty coffee scenes in North America, and Root 86 Coffee's Lévis warehouse exists to support it. Strategically located near Québec City, Lévis gives us fast access to Montréal, the Outaouais, Ontario, and the Maritime provinces.</p>
    <p>Every bag stocked at Lévis is also available in Vancouver and Parksville - same origins, same specialty-grade quality, same Canadian pricing. Your order ships from whichever warehouse is closest.</p>
    <h3>Coverage area from Lévis, QC</h3>
    <ul>
      <li><strong>Québec</strong> - Lévis, Québec City, Montréal, Sherbrooke, Trois-Rivières, Saguenay, Gatineau</li>
      <li><strong>Ontario</strong> - Ottawa, Toronto, Kingston, and points between</li>
      <li><strong>Maritimes</strong> - New Brunswick, Nova Scotia, PEI, Newfoundland</li>
    </ul>
    <h3>Organic, Fair Trade &amp; specialty-grade lots for Québec roasters</h3>
    <p>Québec's strong culture of organic and certified coffee aligns perfectly with our sourcing priorities. Certified Organic, Fair Trade, Rainforest Alliance, and Women's Producer lots make up a large share of our stocked inventory - all available at the Lévis warehouse.</p>
    <p><a href="/#finder">Browse the full catalogue</a> and filter by certification, or <a href="/contact.html">contact us</a> to discuss what you're roasting.</p>
  </div>
</section>
<section class="lp-contact-band">
  <div class="lp-container">
    <h2>Café vert en stock <em style="color:var(--red);">au Québec</em></h2>
    <p>Consultez le catalogue, demandez des échantillons, ou écrivez-nous directement. Réponse la même journée ouvrable.</p>
    <div style="display:flex; gap:12px; justify-content:center; flex-wrap:wrap;">
      <a href="/#finder" class="lp-cta lp-cta-primary">Browse Coffees</a>
      <a href="/contact.html" class="lp-cta lp-cta-ghost">Contact Us</a>
    </div>
  </div>
</section>
{FOOTER_HTML}
</body>
</html>'''

def build_island_page():
    url = f"{SITE_URL}/green-coffee-vancouver-island.html"
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Green Coffee Vancouver Island | Parksville BC | Root 86 Coffee</title>
  <meta name="description" content="Green coffee for Vancouver Island micro-roasters. Root 86 Coffee's Parksville BC warehouse stocks 50+ origins locally for Nanaimo, Victoria, Duncan, Courtenay, Tofino, and all Vancouver Island roasters." />
  <meta name="robots" content="index, follow" />
  <link rel="canonical" href="{url}" />
  <meta property="og:type" content="website" />
  <meta property="og:title" content="Green Coffee Vancouver Island | Root 86 Coffee" />
  <meta property="og:description" content="Vancouver Island green coffee importer. Parksville warehouse serving all Island roasters." />
  <meta property="og:url" content="{url}" />
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>&#9749;</text></svg>" />
  <link rel="stylesheet" href="/css/styles.css" />
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "LocalBusiness",
    "name": "Root 86 Coffee - Parksville Warehouse",
    "url": "{url}",
    "telephone": "+1-855-908-0086",
    "address": {{ "@type": "PostalAddress", "addressLocality": "Parksville", "addressRegion": "BC", "addressCountry": "CA" }},
    "geo": {{ "@type": "GeoCoordinates", "latitude": 49.3186, "longitude": -124.3137 }},
    "areaServed": ["Vancouver Island", "Nanaimo", "Victoria", "Parksville", "Duncan", "Courtenay", "Campbell River", "Tofino", "Ucluelet", "Port Alberni"]
  }}
  </script>
  {LP_STYLE}
</head>
<body>
{NAV_HTML}
<nav class="lp-breadcrumb"><a href="/">Home</a> &rsaquo; <span>Green Coffee Vancouver Island</span></nav>
<section class="lp-hero">
  <div class="lp-container">
    <span class="lp-eyebrow">Parksville, Vancouver Island</span>
    <h1>Green Coffee on <em>Vancouver Island</em></h1>
    <p class="lead">Root 86 Coffee's home base is Parksville, Vancouver Island. Our Parksville warehouse is the only Vancouver Island green coffee supplier carrying 50+ origins locally - no ferry delays, no mainland freight, just specialty-grade green coffee ready for Island roasters.</p>
    <div class="cta-row">
      <a href="/#finder" class="lp-cta lp-cta-primary">Browse Catalogue &rarr;</a>
      <a href="/contact.html" class="lp-cta lp-cta-ghost">Sample Request</a>
    </div>
  </div>
</section>
<section class="lp-section">
  <div class="lp-container">
    <h2>Island roasters, <em>Island warehouse</em></h2>
    <p>Vancouver Island has a disproportionately strong craft coffee culture. From Victoria's established third-wave roasters to the micro-roasteries dotting the Comox Valley, Cowichan Valley, and Tofino/Ucluelet, Island roasters have been pushing Canadian specialty coffee forward for two decades.</p>
    <p>Root 86 Coffee started on Vancouver Island, and our Parksville warehouse remains our home base. We stock the same 50+ origins as our Vancouver and Lévis warehouses - available to Island roasters without ferry freight charges, mainland delays, or minimum orders.</p>
    <h3>Vancouver Island coverage from Parksville</h3>
    <ul>
      <li><strong>Nanaimo &amp; Mid-Island</strong> - Parksville, Nanaimo, Qualicum Beach, Errington</li>
      <li><strong>South Island</strong> - Victoria, Sidney, Sooke, Duncan, Cowichan Valley</li>
      <li><strong>North Island</strong> - Courtenay, Comox, Campbell River, Port McNeill</li>
      <li><strong>West Coast</strong> - Tofino, Ucluelet, Port Alberni</li>
      <li><strong>Gulf Islands</strong> - Salt Spring, Gabriola, Hornby, Denman</li>
    </ul>
    <h3>Sample shipments and small lots</h3>
    <p>Parksville is our sample-courier address too. If you're trialling new origins, we'll ship small samples to your Island location for cupping evaluation. <a href="/contact.html">Request samples</a> and we'll match you to three or four relevant lots.</p>
    <p>We also stock half bags (66 lbs) for many origins - ideal for smaller Island roasters and home roasters building out their origin range without over-committing.</p>
  </div>
</section>
<section class="lp-contact-band">
  <div class="lp-container">
    <h2>Green coffee for <em style="color:var(--red);">Vancouver Island</em> roasters</h2>
    <p>No mainland minimums, no ferry freight. Browse the catalogue or contact us directly.</p>
    <div style="display:flex; gap:12px; justify-content:center; flex-wrap:wrap;">
      <a href="/#finder" class="lp-cta lp-cta-primary">Browse Coffees</a>
      <a href="/contact.html" class="lp-cta lp-cta-ghost">Contact Us</a>
    </div>
  </div>
</section>
{FOOTER_HTML}
</body>
</html>'''

# ── Sitemap ──
def build_sitemap(coffees, origins):
    today = datetime.date.today().isoformat()
    urls = [
        (SITE_URL + "/", "1.0", "weekly"),
        (SITE_URL + "/contact.html", "0.7", "monthly"),
        (SITE_URL + "/roasters.html", "0.6", "monthly"),
        (SITE_URL + "/green-coffee-vancouver.html", "0.9", "weekly"),
        (SITE_URL + "/green-coffee-canada.html", "0.9", "weekly"),
        (SITE_URL + "/green-coffee-quebec.html", "0.8", "weekly"),
        (SITE_URL + "/green-coffee-vancouver-island.html", "0.8", "weekly"),
    ]
    for c in coffees:
        if c.get("hidden"): continue
        urls.append((f"{SITE_URL}/coffees/{slugify(c['name'])}.html", "0.7", "monthly"))
    for o in origins:
        urls.append((f"{SITE_URL}/origins/{slugify(o)}.html", "0.8", "monthly"))

    items = "\n".join(
        f"  <url><loc>{u}</loc><lastmod>{today}</lastmod><changefreq>{cf}</changefreq><priority>{p}</priority></url>"
        for (u, p, cf) in urls
    )
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemap.org/schemas/sitemap/0.9">
{items}
</urlset>'''

# ── Main ──
def main():
    coffees = load_coffees()
    print(f"Loaded {len(coffees)} coffees", file=sys.stderr)

    # Create output dirs
    (ROOT / "coffees").mkdir(exist_ok=True)
    (ROOT / "origins").mkdir(exist_ok=True)

    visible = [c for c in coffees if not c.get("hidden")]

    # Write coffee pages (all, including hidden - for the admin - but hidden excluded from sitemap)
    for c in coffees:
        if c.get("hidden"): continue  # don't generate hidden pages
        path = ROOT / "coffees" / f"{slugify(c['name'])}.html"
        path.write_text(build_coffee_page(c, coffees), encoding="utf-8")
    print(f"Wrote {len(visible)} coffee pages", file=sys.stderr)

    # Write origin pages
    origins = sorted({c["origin"] for c in visible if c.get("origin")})
    for o in origins:
        path = ROOT / "origins" / f"{slugify(o)}.html"
        path.write_text(build_origin_page(o, coffees), encoding="utf-8")
    print(f"Wrote {len(origins)} origin pages", file=sys.stderr)

    # Write additional landing pages
    (ROOT / "green-coffee-canada.html").write_text(build_canada_page(), encoding="utf-8")
    (ROOT / "green-coffee-quebec.html").write_text(build_quebec_page(), encoding="utf-8")
    (ROOT / "green-coffee-vancouver-island.html").write_text(build_island_page(), encoding="utf-8")
    print("Wrote 3 location landing pages", file=sys.stderr)

    # Write sitemap
    (ROOT / "sitemap.xml").write_text(build_sitemap(coffees, origins), encoding="utf-8")
    print("Wrote sitemap.xml", file=sys.stderr)

    print("Done.", file=sys.stderr)

if __name__ == "__main__":
    main()
