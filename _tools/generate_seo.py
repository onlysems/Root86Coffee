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
OG_IMAGE = f"{SITE_URL}/images/og-home.png"
OG_IMAGE_W = 1200
OG_IMAGE_H = 630

# ── i18n scaffold ────────────────────────────────────────────────────────────
# English stays at the root; French will live under /fr/… when activated.
# Flip LANG="fr" + uncomment the fr-CA hreflang alternates and the generator
# will emit a parallel French tree without refactor.
LANG = "en"
LANGS_ACTIVE = ("en",)  # add "fr" to activate French generation later.

# Per-locale URL prefix: English at root, French at /fr/.
def locale_url(path: str, lang: str = LANG) -> str:
    """Compose an absolute URL honoring the locale prefix."""
    if lang == "en":
        return f"{SITE_URL}{path}"
    return f"{SITE_URL}/{lang}{path}"

def hreflang_tags(path: str) -> str:
    """Emit hreflang alternates. English is canonical + x-default.
    French stub is commented out; uncomment when /fr/ content lands."""
    en_url = locale_url(path, "en")
    fr_url = locale_url(path, "fr")
    return (
        f'  <link rel="alternate" hreflang="en-CA" href="{en_url}" />\n'
        f'  <link rel="alternate" hreflang="x-default" href="{en_url}" />\n'
        f'  <!-- <link rel="alternate" hreflang="fr-CA" href="{fr_url}" /> -->'
    )

def hreflang_from_url(url: str) -> str:
    """Derive hreflang block from an absolute canonical URL."""
    path = url[len(SITE_URL):] if url.startswith(SITE_URL) else url
    return hreflang_tags(path)

# i18n dict skeleton. All user-facing UI strings that would need translation
# live here. English values are populated; French values stay empty until the
# translation pass. Templates call I18N[key][LANG] once LANG switches to "fr".
I18N = {
    "nav.find_coffee":        {"en": "Find Coffee",           "fr": ""},
    "nav.contact":            {"en": "Contact",               "fr": ""},
    "nav.home":               {"en": "Home",                  "fr": ""},
    "cta.browse_catalogue":   {"en": "Browse Catalogue →",    "fr": ""},
    "cta.request_sample":     {"en": "Request a Sample",      "fr": ""},
    "cta.get_quote":          {"en": "Get a Quote",           "fr": ""},
    "breadcrumb.coffees":     {"en": "Coffees",               "fr": ""},
    "faq.heading":            {"en": "Frequently asked questions", "fr": ""},
    "tagline":                {"en": "Canadian Green Coffee Importer", "fr": ""},
}

# Analytics + search-console verification — activate on domain-transfer day.
# To enable: fill in the VERIFY_* tokens, swap GA4_MEASUREMENT_ID, and the
# tags will appear on every generator-emitted page automatically.
# Consent banner (Law 25 / PIPEDA) lives separately — see resources.
VERIFY_GOOGLE = ""   # e.g. "google-site-verification: abc123…"
VERIFY_BING   = ""   # e.g. "msvalidate.01: …"
GA4_MEASUREMENT_ID = ""  # e.g. "G-XXXXXXXX"

def analytics_and_verification():
    parts = [
        "  <!-- Analytics & Search Console stubs — populate in _tools/generate_seo.py on domain-transfer day. -->",
    ]
    if VERIFY_GOOGLE:
        parts.append(f'  <meta name="google-site-verification" content="{VERIFY_GOOGLE}" />')
    if VERIFY_BING:
        parts.append(f'  <meta name="msvalidate.01" content="{VERIFY_BING}" />')
    if GA4_MEASUREMENT_ID:
        parts.append(
            f'  <script async src="https://www.googletagmanager.com/gtag/js?id={GA4_MEASUREMENT_ID}"></script>\n'
            f'  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}'
            f'gtag(\'js\',new Date());gtag(\'config\',\'{GA4_MEASUREMENT_ID}\',{{anonymize_ip:true}});</script>'
        )
    return "\n".join(parts)

# Favicon + manifest block — identical on every page.
FAVICONS = '''  <link rel="icon" type="image/png" sizes="32x32" href="/images/favicon-32.png" />
  <link rel="icon" type="image/png" sizes="16x16" href="/images/favicon-16.png" />
  <link rel="apple-touch-icon" sizes="180x180" href="/images/apple-touch-icon.png" />
  <link rel="icon" type="image/png" sizes="192x192" href="/images/icon-192.png" />
  <link rel="icon" type="image/png" sizes="512x512" href="/images/icon-512.png" />
  <link rel="shortcut icon" href="/favicon.ico" />
  <link rel="manifest" href="/site.webmanifest" />
  <meta name="theme-color" content="#3D0008" />'''

# Default OG image meta block (brand card) — for pages without a product-specific image.
DEFAULT_OG_IMAGE = f'''  <meta property="og:image" content="{OG_IMAGE}" />
  <meta property="og:image:width" content="{OG_IMAGE_W}" />
  <meta property="og:image:height" content="{OG_IMAGE_H}" />
  <meta property="og:image:alt" content="Root 86 Coffee — Canadian green coffee importer" />
  <meta property="og:locale" content="en_CA" />
  <meta name="twitter:image" content="{OG_IMAGE}" />'''

def og_image_tags(image_url=None, alt=None):
    """Return og:image + twitter:image tags. Falls back to the brand OG card
    if no product-specific image URL is provided."""
    if not image_url:
        return DEFAULT_OG_IMAGE
    alt_attr = html_escape(alt) if alt else "Root 86 Coffee green coffee"
    return (f'  <meta property="og:image" content="{html_escape(image_url)}" />\n'
            f'  <meta property="og:image:alt" content="{alt_attr}" />\n'
            f'  <meta property="og:locale" content="en_CA" />\n'
            f'  <meta name="twitter:image" content="{html_escape(image_url)}" />')

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

def truncate_at_word(s, limit, suffix="…"):
    """Truncate a string at or before `limit` chars, breaking on a word boundary.
    Never returns longer than `limit` (counting the suffix).
    """
    if s is None: return ""
    s = str(s).strip()
    if len(s) <= limit: return s
    cut = s[: max(0, limit - len(suffix))].rsplit(" ", 1)[0].rstrip(",.;:—-")
    return (cut + suffix) if cut else s[:limit]

# ── Origin descriptions (hand-written for SEO depth, ~600-800 words each) ──
# Keys per origin:
#   headline          - h1 text
#   intro             - 2-3 sentence lead paragraph (hero "lead")
#   context           - 2-3 sentence paragraph about Root 86's offerings
#   flavour           - one-line cupping summary
#   regions           - paragraph(s) about growing regions
#   varieties         - paragraph about cultivar varieties
#   processing        - paragraph about common processing methods
#   harvest           - paragraph about harvest calendar and freshness window
#   cupping_profile   - longer descriptor of typical taste
#   roasting_guidance - advice for Canadian micro-roasters
#   why_canada        - closer tying origin to Canadian market
ORIGIN_COPY = {
    "Ethiopia": {
        "headline": "Ethiopian green coffee — the birthplace of Arabica",
        "intro": "Ethiopia is the ancestral home of Coffea arabica. Ancient heirloom varieties grow wild in the highland forests of Yirgacheffe, Sidama, Guji, and Harar, producing some of the most aromatic, tea-like, and floral coffees in the world. Ethiopian green coffee is a cornerstone of specialty roasting programs across Canada.",
        "context": "Root 86 Coffee imports both washed and natural process Ethiopian lots, including Grade 1 and Grade 2 selections from Yirgacheffe washing stations (Konga, Gersi, Koke) and the fruit-forward naturals of Guji and Sidama. All our Ethiopian lots are specialty grade and available to Canadian roasters from our Vancouver, Parksville, and Lévis warehouses.",
        "flavour": "Expect jasmine, bergamot, peach, blueberry, lemon, black tea, and honey.",
        "regions": (
            "Ethiopia's specialty coffee flows from a handful of high-altitude zones in the south and west of the country. "
            "The Gedeo Zone — home of the Yirgacheffe appellation — is the most recognizable name in Ethiopian green coffee, grown between 1,750 and 2,200 m and famous for its delicate, tea-like, citric cups. "
            "Sidama (formerly Sidamo) sits immediately north, producing fruit-forward naturals and clean washed lots from dozens of small washing stations.\n\n"
            "Guji, carved out of Sidama in the last decade, has become the darling of competition roasters: big stone-fruit and floral notes from ultra-high farms around Shakiso, Hambela, and Uraga. "
            "Limu, Kaffa, and Jimma contribute heavier-bodied washed coffees from the west. Harar, in the east, remains the traditional home of dry-processed (natural) Ethiopian coffee with its wild blueberry character."
        ),
        "varieties": (
            "Ethiopia is genetically unique — thousands of indigenous heirloom Arabica varieties grow there, and most are simply catalogued as 'Ethiopian Heirloom' on spec sheets. "
            "Research stations have released cultivars including 74110, 74112, 74158, and the Kurume and Dega selections, chosen for disease resistance and cup quality. "
            "Because heirloom farms interplant dozens of genetic lines, no two Ethiopian lots cup identically — one of the reasons Canadian micro-roasters keep cupping new arrivals."
        ),
        "processing": (
            "Washed (wet-processed) Ethiopian coffees are floral, tea-like, and citric — the classic Yirgacheffe profile. Fermentation is typically 36-72 hours in tank, followed by mechanical demucilaging and raised-bed sun drying for up to three weeks.\n\n"
            "Natural (dry-processed) Ethiopians are dried in whole cherry on raised beds. When done well, they deliver intense blueberry, strawberry, and tropical fruit notes. Grade 1 naturals are the cleanest; Grade 2 naturals are the workhorse of specialty espresso blends seeking a fruit kick."
        ),
        "harvest": (
            "Main-crop harvest in Ethiopia runs October to February, with washed lots landing at origin port mid-March to May and typically arriving in Canadian warehouses between June and September. "
            "Naturals take longer to dry, so they arrive slightly later. Cup quality peaks in the first six months after arrival — plan fresh-crop ordering accordingly."
        ),
        "cupping_profile": (
            "Washed Ethiopians are jasmine, bergamot, lemon, white peach, black tea, and honey — delicate, high-grown, crystalline. "
            "Naturals swing to blueberry, strawberry, mango, ripe stone fruit, cocoa, and red wine. Guji lots often combine both: floral top-notes over a fruity base. "
            "Acidity is bright and malic to phosphoric; body is typically medium to light. These are coffees built for pour-over, batch brew, and shot-pulled espresso where the aromatics have room to speak."
        ),
        "roasting_guidance": (
            "Ethiopian coffees reward light-to-medium roasts that preserve aromatics. Many Canadian micro-roasters drop washed Yirgacheffes at or just before first-crack-end for pour-over, or push lightly past first-crack for batch brew. "
            "Naturals take slightly more development to tame the ferment without losing fruit. Ethiopian beans are small (screen 14-15) and dense — plan for quicker development time than a Central American 17/18."
        ),
        "why_canada": (
            "Ethiopia is the #1 single origin on most Canadian specialty menus. Our Vancouver, Parksville, and Lévis warehouses all stock Ethiopian washed and natural lots year-round, with fresh-crop arrivals scheduled to match Canadian roasters' seasonal menu rotations. "
            "Request a sample kit to cup multiple processing styles from a single origin side-by-side."
        ),
    },
    "Colombia": {
        "headline": "Colombian green coffee — balanced, bright, consistently excellent",
        "intro": "Colombia is Canada's most-sourced specialty origin for good reason. Diverse microclimates across Huila, Nariño, Tolima, Quindío, Cundinamarca, and Antioquia produce consistently clean, sweet, and well-structured coffees that excel in every brew method.",
        "context": "We import Colombian Excelso EP, Excelso GP, organic, Rainforest Alliance, and Women's Producer lots — including our Terra Rosa Women's Lot from Huila and EcoTerra Women's Lot from Nariño. Whether you need a dependable blend base or a distinctive single-origin, our Colombian catalogue has you covered.",
        "flavour": "Expect milk chocolate, caramel, red apple, peach, honey, citrus, and brown sugar.",
        "regions": (
            "Colombia's coffee geography is broader than any other specialty origin: the Andes split into three ranges, each with its own terroir. "
            "Huila, in the south, is the most-awarded department at Cup of Excellence — volcanic soils, 1,600-2,000 m farms, bright and fruited cups. "
            "Nariño, near the Ecuadorian border, grows at extreme altitude (often above 2,000 m) for intensely sweet, syrupy lots.\n\n"
            "Tolima neighbours Huila with similar clean, sweet profiles and is the source of many women's-producer cooperatives. "
            "Quindío, Caldas, and Risaralda — the 'Zona Cafetera' — deliver the classic balanced Colombian cup. "
            "Antioquia and Cundinamarca round out the staples. Each department's lots cup differently; Canadian roasters often carry two or three Colombians simultaneously to cover the spectrum."
        ),
        "varieties": (
            "Colombia historically grew Typica and Bourbon, but the national federation (FNC / Cenicafé) has bred and deployed disease-resistant varieties across smallholder farms. "
            "Today you'll see Castillo, Colombia, Caturra, Cenicafé 1, Tabi, and smaller plantings of heirloom Bourbon, Geisha, and Pacamara. "
            "Caturra and Castillo dominate Excelso grades. Variety information appears on most single-origin lot cards."
        ),
        "processing": (
            "Colombian coffee is overwhelmingly fully washed: 12-24 hour fermentation in concrete tanks, then patio or parabolic-dryer drying. "
            "Honey and natural processing has grown rapidly in the last decade, especially among microlot producers in Huila and Nariño. "
            "Anaerobic fermentation is the newest frontier — Colombian producers pioneered much of the current specialty-competition processing vocabulary."
        ),
        "harvest": (
            "Colombia is one of the few origins with two harvests per year — the main crop in October-January and the mitaca (fly crop) in April-June. "
            "This means fresh Colombian arrivals to Canadian warehouses spread across the calendar, so Colombia is always 'in season' somewhere on our inventory."
        ),
        "cupping_profile": (
            "A well-sourced Colombian cups like a specialty benchmark: milk chocolate and caramel sweetness, soft stone-fruit acidity (peach, red apple), subtle citrus lift, and a creamy, balanced body. "
            "Huila and Nariño lots push into tropical and berry territory. Lower-altitude Antioquia lots lean nutty and chocolate-forward. "
            "Colombia rarely surprises you in a bad way — it's the origin you can build a house blend around and never worry."
        ),
        "roasting_guidance": (
            "Colombian beans are large (screen 17-18) and roast predictably. Medium roasts (just past first-crack) highlight chocolate-caramel sweetness; light-medium roasts bring out the stone fruit and citrus. "
            "Colombia anchors most Canadian espresso blends because its body and sweetness tolerate both milk drinks and straight shots. Micro-roasters often stock a washed Huila for pour-over and a larger-bag Excelso EP as a blend base."
        ),
        "why_canada": (
            "Colombia is Canada's largest import origin by volume. Root 86 keeps eight or more Colombian lots in stock across Vancouver, Parksville, and Lévis at all times — washed Excelso for blend bases, microlots for pour-over programs, certified organic and Fair Trade lots, and women's-producer cooperative lots. "
            "Ask about our sample set if you're building a new Colombian-led blend."
        ),
    },
    "Brazil": {
        "headline": "Brazilian green coffee — espresso's classic foundation",
        "intro": "Brazil produces roughly a third of the world's coffee and is the backbone of countless espresso blends. The volcanic soils of Alta Mogiana, Sul de Minas Gerais, and Cerrado produce the smooth, low-acid, chocolate-and-nut profile that defines approachable coffee.",
        "context": "Root 86 stocks natural-process Brazilian lots from Alta Mogiana 17/18, Poços de Caldas, and Sul de Minas, plus Swiss Water Process Brazilian decaf. These are workhorses — reliable, sweet, and roast-flexible for espresso or drip.",
        "flavour": "Expect dark chocolate, hazelnut, caramel, brown sugar, almond, and dried fruit.",
        "regions": (
            "Brazilian specialty comes primarily from Minas Gerais, with Sul de Minas, the Cerrado Mineiro, and the Alta Mogiana border region as the three pillars. "
            "Sul de Minas' rolling hills and mild climate produce balanced, chocolatey, nutty cups at 800-1,200 m. "
            "Alta Mogiana, straddling Minas Gerais and São Paulo, is slightly higher and dryer, famous for larger-screen size 17/18 beans and an especially clean natural profile.\n\n"
            "The Cerrado plateau's flat terrain and pronounced dry season produce consistent, mechanized-harvest specialty lots with hallmark full-sun ripening. "
            "Bahia and Espírito Santo round out the Brazilian specialty map with more experimental single-estate projects. "
            "Poços de Caldas, on the Minas-São Paulo border, is a long-established estate region Root 86 sources from regularly."
        ),
        "varieties": (
            "Yellow and Red Bourbon, Catuaí, Catucaí, Mundo Novo, and Obatã are the dominant Brazilian varieties. "
            "Yellow Bourbon — a mutation that produces yellow cherries — is beloved by specialty producers for its particularly sweet cup. "
            "Increasingly you'll see Gesha, Pacamara, and experimental selections on microlot menus from smaller estates."
        ),
        "processing": (
            "Brazil is the spiritual home of natural-process coffee. The climate supports 2-4 week sun drying in whole cherry, producing the classic heavy, sweet, nutty Brazilian cup. "
            "Pulped-natural (a.k.a. Brazilian honey) processing — where the fruit skin is removed before drying, but the mucilage stays on — is widespread and creates a cleaner, more balanced cup without losing body. "
            "Fully washed Brazilians exist but are the exception."
        ),
        "harvest": (
            "Brazil's single-annual harvest runs May to September, with Canadian warehouse arrivals typically late fall to early winter. "
            "New-crop Brazilians stay stable for a long window — the robust processing and lower acidity mean they roast reliably for 9-12 months after arrival."
        ),
        "cupping_profile": (
            "A good Brazilian delivers dark chocolate, toasted hazelnut, almond, brown sugar, raisin, and baked-goods warmth. Acidity is soft and low, body is creamy-to-heavy, and sweetness carries the cup. "
            "Higher-altitude lots pick up red apple, caramel, and a hint of citrus; Cerrado coffees lean drier and more structured. "
            "Brazil is the coffee most North American drinkers intuitively think of as 'coffee-tasting' — and that's its superpower for espresso and milk drinks."
        ),
        "roasting_guidance": (
            "Brazilian beans tolerate a wide roast range. Light-medium pulls highlight hazelnut and cocoa nibs; medium-to-medium-dark roasts develop the classic caramel, dark chocolate, and baked-sugar espresso profile. "
            "Brazil is ideal as 40-70% of an espresso blend because of its body, sweetness, and low acidity. Canadian micro-roasters use Alta Mogiana specifically for its clean-burn behaviour and consistent bean size."
        ),
        "why_canada": (
            "Brazil is the most-used blend base in Canadian roasting because it stretches a budget and behaves predictably on every drum roaster. "
            "Root 86 keeps Alta Mogiana 17/18 and Poços de Caldas lots in Vancouver, Parksville, and Lévis, plus Swiss Water Process Brazilian decaf — bringing a consistent, sweet, chocolate-forward decaf option to roasters across Canada."
        ),
    },
    "Guatemala": {
        "headline": "Guatemalan green coffee — SHB intensity, volcanic complexity",
        "intro": "Guatemala's eight coffee regions each offer distinct character, from the bright, fruited Huehuetenango highlands to the rich, chocolatey lots around Lake Atitlán. SHB (Strictly Hard Bean) grading guarantees beans grown above 1,350 meters — dense, complex, and roast-tolerant.",
        "context": "Our Guatemalan catalogue includes washed SHB EP GP selections from Huehuetenango, Santa Rosa, and San Marcos, plus certified organic lots from Lake Atitlán. These coffees shine across the roast spectrum.",
        "flavour": "Expect milk chocolate, toffee, orange peel, apple, walnut, and dark cherry.",
        "regions": (
            "Anacafé officially recognizes eight Guatemalan coffee regions. Huehuetenango, in the northwestern highlands bordering Mexico, reaches 2,000 m and is celebrated for its bright, fruited washed lots with winey acidity. "
            "Antigua, grown in the shadow of three volcanoes, is smoky, rich, and deeply chocolatey. Atitlán (around the lake of the same name) delivers citric, balanced cups from organic-certified cooperatives.\n\n"
            "Cobán is a rainforest-climate region with lower-acidity, heavy-bodied lots. San Marcos and Santa Rosa, near the Pacific coast, are mid-altitude regions producing dependable specialty workhorses. "
            "Nuevo Oriente and Fraijanes round out the map. SHB (Strictly Hard Bean) grading labels lots grown above 1,350 m — the specialty tier."
        ),
        "varieties": (
            "Bourbon, Caturra, and Catuaí dominate Guatemalan plantings, with increasing amounts of Anacafé 14, Pache, Marsellesa, and Catimor on smallholder farms for leaf-rust resistance. "
            "Microlot producers in Huehuetenango and Antigua plant Geisha, Pacamara, and heirloom Bourbon for competition-grade cups."
        ),
        "processing": (
            "Guatemala is predominantly washed: wet-fermented for 18-36 hours, then washed and sun-dried on patios. "
            "Honey and natural processing has expanded rapidly in the last decade, particularly among Huehuetenango microlot producers. Many lots now specify 'Fully Washed EP GP' (European Preparation, Good Preparation) indicating careful hand-sorting and density grading."
        ),
        "harvest": (
            "Main-crop harvest runs November to April depending on altitude. Fresh-crop Guatemalan lots reach Canadian warehouses from late spring through summer, "
            "and the densest SHB beans from Huehuetenango hold up particularly well through 9-12 months of warehouse storage."
        ),
        "cupping_profile": (
            "Guatemalan SHB is the textbook complex Central American: milk chocolate and toffee backbone, bright orange-peel and apple acidity, a touch of dried cherry, and a walnut-nutty finish. "
            "Huehuetenango lots cup bright and winey with cherry and stone fruit. Antigua leans smoky-chocolate. Atitlán emphasizes lemon and red apple. "
            "Body is typically medium-full, structure is juicy, and the aftertaste is clean and lingering."
        ),
        "roasting_guidance": (
            "The dense SHB bean loves a slower development phase. Most Canadian roasters drop Guatemalan SHB at medium to full-city+ for espresso, or medium for drip to preserve acidity. "
            "Huehuetenango works beautifully as a single-origin pour-over; Antigua anchors darker espresso blends. Watch for second-crack timing — these coffees can push dark quickly if the batch is underdeveloped early."
        ),
        "why_canada": (
            "Guatemala is a top-three blend component for Canadian specialty roasters, prized for its complexity and roast-tolerance. "
            "Root 86 keeps Huehuetenango, Santa Rosa, and Lake Atitlán organic lots in all three Canadian warehouses. Ask about sample sets if you're trying to spot the regional differences for the first time."
        ),
    },
    "Costa Rica": {
        "headline": "Costa Rican green coffee — micromill precision",
        "intro": "Costa Rica's small-producer micromill movement transformed the country's specialty coffee in the 2000s. Today, growers in the West and Central Valleys, Tarrazú, and Tres Ríos produce honey-processed and washed lots of exceptional cleanliness and clarity.",
        "context": "Root 86 offers honey-processed microlots from Hacienda San Ignacio (Marsellesa hybrid), V&G Estate natural process lots, and classic washed Tarrazú SHB. These are Central American benchmarks.",
        "flavour": "Expect peach jam, raisin, brown sugar, vanilla, citrus, and milk chocolate.",
        "regions": (
            "Eight coffee regions are defined by Costa Rica's ICAFE: Tarrazú, Tres Ríos, Central Valley, West Valley, Turrialba, Brunca, Guanacaste, and Orosi. "
            "Tarrazú, south of San José, is the country's most famous — 1,400-1,900 m, volcanic soils, intensely clean cups. "
            "West Valley (Valle Occidental) around Naranjo and Palmares is the hotbed of the micromill revolution — small producers controlling their own processing for maximum cup clarity.\n\n"
            "The Central Valley, closer to San José, has the longest history of Costa Rican coffee growing. "
            "Tres Ríos produces balanced washed lots with exceptional structure. Brunca, near the Panama border, is an up-and-coming region for specialty Canadian roasters looking for something less-traveled."
        ),
        "varieties": (
            "Caturra, Catuaí, and Bourbon remain the staples of Costa Rican coffee. Villa Sarchí, a Bourbon mutation, is a local specialty with a distinctive sweet cup. "
            "Marsellesa, Obatã, and H1/Centroamericano hybrids are planted for leaf-rust resistance. Gesha, Villalobos, and SL28 appear on competition-tier microlots from Tarrazú and West Valley micromills."
        ),
        "processing": (
            "Costa Rica is the world's honey-process capital. The country's micromills grade honey lots by remaining mucilage: yellow honey (less mucilage, cleaner cup), red honey (medium), and black honey (most mucilage, funkiest cup). "
            "Fully washed Costa Rican coffee is meticulous and clean — typically 18-24 hours of tank fermentation and raised-bed drying. "
            "Natural-process Costa Ricans are rarer but increasingly common from producers like V&G Estate."
        ),
        "harvest": (
            "Harvest runs November through February, with Canadian warehouse arrivals March through June. "
            "Costa Rican beans are dense and high-grown — cup quality holds well through 10-12 months of proper warehouse storage at our Canadian facilities."
        ),
        "cupping_profile": (
            "Washed Tarrazú is the Central American benchmark: citric and floral acidity, peach-jam and red apple fruit, brown-sugar sweetness, milk chocolate body, clean aftertaste. "
            "Honey-processed microlots are funkier and sweeter — raisin, vanilla, stone fruit, and winey complexity. "
            "Natural-process Costa Ricans lean toward strawberry, tropical fruit, and red wine. Structure is almost always the defining word: balanced, clean, refined."
        ),
        "roasting_guidance": (
            "Costa Rican lots roast predictably thanks to uniform bean size and density. Light-medium roasts highlight stone fruit and floral notes; medium roasts emphasize sweetness and body. "
            "Honey-process lots benefit from a slightly slower development phase to tame the residual fruit sugars. Canadian micro-roasters often pair Costa Rican with Colombia or Ethiopia in pour-over programs."
        ),
        "why_canada": (
            "Costa Rica is a favourite of Canadian cupping-focused roasters because of its exceptional clarity and consistency. "
            "Root 86's Costa Rican lineup includes classic Tarrazú SHB, Hacienda San Ignacio Marsellesa microlots, and V&G Estate natural process coffees — all stocked in Vancouver, Parksville, and Lévis."
        ),
    },
    "Kenya": {
        "headline": "Kenyan green coffee — wine-like, savoury, unmistakable",
        "intro": "Kenya is the connoisseur's origin. Double-washed fermentation and meticulous sorting (AA, AB Plus grades) produce the distinctive blackcurrant-and-tomato-juice profile that Kenyan SL28 and SL34 varieties are famous for.",
        "context": "Our Kenya AB Plus Sondhi delivers that wine-like complexity at specialty-grade quality. A roaster's coffee — bold, bright, uncompromising.",
        "flavour": "Expect blackcurrant, tomato, grapefruit, dark berry, and bright acidity.",
        "regions": (
            "Kenyan specialty coffee grows across the central highlands — Nyeri, Kirinyaga, Muranga, Embu, Kiambu, Machakos, and the Mt. Elgon foothills in the west. "
            "Nyeri and Kirinyaga, on the slopes of Mt. Kenya, produce the most intense, blackcurrant-led cups. "
            "Kiambu and Murang'a deliver slightly softer, more berry-forward lots. The Kenya Coffee Board auction system funnels most specialty volume through centralized grading and scoring in Nairobi."
        ),
        "varieties": (
            "Kenya is famously home to SL28 and SL34 — Scott Laboratories selections bred in the 1930s for drought tolerance and cup quality. These two varieties deliver Kenya's signature intensity. "
            "Ruiru 11 and Batian are modern disease-resistant releases planted widely on smaller farms. K7 and French Mission Bourbon round out the plantings. SL28 in particular is prized for its deep, berry-forward cup."
        ),
        "processing": (
            "Kenya's double-wash fermentation is the country's signature: coffee ferments for 24-48 hours, is washed, ferments again in clean water for another 12-24 hours, then is soaked and dried on raised beds. "
            "This labour-intensive process gives Kenyan coffee its exceptionally clean, juicy, bright cup. Density grading (AA for largest/densest beans, AB for slightly smaller, PB for peaberry) is done at the factory level."
        ),
        "harvest": (
            "Kenya has two harvests: the main crop (October-December) and a smaller fly crop (April-June). Main-crop lots reach Canadian warehouses February through May. "
            "Kenyan AA and AB lots hold their intense profile well for 6-9 months; plan fresh-crop ordering to keep the black-currant notes at their peak."
        ),
        "cupping_profile": (
            "Kenyan coffee cups unmistakably: blackcurrant, tomato-juice, grapefruit, red-wine, dark berry, savoury and jammy. "
            "Acidity is phosphoric-bright and winey; body is syrupy and juicy. The finish is long, lingering, and savoury — Kenyan coffee has umami in a way no other origin matches. "
            "For some palates Kenya is challenging; for trained palates it's the most exciting origin on earth."
        ),
        "roasting_guidance": (
            "Kenya shines at light-medium roasts where the acidity and fruit stay vibrant. Darker roasts flatten the distinctive blackcurrant note. "
            "Canadian micro-roasters typically drop Kenyan AB/AA at or just past first-crack-end for pour-over, or push slightly darker for milk-espresso where the juiciness supports lattes. Be patient during drying — Kenya's dense beans reward a slower charge."
        ),
        "why_canada": (
            "Kenyan coffee anchors the single-origin programs of almost every top Canadian specialty roaster. Root 86 stocks Kenya AB Plus Sondhi across our three Canadian warehouses. "
            "Sample a Kenyan alongside an Ethiopian washed and a Colombian microlot to understand the East African specialty spectrum."
        ),
    },
    "Honduras": {
        "headline": "Honduran green coffee — approachable Central American sweetness",
        "intro": "Honduras is Central America's largest coffee producer and a reliable source of well-priced specialty lots. The highland regions of Copán, Marcala, and the western cordilleras produce soft, sweetly balanced coffees ideal for everyday blends.",
        "context": "We carry SHG (Strictly High Grown) Copán organic, Lempira SHG Tierra Lenca, and Swiss Water Process Honduras decaf. Gentle, approachable, and roast-flexible.",
        "flavour": "Expect peach, caramel, toasted nuts, apple, and milk chocolate.",
        "regions": (
            "Honduras recognizes six coffee regions: Copán, Opalaca, Montecillos, Comayagua, El Paraíso, and Agalta. "
            "Copán, in the west near the Guatemalan border, is the most recognized — volcanic soils, 1,200-1,700 m, balanced fruit-and-chocolate cups. "
            "Montecillos (home of the Marcala appellation) produces some of the cleanest washed Honduran coffees.\n\n"
            "El Paraíso and Agalta, farther east, have grown rapidly as specialty regions. The Lempira region and the Tierra Lenca designation (after the Lenca indigenous people) mark coffees from the central-western highlands with strong traceability back to smallholder cooperatives."
        ),
        "varieties": (
            "Catuaí, Bourbon, Typica, Lempira, and Parainema are the common Honduran plantings. IHCAFE (the Honduran coffee institute) has released disease-resistant cultivars specifically for smallholder conditions. "
            "Pacas (a Bourbon mutation) and Caturra are common on specialty farms. Most smallholder cooperatives plant a mix of varieties for resilience."
        ),
        "processing": (
            "Honduras is predominantly fully washed: 18-36 hour tank fermentation, mechanical or manual washing, and sun drying on patios or raised beds. "
            "Honey and natural processing have expanded rapidly among specialty-focused producers. "
            "Many Canadian-imported Honduran lots are certified organic, Fair Trade, or both — cooperative structures make certification accessible to smallholders here."
        ),
        "harvest": (
            "Harvest runs November through April depending on altitude. Fresh-crop Honduran lots reach Canadian warehouses April through August. "
            "The gentler profile of Honduran coffee holds up well in storage — these lots are ideal for blend-base buying across the calendar."
        ),
        "cupping_profile": (
            "Honduran SHG cups soft and sweet: peach, apple, caramel, toasted almond, milk chocolate, a touch of citrus. Acidity is mild and fruity, body is medium, sweetness is the star. "
            "Higher-altitude lots from Copán and Marcala push into stone-fruit and floral territory. Honduran coffee is approachable — it never shocks a palate and rarely disappoints."
        ),
        "roasting_guidance": (
            "Honduran beans roast predictably across a wide range. Medium roasts bring out the peach and apple; medium-dark roasts develop the caramel and chocolate for espresso. "
            "Honduras works beautifully as a 20-40% component in a Central American espresso blend, bringing sweetness and drinkability. Canadian roasters often stock a Honduran SHG organic as an accessible single-origin for shop menus."
        ),
        "why_canada": (
            "Honduras is an important certified-organic origin for the Canadian specialty market. "
            "Root 86 keeps Copán SHG Organic, Lempira SHG Tierra Lenca Organic, and Swiss Water Process Honduran decaf at all three Canadian warehouses — approachable, well-priced, and certified."
        ),
    },
    "Mexico": {
        "headline": "Mexican green coffee — organic specialty from Chiapas and Oaxaca",
        "intro": "Mexico is North America's closest specialty origin and a leader in certified organic production. Chiapas and Oaxaca dominate Mexico's fine coffee output, with indigenous smallholder cooperatives producing some of the world's most consistently organic-certified lots.",
        "context": "Root 86 imports SHG organic selections from Chiapas (including producer-named Angel Diaz) and Oaxaca Pluma. We also offer Mexican Mountain Water Process decaf — the gold standard of chemical-free decaffeination.",
        "flavour": "Expect hazelnut, milk chocolate, caramel, orange, dried apricot, and honey.",
        "regions": (
            "Chiapas, in the southern highlands bordering Guatemala, is Mexico's dominant specialty region. Chiapas SHG (Strictly High Grown) lots come from indigenous cooperatives across Sierra Madre altitudes of 1,200-1,700 m. "
            "Oaxaca's Pluma and Sierra Sur regions produce cleaner, more citric washed cups. Veracruz, on the Gulf side, contributes volume specialty through its highland Coatepec region. "
            "Puebla and Guerrero round out the smaller specialty origins. Nearly 90% of Mexican specialty export is smallholder-produced, often organic-certified through cooperative structures."
        ),
        "varieties": (
            "Typica, Bourbon, Caturra, and Mundo Novo dominate traditional plantings. Marsellesa, Oro Azteca, and Garnica are modern disease-resistant releases. "
            "Many smallholder farms in Chiapas and Oaxaca maintain mixed-variety plots with shade-grown canopy."
        ),
        "processing": (
            "Mexican specialty is almost exclusively fully washed — smallholder cooperative infrastructure centres on shared depulpers, fermentation tanks, and patio drying. "
            "The Mountain Water Process decaffeination, done in Veracruz, is the cleanest chemical-free decaf method available. It uses only pure glacial mountain water from the Pico de Orizaba to strip caffeine while preserving flavour compounds."
        ),
        "harvest": (
            "Mexican harvest runs October through March. Fresh-crop lots reach Canadian warehouses April through August — the closest origin geography to Canada means shortest transit times."
        ),
        "cupping_profile": (
            "Mexican SHG cups gently: hazelnut, milk chocolate, caramel, toasted almond, soft citrus, and a touch of honey. Acidity is mild and pleasant, body is medium, sweetness carries the cup. "
            "Higher-altitude Chiapas lots bring more stone fruit and dried apricot. Oaxaca leans citric and clean. Overall profile is approachable, blend-friendly, and reliably consistent."
        ),
        "roasting_guidance": (
            "Mexican beans are moderate density and roast forgivingly. Light-medium for single-origin programs, medium-dark for espresso blends. "
            "The MWP decaf behaves similarly to a washed Central American — not stripped of body or character. Many Canadian roasters anchor a decaf espresso blend entirely on Mexican MWP."
        ),
        "why_canada": (
            "Mexico is the closest specialty origin to Canada, offering shorter shipping times and a strong organic-certified supply. "
            "Root 86 keeps Chiapas SHG organic (including single-producer lots), Oaxaca Pluma, and Mountain Water Process decaf organic across all three Canadian warehouses."
        ),
    },
    "Peru": {
        "headline": "Peruvian green coffee — Andean organic specialty",
        "intro": "Peru produces more certified organic coffee than almost any other country. The cloud forests of Cajamarca, Amazonas, and San Martín grow Bourbon, Typica, and Caturra varieties at extreme altitude on small indigenous farms.",
        "context": "Our El Gran Mirador certified organic lot is a standout — bright, floral, sweetly balanced. We also carry Swiss Water Process Peru decaf organic.",
        "flavour": "Expect peach, caramel, milk chocolate, floral, almond, and dried fruit.",
        "regions": (
            "Northern Peru dominates specialty production: Cajamarca, Amazonas, and San Martín regions grow coffee at 1,400-2,100 m on the eastern Andean slopes. "
            "The Jaén and San Ignacio areas in Cajamarca are the most recognized for specialty cup quality. "
            "Cusco and Puno contribute southern-region specialty with distinct profiles. Most Peruvian specialty is smallholder-produced (1-5 hectare plots) through FLO-certified cooperatives."
        ),
        "varieties": (
            "Typica, Bourbon, Caturra, Catimor, and Pache are the common Peruvian varieties. Heirloom Typica from the northern cloud-forest regions is particularly prized for its delicate, floral cup. "
            "Variety diversity on a single smallholder farm is common and contributes to Peruvian coffee's layered complexity."
        ),
        "processing": (
            "Peru is predominantly fully washed. Smallholder producers ferment 18-30 hours in wooden or concrete tanks and sun-dry on patios or rooftop beds. "
            "Natural processing is rarer but growing. The extreme altitude and cool climate make drying slower and more controlled than lower-elevation origins."
        ),
        "harvest": (
            "Peruvian harvest runs May through October — a reverse calendar from Central America. Fresh-crop arrivals reach Canadian warehouses late fall through winter, "
            "making Peru an excellent mid-year blend rotation when other certified-organic origins are running low."
        ),
        "cupping_profile": (
            "A well-sourced Peruvian is delicate and balanced: peach, apricot, milk chocolate, caramel, floral notes (often jasmine or honeysuckle), and a hint of almond. "
            "Acidity is soft and malic; body is medium-light; sweetness is honeyed. Higher-altitude lots cup more complex with stone-fruit and floral intensity. Peru is the quiet, refined origin — easy to love on pour-over."
        ),
        "roasting_guidance": (
            "Peruvian beans are large and moderately dense. Light-medium roasts preserve the floral and stone-fruit aromatics. Medium roasts develop the chocolate and caramel for espresso use. "
            "Peru pairs well with Colombia in blends where you want to add floral lift without sacrificing approachability."
        ),
        "why_canada": (
            "Peru is one of the top certified-organic origins on the Canadian specialty market. "
            "Root 86's El Gran Mirador Organic and SWP Peru Decaf Organic serve Canadian roasters looking for traceable, smallholder, certified-organic supply year-round."
        ),
    },
    "Rwanda": {
        "headline": "Rwandan green coffee — Bourbon on volcanic soil",
        "intro": "Rwanda's specialty revival, led by women's producer cooperatives, has made it one of East Africa's most exciting specialty origins. The country grows almost exclusively Red Bourbon on volcanic soils at 1,700-2,000 meters.",
        "context": "Our Nyampinga Organic Women's COOP represents the best of Rwanda — Kinyarwanda for 'beautiful girl', the lot supports the cooperative's female members directly. Deeply fruited, floral, and clean.",
        "flavour": "Expect raspberry, plum, caramel, rose, and bright acidity.",
        "regions": (
            "Rwanda's coffee grows on the slopes of the Virunga volcanic range and around Lakes Kivu and Muhazi. "
            "Major specialty regions include the Western Province (around Lake Kivu — including Kabuye and Gakenke districts), Northern Province (Rulindo and Gakenke), and the Southern Province (Huye and Nyamagabe). "
            "Every specialty lot is microlot-traceable to a specific washing station and harvest day."
        ),
        "varieties": (
            "Rwanda grows almost exclusively Red Bourbon, a heirloom selection perfectly suited to the country's high altitude and volcanic soils. "
            "Small amounts of Jackson and Mibirizi are planted on experimental lots. The varietal uniformity makes Rwandan coffee remarkably consistent by terroir."
        ),
        "processing": (
            "Rwandan specialty is overwhelmingly fully washed through centralized washing stations. 18-36 hour tank fermentation, extensive clean-water washing, and raised-bed sun drying for 2-3 weeks deliver the signature clean, bright Rwandan cup. "
            "Some honey and natural processing exists for microlot experimentation. The 'potato defect' — a rare Rwandan-specific issue — is managed through careful sorting at specialty washing stations."
        ),
        "harvest": (
            "Rwanda's main harvest runs March through July. Fresh-crop Rwandan arrivals to Canadian warehouses land August through November. Rwandan washed lots hold their bright, fruity profile well for 6-9 months after arrival."
        ),
        "cupping_profile": (
            "A fresh-crop Rwandan cups jammy and bright: raspberry, plum, red grape, rose, caramel, milk chocolate, and a lifted acidity reminiscent of Kenya but softer. Body is medium and syrupy. "
            "Women's-producer lots and organic-certified microlots often show extra floral and stone-fruit complexity."
        ),
        "roasting_guidance": (
            "Rwandan beans love a light-medium roast that preserves the berry and floral complexity. Push too dark and the bright acidity flattens into generic East African darkness. "
            "Canadian micro-roasters often feature Rwandan Bourbon as a seasonal single-origin pour-over, or use it as the bright component in a blend with Brazil or Colombia."
        ),
        "why_canada": (
            "Rwanda is a rising origin on Canadian specialty menus, valued for its cup quality and its alignment with women's-producer and organic certification priorities. "
            "Root 86 stocks Nyampinga Organic Women's COOP across Vancouver, Parksville, and Lévis."
        ),
    },
    "Tanzania": {
        "headline": "Tanzanian green coffee — Kilimanjaro sweetness, Southern brightness",
        "intro": "Tanzania produces two distinct coffee styles: the classic Northern lots from the slopes of Mount Kilimanjaro (Kent, Bourbon, Blue Mountain varieties) and the emerging Southern Highlands offering.",
        "context": "We stock PB Plus (Peaberry) from both Northern Kilimanjaro and Southern estates. Peaberry beans are the naturally-occurring single-bean cherry — concentrated sweetness and flavour.",
        "flavour": "Expect blackberry, citrus, dark chocolate, plum, and mandarin.",
        "regions": (
            "Tanzania's specialty splits into two geographies. The Northern Highlands — Kilimanjaro, Arusha, and the Mbulu/Mbinga areas — produce the classic Tanzanian washed cup at 1,200-1,900 m. "
            "The Southern Highlands — Mbeya and Ruvuma — have grown into a major specialty origin in the last two decades, with large estates producing traceable lots at comparable altitudes. "
            "The Usambara Mountains contribute a smaller volume of specialty from the Tanga region."
        ),
        "varieties": (
            "Kent, Bourbon, Blue Mountain (a selection brought from Jamaica), Typica, and Compact Bourbon dominate Tanzanian plantings. "
            "N39, KP423, SL28, and SL34 are also planted on specialty estates. Peaberry (PB) is not a variety but a natural genetic occurrence — about 5% of any coffee crop produces single-bean cherries, which are sorted and sold separately."
        ),
        "processing": (
            "Tanzania is predominantly fully washed: 24-48 hour fermentation, patio or raised-bed drying. Peaberry sorting happens at the mill — the single beans are graded and exported separately. "
            "Natural and honey processing is growing in the Southern Highlands among specialty-focused estates."
        ),
        "harvest": (
            "Tanzanian harvest runs July through December. Fresh-crop arrivals reach Canadian warehouses January through May. Peaberry lots are particularly stable in storage."
        ),
        "cupping_profile": (
            "Tanzanian PB cups bright and complex: blackberry, plum, mandarin, citrus peel, dark chocolate, black tea, and a winey structure reminiscent of Kenya. "
            "Northern Kilimanjaro lots tend toward dark chocolate and stone fruit. Southern estates push brighter with more citric acidity. Body is typically medium; acidity is juicy."
        ),
        "roasting_guidance": (
            "Tanzanian PB beans are smaller than regular AA/AB — adjust batch profiles accordingly. Light-medium roasts preserve the fruit and brightness; medium roasts develop the dark-chocolate body for milk-drink espresso. "
            "PB is beloved by Canadian filter-program roasters for its concentrated sweetness."
        ),
        "why_canada": (
            "Tanzania offers Kenya-adjacent cup complexity at a more accessible price point — an important option for Canadian roasters building East African single-origin programs. "
            "Root 86 keeps Northern Kilimanjaro PB Plus and Southern Estate PB Plus at our Vancouver, Parksville, and Lévis warehouses."
        ),
    },
    "Uganda": {
        "headline": "Ugandan green coffee — Mt. Elgon AA, Kenya-adjacent complexity",
        "intro": "Uganda's Mt. Elgon region shares terroir with Kenya across the border — high altitude, rich volcanic soils, and SL14/SL28 varieties. The result is a Kenyan-style cup at an accessible price point.",
        "context": "Our Mt. Elgon AA Rainforest Alliance certified lot delivers exactly that: complex, fruit-forward, bold.",
        "flavour": "Expect apricot, dark berry, dark chocolate, cedar, and bright acidity.",
        "regions": (
            "Ugandan specialty Arabica grows on Mt. Elgon (bordering Kenya to the east) and the Rwenzori Mountains (bordering the DRC to the west). Mt. Elgon is the dominant specialty region — volcanic soils, 1,500-2,200 m, SL-family varieties. "
            "The Bugisu region on Mt. Elgon and the Bukonzo region in the Rwenzoris deliver the Kenya-adjacent cup profiles Canadian roasters prize. "
            "Uganda also produces substantial Robusta from the lowlands, but specialty Canadian imports are almost exclusively high-altitude Arabica."
        ),
        "varieties": (
            "SL14, SL28, and SL34 — Scott Laboratories selections — are the dominant Mt. Elgon Arabica varieties, the same cultivars that define Kenyan specialty cup. "
            "Nyasaland and Bugisu local selections are also planted. The variety genetics explain the Kenya-like cup profile on the Ugandan side of the mountain."
        ),
        "processing": (
            "Ugandan specialty Arabica is fully washed through cooperative washing stations or estate-level processing. 24-48 hour fermentation, patio and raised-bed drying. "
            "Rainforest Alliance certification is common on Mt. Elgon lots, reflecting the region's focus on sustainable smallholder production."
        ),
        "harvest": (
            "Mt. Elgon harvest runs October through February. Fresh-crop Ugandan arrivals reach Canadian warehouses April through August."
        ),
        "cupping_profile": (
            "Ugandan Mt. Elgon AA cups surprisingly Kenya-like: apricot, black currant, dark berry, dark chocolate, cedar, molasses, and a bright juicy acidity. "
            "It's bolder and less refined than top Kenyan AA but offers much of the same complexity at a lower cost point. Body is medium-full; structure is winey."
        ),
        "roasting_guidance": (
            "Mt. Elgon AA roasts similarly to Kenyan AA — light-medium for maximum complexity, medium for milk-drink espresso. Watch the dense bean during drying and Maillard. "
            "Works beautifully in an East African single-origin program or as the bright component in a more-budget-friendly blend."
        ),
        "why_canada": (
            "Uganda is an underappreciated origin that offers Kenya-adjacent cup quality at an accessible price. "
            "Our Mt. Elgon AA Rainforest Alliance certified lot is stocked at all three Canadian warehouses."
        ),
    },
    "Indonesia": {
        "headline": "Indonesian green coffee — Sumatra Mandheling and beyond",
        "intro": "Indonesia produces some of the most distinctive coffees in the world. Sumatra's Giling Basah (wet-hulling) process creates the iconic low-acid, full-body, earthy-herbal Mandheling profile. Sulawesi, Java, and Flores offer their own terroir stories.",
        "context": "Root 86 imports Sumatra Mandheling Grade 1 (both standard and Women's Producer Organic) and Indonesia Flores Rainforest Alliance Organic. Deep, bold, and complex — the cornerstone of many espresso blends.",
        "flavour": "Expect dark chocolate, tobacco, earth, cedar, molasses, and clove.",
        "regions": (
            "Sumatra's Aceh province (Gayo Highlands, around Lake Tawar) and North Sumatra province (Lintong, around Lake Toba) are the specialty heartlands, producing the iconic Mandheling profile at 1,100-1,600 m. "
            "Sulawesi's Toraja highlands deliver cleaner, more classic washed profiles at high altitude. Java's Ijen Plateau produces washed coffees with history dating to the Dutch colonial era. "
            "Flores, Bali, and Papua contribute smaller-volume specialty with distinct local character."
        ),
        "varieties": (
            "Sumatra plants Typica, Bourbon, Catimor, TimTim (Timor Hybrid), Sigarar Utang, Ateng, and Ramung. The dense variety mix and Giling Basah processing produce Sumatra's characteristic cup. "
            "Sulawesi focuses on S795, Typica, and Bourbon. Flores grows Typica, Bourbon, and local selections."
        ),
        "processing": (
            "Giling Basah (wet-hulling) is Sumatra's signature process and unlike any other origin: coffee is pulped, briefly fermented, then hulled while still wet at 30-50% moisture. "
            "The beans finish drying after hulling, resulting in the characteristic blue-green colour, unusual hook shape, and earthy-herbal-woody cup profile. "
            "Sulawesi and Java use more conventional washed processing. Natural and honey processing is growing among specialty-focused Indonesian estates."
        ),
        "harvest": (
            "Indonesian harvest runs year-round in some regions (Sumatra has a main crop May-November and smaller fly crops). Fresh-crop arrivals reach Canadian warehouses across the calendar. "
            "Sumatra's Giling Basah coffee is remarkably stable in storage — often a year or more at specialty grade."
        ),
        "cupping_profile": (
            "Sumatra Mandheling Grade 1 cups unmistakably: dark chocolate, tobacco, cedar, molasses, clove, stewed fruit, earthy-herbal depth, and a full heavy body with low acidity. "
            "Sulawesi Toraja is cleaner and brighter — still deep-bodied but with more structure and stone-fruit. Flores brings chocolate, nut, and gentle spice. "
            "Indonesian coffees are the antithesis of bright East African; they ground an espresso blend or a winter menu."
        ),
        "roasting_guidance": (
            "Sumatra's irregular, blue-green beans roast unevenly if pushed too fast — give them time in drying and early Maillard. Medium to medium-dark roasts develop the classic espresso profile; darker roasts emphasize the molasses and cedar. "
            "Sumatra is the classic 20-40% component in a full-bodied espresso blend paired with Brazil and a Central American."
        ),
        "why_canada": (
            "Sumatra is the defining espresso-base for Canadian cafes that favour darker roasting. "
            "Root 86 keeps Sumatra Mandheling G1, Sumatra Mandheling Women's Producer Organic, and Flores Rainforest Alliance Organic across all three Canadian warehouses."
        ),
    },
    "Panama": {
        "headline": "Panamanian green coffee — Boquete refinement",
        "intro": "Panama's Boquete region, nestled in Chiriquí province, produces some of the world's most refined coffees. Volcanic soils, cool nights, and careful micromill processing create cups of exceptional elegance.",
        "context": "Our Boquete Finca La Santa Catuai single-variety lot showcases Panama's best: floral, nuanced, beautifully balanced.",
        "flavour": "Expect honey, orange blossom, stone fruit, brown sugar, and creamy body.",
        "regions": (
            "Boquete in Chiriquí province, on the slopes of Volcán Barú, is Panama's dominant specialty region — 1,200-1,900 m, volcanic soils, cool Pacific-influenced climate. "
            "Volcán-Candela, north of Boquete, produces comparable elevation lots with slightly drier terroir. Small amounts of specialty also come from eastern Chiriquí and the Renacimiento district."
        ),
        "varieties": (
            "Catuaí, Caturra, Typica, and Bourbon are traditional. Panama is also ground-zero for Gesha (Geisha) — the variety was rediscovered and popularized by Hacienda La Esmeralda in 2004. "
            "Pacamara and SL28 round out the specialty-microlot plantings. Single-variety lot labelling is standard in Panama, an indicator of the region's microlot sophistication."
        ),
        "processing": (
            "Panama's micromill culture is among the most refined in the world. Fully washed, honey, natural, and anaerobic processing are all practiced, often with extensive experimentation at competition-grade estates. "
            "Raised-bed drying and extended cherry-sorting are standard."
        ),
        "harvest": (
            "Panamanian harvest runs November through March. Fresh-crop Panamanian lots reach Canadian warehouses April through July. The refined processing and high altitude mean Panamanian coffees hold well in storage."
        ),
        "cupping_profile": (
            "A well-sourced Boquete Catuai or Caturra cups elegantly: honey, orange blossom, white peach, brown sugar, creamy body, malic acidity, and a long clean finish. "
            "Competition-grade Gesha from Panama is another universe — intensely floral, jasmine-tea-like, tropical-fruit-forward. Everyday Boquete lots offer much of the refinement at a far more accessible price."
        ),
        "roasting_guidance": (
            "Panamanian beans are large and dense — reward slow, patient roasts. Light-medium is ideal for pour-over and filter programs; medium develops the honey-caramel body for espresso. "
            "Gesha lots deserve light-roast treatment to preserve the floral character."
        ),
        "why_canada": (
            "Panama occupies a specific niche in the Canadian specialty market — refined, elegant, often used as a seasonal single-origin pour-over. "
            "Root 86's Finca La Santa Catuai Boquete lot is a beautiful entry point to Panamanian coffee, stocked at our Canadian warehouses."
        ),
    },
    "Nicaragua": {
        "headline": "Nicaraguan green coffee — Jinotega shade-grown organic",
        "intro": "Nicaragua's northern highlands — especially Jinotega, Matagalpa, and Nueva Segovia — produce reliable specialty coffee under native shade canopy. Small cooperative producers dominate Nicaraguan specialty output.",
        "context": "Our Jinotega FT Organic is a clean, sweetly balanced certified Fair Trade and Organic lot from highland Jinotega cooperatives.",
        "flavour": "Expect milk chocolate, almond, apple, and caramel.",
        "regions": (
            "Jinotega, Nicaragua's largest specialty-producing department, accounts for roughly two-thirds of the national specialty crop. Farms sit at 1,100-1,700 m in a cloud-forest climate. "
            "Matagalpa, south of Jinotega, produces similar profiles with slightly more body. Nueva Segovia, in the far north, has gained reputation for its brighter, more complex cups in the last decade. "
            "Most specialty Nicaraguan coffee is produced by small cooperatives with strong Fair Trade and organic certification rates."
        ),
        "varieties": (
            "Caturra, Catuaí, Bourbon, Maragogype, Pacamara, and Typica are the common Nicaraguan varieties. Pacamara — a Salvadoran-bred giant bean — is especially prized on microlot offerings. "
            "Most cooperative volume coffee is Caturra and Catuaí."
        ),
        "processing": (
            "Nicaragua is predominantly fully washed. Honey and natural processing has expanded among microlot producers, particularly in Nueva Segovia. "
            "Certified Fair Trade and Organic lots are common — the cooperative structure makes certification accessible to smallholder producers."
        ),
        "harvest": (
            "Harvest runs November through March. Fresh-crop Nicaraguan lots reach Canadian warehouses May through August."
        ),
        "cupping_profile": (
            "Jinotega FT Organic cups clean and sweet: milk chocolate, toasted almond, red apple, soft citrus, caramel, and a gentle honeyed finish. Acidity is mild, body is medium, sweetness is the primary attribute. "
            "Higher-altitude Nueva Segovia lots bring more stone fruit and winey brightness."
        ),
        "roasting_guidance": (
            "Nicaraguan beans roast predictably and forgivingly — medium for single-origin pour-over, medium-dark for espresso blending. "
            "Nicaragua anchors Canadian house blends well because of its sweetness and approachability."
        ),
        "why_canada": (
            "Nicaragua is a key certified-organic and Fair Trade origin for Canadian specialty roasters committed to smallholder-cooperative sourcing. "
            "Root 86 stocks Jinotega FT Organic across all three Canadian warehouses."
        ),
    },
    "Papua New Guinea": {
        "headline": "Papua New Guinea green coffee — heritage Arabica from Simbu Highlands",
        "intro": "Papua New Guinea's remote highlands grow some of the world's most isolated and traditionally-farmed Arabica. Smallholder gardens of Arusha, Bourbon, and Typica thrive at 1,500-1,800 meters in the Simbu province.",
        "context": "Our PSC (Premium Smallholder Coffee) Simbu lot is uniquely complex — tropical fruit, cocoa, and gentle spice with lingering sweetness.",
        "flavour": "Expect tropical fruit, cocoa, black tea, and sweet spice.",
        "regions": (
            "PNG specialty coffee grows in the highland provinces of Eastern Highlands, Western Highlands, Chimbu (Simbu), and Jiwaka. "
            "Simbu, in the central highlands, grows at 1,500-1,900 m and is the source of our PSC lot. "
            "The Arusha, Wahgi, and Asaro valleys produce the majority of PNG's specialty volume. Most PNG coffee is smallholder-grown on 'coffee gardens' of 20-100 trees per household — there are no large-scale estates in the specialty tier."
        ),
        "varieties": (
            "Arusha (a Typica-Bourbon cross), Bourbon, Typica, and Mundo Novo are the traditional PNG varieties. "
            "Catimor and new hybrid releases are planted for disease resistance. The isolation of PNG coffee gardens means genetic drift has produced distinctive local selections you won't find elsewhere."
        ),
        "processing": (
            "PNG specialty is predominantly fully washed through small-scale depulping and patio/raised-bed drying at the village or cooperative level. "
            "The 'PSC' designation (Premium Smallholder Coffee) marks lots assembled from small producers and prepared to specialty standards at central mills."
        ),
        "harvest": (
            "PNG harvest runs April through September. Fresh-crop PSC arrivals to Canadian warehouses land November through March."
        ),
        "cupping_profile": (
            "PNG Simbu PSC cups with tropical complexity: mango, pineapple, cocoa, black tea, gentle baking spice, and a creamy, honeyed body. "
            "Acidity is soft and juicy; body is medium-full; sweetness lingers long. It's a distinctive cup — not quite like any other origin — and Canadian roasters often feature it as a seasonal single-origin for its exotic profile."
        ),
        "roasting_guidance": (
            "PNG beans are moderate density and roast forgivingly. Medium roasts highlight the tropical fruit and cocoa; medium-dark roasts deepen the chocolate-spice for espresso. Works beautifully as a 10-20% component in a distinctive single-origin-leaning blend."
        ),
        "why_canada": (
            "PNG offers Canadian roasters a genuinely different cup — tropical-fruit-and-cocoa territory not found in Central or South American origins. "
            "Root 86 imports PSC Simbu when seasonal quality aligns, stocking at our three Canadian warehouses."
        ),
    },
    "Blend": {
        "headline": "Blended green coffee — espresso-ready selections",
        "intro": "Our purpose-crafted blends give you consistent, roast-ready foundations for specialty espresso programs. Pre-blended green coffee simplifies small-roaster inventory — one SKU produces a consistent finished cup.",
        "context": "Root 86's blended offerings include the SWP Premium Espresso Blend Decaf — engineered for thick crema, deep body, and rich chocolatey sweetness, all without caffeine.",
        "flavour": "Expect dark chocolate, toffee, clean crema body.",
        "regions": (
            "Our blends combine origins for specific cup outcomes — Central and South American bases for body and sweetness, East African or washed Central American components for lift, and Indonesian components for depth when called for."
        ),
        "varieties": (
            "Varieties in our blends reflect the underlying origin components. Most are Caturra, Catuaí, Bourbon, and Typica with occasional microlot specialty additions."
        ),
        "processing": (
            "Blend components typically match on processing style — our SWP Decaf Blend uses Swiss Water Process decaf beans exclusively, guaranteeing a chemical-free drinking experience."
        ),
        "harvest": (
            "Blend availability tracks the underlying origin harvests. Because multiple origins feed a blend, seasonal supply is smoother than any single-origin component."
        ),
        "cupping_profile": (
            "Our SWP Premium Espresso Blend Decaf cups as a full-bodied espresso base: dark chocolate, toffee, toasted nut, brown sugar, clean crema, and a smooth decaf finish with no chemical aftertaste."
        ),
        "roasting_guidance": (
            "Blends roast best at a single profile — aim for espresso-appropriate medium-dark. Watch for variable component behaviour during drying if you mix components yourself at the roaster."
        ),
        "why_canada": (
            "Pre-blended green coffee simplifies inventory for smaller Canadian micro-roasters. Root 86's SWP Espresso Blend Decaf delivers a complete decaf program in a single SKU across our three Canadian warehouses."
        ),
    },
    "El Salvador": {
        "headline": "Salvadoran green coffee — specialty from Santa Ana",
        "intro": "El Salvador's highland Santa Ana region produces some of Central America's most refined Bourbon and Pacamara lots — silky body, honeyed sweetness, clean cup.",
        "context": "We feature traceable Salvadoran specialty lots when available, prioritizing single-estate and cooperative-producer selections.",
        "flavour": "Expect hazelnut, sweet chocolate, dark honey, silky body.",
        "regions": (
            "Santa Ana, in the western highlands around the Ilamatepec volcano (1,200-1,800 m), produces the majority of Salvadoran specialty coffee. "
            "Ahuachapán, in the northwest corner, contributes smaller-volume specialty. Chalatenango's El Balsamar region produces interesting highland lots as well."
        ),
        "varieties": (
            "El Salvador is the ancestral home of Pacas (a Bourbon mutation) and Pacamara (a Pacas x Maragogype cross bred in the 1950s — now one of specialty coffee's most prestigious varieties). "
            "Bourbon remains the traditional staple. Caturra, Catuaí, and Catisic are also planted."
        ),
        "processing": (
            "Salvadoran specialty is predominantly fully washed — 18-36 hour fermentation, patio or raised-bed drying. "
            "Honey processing, particularly 'black honey' and 'red honey' styles, is increasingly common on microlots. Some estate producers experiment with anaerobic and natural-process lots."
        ),
        "harvest": (
            "Harvest runs November through March. Fresh-crop Salvadoran lots reach Canadian warehouses April through July."
        ),
        "cupping_profile": (
            "Salvadoran Bourbon and Pacamara cup softly and sweetly: hazelnut, milk chocolate, sweet honey, red apple, gentle citrus, silky-creamy body. "
            "Pacamara lots scale up in intensity — tropical fruit, floral, stone fruit. Santa Ana lots are especially prized for their refined structure."
        ),
        "roasting_guidance": (
            "Salvadoran beans roast gently. Light-medium preserves the honey-floral sweetness for single-origin. Medium develops the hazelnut-chocolate body for espresso use."
        ),
        "why_canada": (
            "El Salvador is a smaller-volume origin for the Canadian market but offers exceptional refinement when available. Root 86 imports Salvadoran lots when seasonal quality and availability align."
        ),
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
  <div class="lp-footer-grid">
    <div class="lp-footer-col">
      <h4>Root 86 Coffee</h4>
      <p><a href="/">Home</a></p>
      <p><a href="/about.html">About</a></p>
      <p><a href="/contact.html">Contact</a></p>
      <p><a href="/roasters.html">Find a Roaster</a></p>
    </div>
    <div class="lp-footer-col">
      <h4>Catalogue</h4>
      <p><a href="/#finder">Find Coffee</a></p>
      <p><a href="/wholesale.html">Wholesale</a></p>
      <p><a href="/certifications.html">Certifications</a></p>
      <p><a href="/process.html">Our Process</a></p>
      <p><a href="/resources/">Resources</a></p>
    </div>
    <div class="lp-footer-col">
      <h4>Warehouses</h4>
      <p><a href="/green-coffee-canada.html">Canada</a></p>
      <p><a href="/green-coffee-vancouver.html">Vancouver, BC</a></p>
      <p><a href="/green-coffee-vancouver-island.html">Vancouver Island</a></p>
      <p><a href="/green-coffee-quebec.html">Québec / Lévis</a></p>
    </div>
    <div class="lp-footer-col lp-footer-origins">
      <h4>Origins</h4>
      <p>
        <a href="/origins/brazil.html">Brazil</a> &middot;
        <a href="/origins/colombia.html">Colombia</a> &middot;
        <a href="/origins/costa-rica.html">Costa Rica</a> &middot;
        <a href="/origins/ethiopia.html">Ethiopia</a> &middot;
        <a href="/origins/guatemala.html">Guatemala</a> &middot;
        <a href="/origins/honduras.html">Honduras</a> &middot;
        <a href="/origins/indonesia.html">Indonesia</a> &middot;
        <a href="/origins/kenya.html">Kenya</a> &middot;
        <a href="/origins/mexico.html">Mexico</a> &middot;
        <a href="/origins/nicaragua.html">Nicaragua</a> &middot;
        <a href="/origins/panama.html">Panama</a> &middot;
        <a href="/origins/papua-new-guinea.html">PNG</a> &middot;
        <a href="/origins/peru.html">Peru</a> &middot;
        <a href="/origins/rwanda.html">Rwanda</a> &middot;
        <a href="/origins/tanzania.html">Tanzania</a> &middot;
        <a href="/origins/uganda.html">Uganda</a>
      </p>
    </div>
  </div>
  <p class="lp-footer-tag">&copy; Root 86 Coffee &middot; Canadian Green Coffee Importer &middot; <a href="tel:18559080086">1-855-908-0086</a> &middot; <a href="mailto:root86coffee@gmail.com">root86coffee@gmail.com</a></p>
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
  .lp-footer { padding: 48px 24px 32px; color: var(--muted); font-size:.82rem; border-top: 1px solid rgba(0,0,0,0.08); background: #FAF8F6; }
  .lp-footer-grid { max-width: 1100px; margin: 0 auto; display: grid; grid-template-columns: repeat(4, 1fr); gap: 32px; }
  .lp-footer-col h4 { font-family: var(--font-serif); font-size: .95rem; color: var(--ink); margin: 0 0 12px; font-weight: 400; letter-spacing: .02em; }
  .lp-footer-col p { margin: 6px 0; line-height: 1.4; }
  .lp-footer a { color: var(--muted); text-decoration:none; }
  .lp-footer a:hover { color: var(--red); }
  .lp-footer-origins { grid-column: span 1; }
  .lp-footer-origins p { line-height: 1.9; }
  .lp-footer-tag { max-width: 1100px; margin: 32px auto 0; padding-top: 20px; border-top: 1px solid rgba(0,0,0,0.06); text-align:center; font-size:.76rem; }
  .lp-footer-tag a { margin: 0 6px; }
  @media (max-width: 720px) {
    .lp-footer-grid { grid-template-columns: repeat(2, 1fr); gap: 24px; }
    .lp-footer-origins { grid-column: span 2; }
  }
  .coffee-grid-sm { display:grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; margin-top: 24px; }
  .cg-card { padding: 18px; border: 1px solid rgba(0,0,0,0.08); background: var(--white); text-decoration:none !important; color: inherit; transition: border-color .2s, transform .15s; display:block; }
  .cg-card:hover { border-color: var(--red); transform: translateY(-2px); }
  .cg-origin { font-size:.65rem; letter-spacing:.2em; text-transform:uppercase; color: var(--red); margin-bottom: 6px; }
  .cg-name { font-family: var(--font-serif); font-size: 1.1rem; color: var(--ink); line-height:1.3; margin-bottom: 6px; }
  .cg-notes { font-size:.78rem; color: var(--muted); line-height:1.55; font-style: italic; }
  body { overflow-x:hidden; }
  * { cursor: auto !important; }
  a[href], button { cursor: pointer !important; }
  .lp-faq { max-width: 820px; margin-top: 8px; }
  .lp-faq-item { border-top: 1px solid rgba(0,0,0,0.1); padding: 14px 0; }
  .lp-faq-item:last-of-type { border-bottom: 1px solid rgba(0,0,0,0.1); }
  .lp-faq-item summary { font-family: var(--font-serif); font-size: 1.15rem; color: var(--ink); cursor: pointer !important; list-style: none; padding-right: 28px; position: relative; }
  .lp-faq-item summary::-webkit-details-marker { display: none; }
  .lp-faq-item summary::after { content: '+'; position: absolute; right: 4px; top: -2px; font-size: 1.4rem; color: var(--red); transition: transform .15s; }
  .lp-faq-item[open] summary::after { content: '−'; }
  .lp-faq-a { padding-top: 8px; color: var(--muted); line-height: 1.7; font-size: .96rem; }
  .lp-faq-a p { margin: 0 0 10px; }
  .lp-faq-a a { color: var(--red); text-decoration: underline; text-underline-offset: 3px; }
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
    notes_short = truncate_at_word(notes, 90)
    whs_str = ", ".join(whs) if whs else "Canada"
    meta_desc = truncate_at_word(
        f"{name} — {origin} green coffee from {region or origin}. {notes_short} Bag size {bag} lbs, stocked in {whs_str}.",
        158,
    )

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

    if available:
        if whs:
            status = "In stock at " + ", ".join(whs)
        else:
            status = "In stock"
    else:
        status = "Currently out of stock - contact us for similar lots"

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
{hreflang_from_url(url)}
  <meta property="og:type" content="product" />
  <meta property="og:site_name" content="Root 86 Coffee" />
  <meta property="og:title" content="{html_escape(name)} | Root 86 Coffee" />
  <meta property="og:description" content="{html_escape(meta_desc)}" />
  <meta property="og:url" content="{url}" />
  <meta name="twitter:card" content="summary_large_image" />
{og_image_tags(image, name + " green coffee")}
{FAVICONS}
{analytics_and_verification()}
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

# ── FAQ helpers (shared block renderer + JSON-LD FAQPage schema) ──
def build_faq_block(faqs, heading="Frequently asked questions"):
    """Return (visible_html, jsonld_schema) for a list of (question, answer) tuples."""
    if not faqs:
        return "", ""
    items_html = []
    for q, a in faqs:
        items_html.append(
            f'<details class="lp-faq-item"><summary>{html_escape(q)}</summary>'
            f'<div class="lp-faq-a">{a}</div></details>'
        )
    visible = (
        f'<section class="lp-section alt">\n'
        f'  <div class="lp-container">\n'
        f'    <h2>{html_escape(heading)}</h2>\n'
        f'    <div class="lp-faq">\n      {chr(10).join(items_html)}\n    </div>\n'
        f'  </div>\n</section>'
    )
    entities = [
        {
            "@type": "Question",
            "name": q,
            "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"<[^>]+>", "", a)}
        }
        for q, a in faqs
    ]
    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": entities,
    }
    jsonld = f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>'
    return visible, jsonld

# Canonical B2B FAQs used site-wide; regional pages extend these with local questions.
BASE_FAQS = [
    ("What is green coffee?",
     "<p>Green coffee is unroasted coffee — the dried seed of the coffee cherry after processing but before any heat is applied. "
     "Roasters source green coffee and apply heat themselves to develop the flavours in the final roasted product. "
     "Root 86 Coffee imports green coffee and supplies it to Canadian micro-roasters, cafes, and wholesale buyers.</p>"),
    ("Do you sell roasted coffee or only green?",
     "<p>Root 86 is a green coffee importer and broker — we sell unroasted beans only. If you're looking for roasted coffee, "
     "visit our <a href=\"/roasters.html\">Canadian roaster directory</a> to find an independent roaster that uses Root 86 green coffee.</p>"),
    ("Do you sell to home roasters?",
     "<p>Root 86 Coffee primarily serves commercial micro-roasters, cafes, and wholesale buyers. We stock specialty-grade green coffee in full-bag (132-152 lb) and half-bag (66 lb) quantities. "
     "Contact us to discuss whether our supply model fits your needs.</p>"),
    ("What bag sizes do you stock?",
     "<p>Our standard full bags range from 132 to 152 lbs depending on origin. We also stock half bags (66 lbs) for many origins, ideal for smaller micro-roasters building out origin variety without over-committing inventory.</p>"),
    ("Where do you ship from?",
     "<p>We stock all 50+ origins at three Canadian warehouses: "
     "<a href=\"/green-coffee-vancouver.html\">Vancouver, BC</a>; "
     "<a href=\"/green-coffee-vancouver-island.html\">Parksville, BC</a> (Vancouver Island); and "
     "<a href=\"/green-coffee-quebec.html\">Lévis, QC</a>. Your order ships from whichever warehouse is closest, minimizing freight cost and transit time.</p>"),
    ("Do you ship across Canada?",
     "<p>Yes — we ship to every province. Our three strategically-placed warehouses cover British Columbia, Alberta, the Prairies, Ontario, Quebec, and the Maritimes with domestic freight. No border crossings, no USD conversions, no customs delays.</p>"),
    ("Is your green coffee certified organic or Fair Trade?",
     "<p>We carry certified Organic, Fair Trade, Rainforest Alliance, and Women's Producer lots across many origins. Every certification is verifiable — request documentation for any lot. "
     "Browse the <a href=\"/#finder\">catalogue</a> and filter by certification to find matching lots.</p>"),
    ("How do I request a sample?",
     "<p>Contact us through our <a href=\"/contact.html\">contact page</a> or build a sample-request <a href=\"/#finder\">quote</a>. "
     "We ship samples from our Parksville, BC sample-courier address (1006 Herring Gull Way, Parksville, BC V9P 1R2) and respond to sample requests within the same business day.</p>"),
    ("How long does green coffee stay fresh?",
     "<p>Properly stored green coffee holds its specialty-grade cup quality for 9-12 months after arrival at port, and some origins (notably Brazil and Sumatra) retain quality even longer. "
     "Our Canadian warehouses are temperature and humidity controlled. Buy quantities that match your roasting cadence for best cup consistency.</p>"),
]

# ── Deep per-origin content renderer ──
def _origin_deep_copy(origin, copy, cards):
    """Render the long-form sections of an origin hub page.
    Each optional key in ORIGIN_COPY (regions, varieties, processing, harvest,
    cupping_profile, roasting_guidance, why_canada) renders as its own H3
    block so Google sees a structured, content-rich page.
    """
    def block(heading, body):
        if not body: return ""
        paras = [p.strip() for p in body.split("\n\n") if p.strip()]
        body_html = "\n    ".join(f"<p>{html_escape(p)}</p>" for p in paras)
        return f'    <h3>{heading}</h3>\n    {body_html}\n'

    sections = (
        block(f"Growing regions of {origin}",          copy.get("regions")) +
        block(f"Common {origin} coffee varieties",     copy.get("varieties")) +
        block(f"Processing methods",                    copy.get("processing")) +
        block(f"Harvest calendar &amp; freshness",      copy.get("harvest")) +
        block(f"What {origin} green coffee tastes like", copy.get("cupping_profile")) +
        block(f"Roasting guidance for {origin}",        copy.get("roasting_guidance")) +
        block(f"Why Canadian roasters source {origin} from Root 86", copy.get("why_canada"))
    )

    grid_html = (''.join(cards) if cards
                 else '<p>No lots currently visible. Contact us for availability.</p>')

    return f'''<section class="lp-section">
  <div class="lp-container">
    <h2>About our <em>{html_escape(origin)}</em> green coffee selection</h2>
    <p>{html_escape(copy["context"])}</p>
    {f"<h3>Flavour profile</h3><p>{html_escape(copy['flavour'])}</p>" if copy.get("flavour") else ""}
{sections}    <h3>Available {html_escape(origin)} coffees at Root 86</h3>
    <div class="coffee-grid-sm">{grid_html}</div>
  </div>
</section>'''

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
    # Word-aware meta description — never truncates mid-word.
    intro_short = truncate_at_word(copy["intro"], 95)
    meta_desc = truncate_at_word(
        f"{intro_short} Stocked for Canadian roasters at our Vancouver, Parksville, and Lévis warehouses.",
        158,
    )

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

    regions_first_para = (copy.get("regions") or "").split("\n\n")[0].strip()
    if not regions_first_para:
        regions_first_para = f"{origin} coffee grows in the country's highland regions."
    origin_faqs = [
        (f"Where does {origin} green coffee come from?",
         f"<p>{html_escape(regions_first_para)}</p>"),
        (f"What does {origin} green coffee taste like?",
         f"<p>{html_escape(copy.get('flavour', 'See our cupping notes for current lots.'))}</p>"),
        (f"Is {origin} green coffee available year-round in Canada?",
         f"<p>Root 86 Coffee stocks {html_escape(origin)} lots at our Vancouver, Parksville, and Lévis warehouses. "
         f"Availability rotates with the {html_escape(origin)} harvest cycle — <a href=\"/#finder\">browse the catalogue</a> for current in-stock lots or <a href=\"/contact.html\">contact us</a> about fresh-crop timing.</p>"),
    ] + BASE_FAQS[:4]
    faq_html, faq_schema = build_faq_block(origin_faqs,
        heading=f"{origin} green coffee — frequently asked questions")

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html_escape(title)}</title>
  <meta name="description" content="{html_escape(meta_desc)}" />
  <meta name="robots" content="index, follow, max-image-preview:large" />
  <link rel="canonical" href="{url}" />
{hreflang_from_url(url)}
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="Root 86 Coffee" />
  <meta property="og:title" content="{html_escape(title)}" />
  <meta property="og:description" content="{html_escape(meta_desc)}" />
  <meta property="og:url" content="{url}" />
{FAVICONS}
{DEFAULT_OG_IMAGE}
{analytics_and_verification()}
  <link rel="stylesheet" href="/css/styles.css" />
  <script type="application/ld+json">{breadcrumb}</script>
  {faq_schema}
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
{_origin_deep_copy(origin, copy, cards)}
{faq_html}
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
CANADA_FAQS = [
    ("Which Canadian provinces does Root 86 Coffee serve?",
     "<p>Every province. We have three warehouses — Vancouver BC, Parksville BC, and Lévis QC — that together cover the Lower Mainland, BC Interior, Vancouver Island, Alberta, the Prairies, Ontario, Québec, the Maritimes, and Newfoundland. Freight is purely domestic.</p>"),
    ("Do you price in CAD?",
     "<p>Yes — all pricing is quoted and invoiced in Canadian dollars. No exchange-rate surprises, no USD-to-CAD conversion math when you're working out cost of goods.</p>"),
    ("How does a Canadian roaster set up an account with Root 86?",
     "<p><a href=\"/contact.html\">Contact us</a> with your business information and roasting volume. We'll walk you through the first-order process, sample program, and payment terms. Most Canadian micro-roasters are approved within one business day.</p>"),
    ("Do you offer delivery to Alberta, Saskatchewan, and Manitoba?",
     "<p>Yes — Prairie deliveries ship from our Vancouver warehouse, typically reaching Calgary, Edmonton, Saskatoon, Regina, and Winnipeg within 3-5 business days via domestic freight.</p>"),
    ("Can I pick up green coffee in person at a warehouse?",
     "<p>Pickup at our Parksville, BC address is available by appointment. Vancouver and Lévis pickups can be arranged — <a href=\"/contact.html\">contact us</a> to coordinate.</p>"),
] + BASE_FAQS[:4]

def build_canada_page():
    url = f"{SITE_URL}/green-coffee-canada.html"
    faq_html, faq_schema = build_faq_block(CANADA_FAQS,
        heading="Canadian green coffee — frequently asked questions")
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Green Coffee Canada | Nationwide Importer | Root 86 Coffee</title>
  <meta name="description" content="Green coffee importer serving roasters across Canada. Root 86 Coffee stocks 50+ origins in Vancouver BC, Parksville BC, and Lévis QC with fast domestic delivery. Organic, Fair Trade, and specialty lots." />
  <meta name="robots" content="index, follow, max-image-preview:large" />
  <link rel="canonical" href="{url}" />
{hreflang_from_url(url)}
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="Root 86 Coffee" />
  <meta property="og:title" content="Green Coffee Canada | Root 86 Coffee" />
  <meta property="og:description" content="Canada's trusted green coffee importer. 50+ origins, 3 warehouses, nationwide delivery." />
  <meta property="og:url" content="{url}" />
{FAVICONS}
{DEFAULT_OG_IMAGE}
{analytics_and_verification()}
  <link rel="stylesheet" href="/css/styles.css" />
  {faq_schema}
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
{faq_html}
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

QUEBEC_FAQS = [
    ("Où est situé votre entrepôt au Québec?",
     "<p>Notre entrepôt québécois est situé à Lévis, QC (près de Québec). Il dessert les torréfacteurs de Montréal, Québec, Sherbrooke, Trois-Rivières, Saguenay, Gatineau, et partout au Québec.</p>"),
    ("Do you serve coffee roasters in Montréal?",
     "<p>Yes. Our Lévis QC warehouse ships to Montréal, the Outaouais, Québec City, the Eastern Townships, Saguenay, and every major Québec roasting region with domestic freight — typically 1-3 business days to Montréal.</p>"),
    ("Do you ship from Lévis to Ontario and the Maritimes?",
     "<p>Yes — the Lévis warehouse serves Eastern Ontario (Ottawa, Kingston, Toronto), and all of New Brunswick, Nova Scotia, PEI, and Newfoundland. Freight costs are typically the lowest from Lévis to these destinations.</p>"),
    ("Quelles certifications offrez-vous?",
     "<p>Nous offrons des lots certifiés biologique, Commerce équitable (Fair Trade), Rainforest Alliance, et des lots « Women's Producer » — tous stockés à Lévis et traçables jusqu'au producteur.</p>"),
    ("Is bilingual support available?",
     "<p>Yes. We work regularly with Québec roasters and correspond in English or French as you prefer. <a href=\"/contact.html\">Contactez-nous</a> in either language.</p>"),
] + BASE_FAQS[:3]

def build_quebec_page():
    url = f"{SITE_URL}/green-coffee-quebec.html"
    faq_html, faq_schema = build_faq_block(QUEBEC_FAQS,
        heading="Green coffee in Québec — frequently asked questions")
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Green Coffee Québec | Café Vert Lévis QC | Root 86 Coffee</title>
  <meta name="description" content="Green coffee (café vert) importer serving Québec roasters from our Lévis QC warehouse. 50+ origins, organic, Fair Trade, and specialty-grade lots. Fast delivery across Québec, Ontario, and Atlantic Canada." />
  <meta name="robots" content="index, follow" />
  <link rel="canonical" href="{url}" />
{hreflang_from_url(url)}
  <meta property="og:type" content="website" />
  <meta property="og:title" content="Green Coffee Québec | Root 86 Coffee" />
  <meta property="og:description" content="Green coffee importer serving Québec from Lévis warehouse. 50+ origins for Québec roasters." />
  <meta property="og:url" content="{url}" />
{FAVICONS}
{DEFAULT_OG_IMAGE}
{analytics_and_verification()}
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
  {faq_schema}
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
{faq_html}
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

ISLAND_FAQS = [
    ("Do you deliver green coffee on Vancouver Island?",
     "<p>Yes — our Parksville warehouse is the only green coffee supplier on Vancouver Island carrying 50+ origins locally. Island roasters get same-week delivery without ferry freight, mainland minimums, or BC-Ferries scheduling delays.</p>"),
    ("What are your delivery areas on the Island?",
     "<p>We deliver from Parksville to Nanaimo, Qualicum Beach, Port Alberni, Courtenay, Comox, Campbell River, Duncan, the Cowichan Valley, Victoria, Sidney, Sooke, Tofino, Ucluelet, and the Gulf Islands. For North Island and remote-coast destinations, we can arrange freight via BC Ferries or local courier.</p>"),
    ("Can I pick up green coffee at the Parksville warehouse?",
     "<p>Yes, pickup is available by appointment at 1006 Herring Gull Way, Parksville, BC V9P 1R2. This is also our sample-shipping courier address. <a href=\"/contact.html\">Contact us</a> to schedule.</p>"),
    ("Do you offer small lots for Vancouver Island micro-roasters?",
     "<p>Yes — we stock half bags (66 lbs) for many origins specifically to support Island micro-roasters building out origin variety without over-committing. We also handle sample ships for Island roasters trialling new origins.</p>"),
    ("Which Island roasters use Root 86 green coffee?",
     "<p>Root 86 supplies dozens of Vancouver Island specialty roasters — from Victoria to Tofino. See our <a href=\"/roasters.html\">roaster directory</a> for a list of Island cafes and roasteries that feature coffee we've imported.</p>"),
] + BASE_FAQS[:3]

def build_island_page():
    url = f"{SITE_URL}/green-coffee-vancouver-island.html"
    faq_html, faq_schema = build_faq_block(ISLAND_FAQS,
        heading="Vancouver Island green coffee — frequently asked questions")
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Green Coffee Vancouver Island | Parksville BC | Root 86 Coffee</title>
  <meta name="description" content="Green coffee for Vancouver Island micro-roasters. Root 86 Coffee's Parksville BC warehouse stocks 50+ origins locally for Nanaimo, Victoria, Duncan, Courtenay, Tofino, and all Vancouver Island roasters." />
  <meta name="robots" content="index, follow" />
  <link rel="canonical" href="{url}" />
{hreflang_from_url(url)}
  <meta property="og:type" content="website" />
  <meta property="og:title" content="Green Coffee Vancouver Island | Root 86 Coffee" />
  <meta property="og:description" content="Vancouver Island green coffee importer. Parksville warehouse serving all Island roasters." />
  <meta property="og:url" content="{url}" />
{FAVICONS}
{DEFAULT_OG_IMAGE}
{analytics_and_verification()}
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
  {faq_schema}
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
{faq_html}
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

# ── _redirects emitter ─────────────────────────────────────────────
# Old Wix URL structure (from root86coffee.com sitemap) → new structure.
# Hand-curated so that every indexed Wix URL has a deterministic 301 target.
# Last audited: see Wix sitemap at https://www.root86coffee.com/sitemap.xml
WIX_STATIC_REDIRECTS = {
    "/aboutr86coffee":             "/about.html",
    "/contact-root86coffee":       "/contact.html",
    "/quote-builder":              "/contact.html",
    "/r86-green-coffees":          "/#finder",
    "/roasters-for-sale":          "/roasters.html",
    "/jan-2026-new-year-update":   "/",
}

# Maps each old Wix coffee slug (the part after /r86coffees/) to either
# a new /coffees/<slug>.html slug OR an origin hub fallback.
# Keys use the exact URL-encoded form Google has indexed.
# Values starting with "origin:" redirect to /origins/<slug>.html.
WIX_COFFEE_REDIRECTS = {
    "mexico-water-process-decaf-(mwp)-organic":                        "mexico-water-process-decaf-mwp-organic",
    "colombia-huila-organic":                                          "colombia-huila-organique",
    "honduras-copan-shg-tierra-lenca---organic":                       "honduras-lempira-shg-tierra-lenca-organic",
    "costa-rica-west-central-blend":                                   "costa-rica-west-central-valley-fancy-blend",
    "brazil-alta-mogiana":                                             "brazil-alta-mogiana-17-18",
    "panama-boquete-finca-la-santa-catuai-lot":                        "panama-boquete-finca-la-santa-catuai-lot",
    "mexico-chiapas-grapos-shg-specialty-small-farmer-organic":        "mexico-chiapas-angel-diaz-shg-organic",
    "costa-rica-tarrazu-shb":                                          "costa-rica-tarrazu-shb",
    "brazil-vale-de-grama-specialty-prep-mogiana":                     "brazil-vale-da-grama-mogiana-specialty-prep",
    "honduras-shg-copan-organic":                                      "honduras-shg-copan-organic",
    "ethiopia-sidamo-natural-gr-1-bombe-ayla":                         "ethiopia-sidama-natural-gr-3-bombe",
    "costa-rica-west-valley-v%26g-estate-white-honey":                 "origin:costa-rica",
    "mexico-chiapas-hg":                                               "mexico-chiapas-hg",
    "colombia-quindio-genova-excelso-ep":                              "colombia-genova-quindio-excelso-ep",
    "costa-rica-west-valley-v%26g-estate-natural-marsellesa":          "costa-rica-hacienda-san-ignacio-marsellesa-hybrid",
    "uganda%2C-mt.-elgon%2C-aa-rfa":                                   "uganda-mt-elgon-aa-rfa",
    "guatemala-huehuetenango-shb-ep":                                  "guatemala-huehuetenango-shb-ep-gp",
    "costa-rica-san-ignacio-mircolot-natural":                         "costa-rica-hacienda-san-ignacio-marsellesa-hybrid",
    "ethiopia-sidama-riripa-g2-organic":                               "origin:ethiopia",
    "tanzania-pb-northern-kilimanjaro":                                "tanzania-pb-plus-northern-kilimanjaro",
    "mexico-oaxaca--shg---specialty-small-farmer-organic":             "mexico-oaxaca-shg-organic",
    "costa-rica-west-valley-estate-natural-catigua":                   "origin:costa-rica",
    "guatemala-sanmarcos-shb-ep":                                      "origin:guatemala",
    "swp-peru-decaf-organic":                                          "swp-peru-decaf-organic",
    "guatemala-santarosa-shb-ep":                                      "guatemala-santa-rosa-estate-shb-ep-gp",
    "kenya-ab-plus-sondhi-":                                           "kenya-ab-plus-sondhi",
    "swp-brazil-decaf-":                                               "swp-brazil-decaf",
    "colombia-cundinamarca-excelso-ep-":                               "colombia-cundinamarca-excelso-rfa-gp-ep",
    "tanzania-pb-plus-southern":                                       "tanzania-pb-plus-southern-estate",
    "rwanda--nyampinga-organic.-womens-coop":                          "rwanda-nyampinga-organic-womens-coop",
    "swp-premium-espresso-blend-decaf":                                "swp-premium-espresso-blend-decaf",
    "ethiopia-gedeo-zone-yirgacheffe-konga-washed":                    "ethiopia-gedeo-zone-yirgacheffe-konga-washed",
    "nicaragua-jinotega-ft-organic":                                   "nicaragua-jinotega-ft-organic",
    "ethiopia-gedeo-yirgacheffe-koke-g2-natural":                      "ethiopia-gedeo-yirgacheffe-koke-g2-natural",
    "colombia-tolima-planadas-organic%2C-womens-coop":                 "colombia-tolima-planadas-organic-womens-coop",
    "colombia-narino-ecoterra-women&apos;s-lot-":                      "colombia-narino-ecoterra-women-s-lot",
    "colombia-antioquia-excelso-ep":                                   "origin:colombia",
    "costa-rica-west-valley-vg-estate-natural":                        "origin:costa-rica",
    "colombia-huila-terra-rosa-women&apos;s-lot":                      "colombia-huila-terra-rosa-women-s-lot",
    "ethiopia-guji-shakiso---kayon-mountain-estate-ft-organic":        "origin:ethiopia",
    "ethiopia-gedeo-yirgacheffe-gersi-washedg2":                       "ethiopia-gedeo-yirgacheffe-gersi-gr2-washed",
    "indonesia-sumatra-mandheling-g1-organic":                         "indonesia-sumatra-mandheling-g1",
    "guatemala-lake-atitlan-organic-":                                 "guatemala-lake-atitlan-organic",
    "indonesia-flores-rfa-organic":                                    "origin:indonesia",
    "brazil-pocos-de-caldas":                                          "brazil-pocos-de-caldas-sul-de-minas-gerais",
    "el-salvador-santa-ana%2C-monte-verde":                            "redirect:/#finder",
    "indonesia-sumatra-mandheling-g1%2C--women&apos;s-producer-organic": "indonesia-sumatra-mandheling-g1-women-s-producer-organic",
    "papua-new-guinea-psc-simbu":                                      "papua-new-guinea-psc-simbu",
    "peru-el-gran-mirador%2C-women-production%2C-organic":             "peru-el-gran-mirador-organic",
    "swp-honduras-decaf-organic":                                      "origin:honduras",
}

def build_redirects(coffees):
    """Emit the Cloudflare Pages _redirects file.

    Format per line:  /source  /destination  STATUS
    Cloudflare Pages matches paths literally (before URL decoding), so
    percent-encoded keys like %26 must be preserved exactly as Google indexed
    them. Specific rules are ordered above the /r86coffees/* catch-all.
    """
    valid_slugs = {slugify(c["name"]) for c in coffees if not c.get("hidden")}
    lines = [
        "# Root 86 Coffee — Cloudflare Pages redirects",
        "# Auto-generated by _tools/generate_seo.py — DO NOT EDIT BY HAND.",
        "# Preserves SEO equity from the legacy Wix site at root86coffee.com.",
        "",
        "# ── Static Wix pages ─────────────────────────────────────────",
    ]
    for src, dst in WIX_STATIC_REDIRECTS.items():
        lines.append(f"{src}  {dst}  301")

    lines += ["", "# ── Wix coffee detail pages ──────────────────────────────────"]
    missing = []
    for old, new in WIX_COFFEE_REDIRECTS.items():
        if new.startswith("origin:"):
            target = f"/origins/{new.split(':',1)[1]}.html"
        elif new.startswith("redirect:"):
            target = new.split(":",1)[1]
        else:
            target = f"/coffees/{new}.html"
            if new not in valid_slugs:
                missing.append((old, new))
        lines.append(f"/r86coffees/{old}  {target}  301")

    lines += [
        "",
        "# ── Catch-all for any Wix coffee URL not individually mapped ─",
        "/r86coffees/*  /#finder  301",
        "",
        "# ── Trailing-slash normalization ─────────────────────────────",
        "# Cloudflare Pages already normalizes /foo/ → /foo for static files;",
        "# apex ↔ www is handled at the DNS/custom-domain layer, not here.",
        "",
    ]

    if missing:
        print("WARNING — _redirects targets that don't match a current coffee slug:",
              file=sys.stderr)
        for old, new in missing:
            print(f"  /r86coffees/{old}  ->  /coffees/{new}.html (slug not found)",
                  file=sys.stderr)

    return "\n".join(lines) + "\n"

# ── Commercial-intent + informational landing pages ──

def _basic_lp_head(title, meta_desc, url, extra_schema=""):
    """Shared <head> for the simpler generator-emitted landing pages."""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html_escape(title)}</title>
  <meta name="description" content="{html_escape(meta_desc)}" />
  <meta name="robots" content="index, follow, max-image-preview:large" />
  <link rel="canonical" href="{url}" />
{hreflang_from_url(url)}
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="Root 86 Coffee" />
  <meta property="og:title" content="{html_escape(title)}" />
  <meta property="og:description" content="{html_escape(meta_desc)}" />
  <meta property="og:url" content="{url}" />
{FAVICONS}
{DEFAULT_OG_IMAGE}
{analytics_and_verification()}
  <link rel="stylesheet" href="/css/styles.css" />
  {extra_schema}
  {LP_STYLE}
</head>'''

PROCESS_FAQS = [
    ("How does Root 86 Coffee source its green coffee?",
     "<p>We work with a mix of direct-trade producer relationships, long-term importer partnerships, and cooperative structures at origin. Every lot is cupped and Q-graded before we commit to a container. Traceability documentation is available for every coffee we import.</p>"),
    ("What is Q-grading?",
     "<p>Q-grading is the Specialty Coffee Association's standardized cupping protocol. A certified Q-grader scores coffees on 10 attributes including aroma, flavour, aftertaste, acidity, body, balance, and defects. Only coffees scoring 80+ on the 100-point scale qualify as 'specialty'. We only import specialty-grade green coffee.</p>"),
    ("How long does a container take to reach Canada?",
     "<p>Transit times vary by origin: Central American containers typically take 4-6 weeks ocean freight plus 1-2 weeks customs/trucking inland, while East African and Indonesian origins run 6-9 weeks port-to-warehouse. We plan arrivals to land fresh-crop inventory in Canadian warehouses during peak roasting demand.</p>"),
    ("Can I request a pre-import sample before a container lands?",
     "<p>Yes. For committed volume buyers, we can ship origin samples via air courier before a container leaves port. This lets you approve a lot against the exact pre-shipment sample that represents your order.</p>"),
] + BASE_FAQS[:3]

def build_process_page():
    url = f"{SITE_URL}/process.html"
    title = "How Root 86 Imports Green Coffee | Canadian Green Coffee Importer"
    meta_desc = "How we import green coffee to Canada: producer sourcing, Q-grading, container consolidation, and Canadian warehousing. Specialty-grade traceability from origin to roaster."
    faq_html, faq_schema = build_faq_block(PROCESS_FAQS,
        heading="How green coffee importing works — FAQ")
    breadcrumb = f'''<script type="application/ld+json">{{
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      {{ "@type": "ListItem", "position": 1, "name": "Home", "item": "{SITE_URL}/" }},
      {{ "@type": "ListItem", "position": 2, "name": "Our Process", "item": "{url}" }}
    ]
  }}</script>'''
    return _basic_lp_head(title, meta_desc, url, breadcrumb + faq_schema) + f'''
<body>
{NAV_HTML}
<nav class="lp-breadcrumb"><a href="/">Home</a> &rsaquo; <span>Our Process</span></nav>
<section class="lp-hero">
  <div class="lp-container">
    <span class="lp-eyebrow">How We Import</span>
    <h1>From <em>origin</em> to your roaster</h1>
    <p class="lead">Root 86 Coffee imports specialty-grade green coffee to Canada through a deliberate, four-stage process: sourcing, sampling, shipping, and warehousing. Every stage exists to make sure the bag a Canadian roaster opens is the bag we cupped at origin.</p>
    <div class="cta-row">
      <a href="/#finder" class="lp-cta lp-cta-primary">Browse Catalogue &rarr;</a>
      <a href="/contact.html" class="lp-cta lp-cta-ghost">Ask About a Lot</a>
    </div>
  </div>
</section>
<section class="lp-section">
  <div class="lp-container">
    <h2>Stage 1 — <em>Sourcing</em> at origin</h2>
    <p>We work with a mix of direct producer relationships, long-term importer partnerships, and certified cooperatives. For every origin in our catalogue, we have specific producer or cooperative contacts who know the harvest, understand our quality bar, and ship us pre-shipment samples every season.</p>
    <p>Cooperative-origin lots (Mexico, Peru, Nicaragua, Honduras, Rwanda, Indonesia) give us access to certified-organic and Fair Trade supply with real producer traceability. Direct-trade and single-estate lots (Panama Boquete, Costa Rican micromills, Huehuetenango microlots) let us source competition-grade coffees when a Canadian roaster wants something distinctive.</p>
    <h2>Stage 2 — <em>Sampling and Q-grading</em></h2>
    <p>Every shortlisted lot arrives at our Canadian cupping table before we commit to a container. Q-certified cupping evaluates each coffee on 10 attributes — aroma, flavour, aftertaste, acidity, body, balance, uniformity, sweetness, clean cup, and overall — against the SCA's 100-point specialty standard. Only coffees scoring 80+ earn specialty-grade classification and a place in our offer list.</p>
    <p>We cup double-blind against peer lots from the same origin and processing, so our specialty-grade bar isn't just a score — it's comparative quality. Canadian roasters receiving our samples get scorecards with every lot.</p>
    <h2>Stage 3 — <em>Container consolidation</em> &amp; ocean freight</h2>
    <p>Containers are consolidated at origin or at port, with documentation covering each individual lot inside. Transit times range from 4-6 weeks (Central and South America) to 6-9 weeks (East Africa and Indonesia). We stage orders so fresh-crop arrivals land in Canadian warehouses in time to meet seasonal roasting demand.</p>
    <p>Imports clear Canadian customs, get de-vanned at port, and are trucked to our three warehouses depending on destination demand. Food-safety and phytosanitary documentation accompanies every lot.</p>
    <h2>Stage 4 — <em>Canadian warehousing</em></h2>
    <p>All inventory is held at three climate-controlled Canadian warehouses: <a href="/green-coffee-vancouver.html">Vancouver, BC</a> for Western Canada, <a href="/green-coffee-vancouver-island.html">Parksville, BC</a> for Vancouver Island and the Gulf Islands, and <a href="/green-coffee-quebec.html">Lévis, QC</a> for Québec, Ontario, and the Maritimes. Every in-stock lot is available from whichever warehouse is closest to your roaster.</p>
    <p>Green coffee holds specialty-grade cup quality for 9-12 months in properly controlled storage. Our warehouse conditions — temperature, humidity, rotation — are tuned to preserve fresh-crop character through a full roasting calendar.</p>
    <h3>Quality-control and traceability</h3>
    <p>Every lot in stock at a Root 86 warehouse has: origin-certificate documentation, cupping scorecard, processing information, farm or cooperative traceability, and certification documentation (where applicable). Ask for any of it — we send it with your first sample.</p>
  </div>
</section>
{faq_html}
<section class="lp-contact-band">
  <div class="lp-container">
    <h2>Source coffee from our <em style="color:var(--red);">import process</em></h2>
    <p>Browse what we currently have in stock, or contact us about a specific origin, processing style, or certification.</p>
    <div style="display:flex; gap:12px; justify-content:center; flex-wrap:wrap;">
      <a href="/#finder" class="lp-cta lp-cta-primary">Browse Catalogue</a>
      <a href="/contact.html" class="lp-cta lp-cta-ghost">Contact Us</a>
    </div>
  </div>
</section>
{FOOTER_HTML}
</body>
</html>'''


CERTIFICATIONS_FAQS = [
    ("Is your organic certification verifiable?",
     "<p>Yes. Every certified organic lot comes with documentation traceable to the producer cooperative and the certifying body. Request the certificate for any lot before you commit to a purchase.</p>"),
    ("What does Fair Trade certification mean for green coffee?",
     "<p>Fair Trade certification (FLO) requires a minimum farmgate price, a premium that funds community projects, and cooperative democratic governance. Our Fair Trade lots come from certified smallholder cooperatives in Nicaragua, Colombia, Ethiopia, Peru, and elsewhere.</p>"),
    ("What is Rainforest Alliance certification?",
     "<p>Rainforest Alliance (RFA) certification focuses on environmental stewardship — biodiversity, forest conservation, soil health — alongside fair labour practices. Our RFA lots include Uganda Mt. Elgon AA and selected Indonesian and Colombian origins.</p>"),
    ("What are Women's Producer lots?",
     "<p>Women's Producer certification identifies coffee lots produced by women-led farms, producer groups, or cooperatives. Purchases of these lots directly support women coffee producers at origin. Our Women's Producer lineup includes Rwanda Nyampinga, Colombia Terra Rosa and EcoTerra, Colombia Tolima Planadas, and Sumatra Mandheling Women's Producer Organic.</p>"),
    ("Can I filter the catalogue by certification?",
     "<p>Yes — the <a href=\"/#finder\">catalogue finder</a> includes certification filters. Select Organic, Fair Trade, Rainforest Alliance, or Women's Producer to see only matching in-stock lots.</p>"),
] + BASE_FAQS[:2]

def build_certifications_page():
    url = f"{SITE_URL}/certifications.html"
    title = "Certified Green Coffee — Organic, Fair Trade, RFA | Root 86 Coffee"
    meta_desc = "Certified organic, Fair Trade, Rainforest Alliance, and Women's Producer green coffee for Canadian roasters. Traceable to the producer cooperative. Stocked in Vancouver, Parksville, and Lévis."
    faq_html, faq_schema = build_faq_block(CERTIFICATIONS_FAQS,
        heading="Certified green coffee — FAQ")
    breadcrumb = f'''<script type="application/ld+json">{{
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      {{ "@type": "ListItem", "position": 1, "name": "Home", "item": "{SITE_URL}/" }},
      {{ "@type": "ListItem", "position": 2, "name": "Certifications", "item": "{url}" }}
    ]
  }}</script>'''
    return _basic_lp_head(title, meta_desc, url, breadcrumb + faq_schema) + f'''
<body>
{NAV_HTML}
<nav class="lp-breadcrumb"><a href="/">Home</a> &rsaquo; <span>Certifications</span></nav>
<section class="lp-hero">
  <div class="lp-container">
    <span class="lp-eyebrow">Certified Green Coffee</span>
    <h1>Certified <em>green coffee</em> for Canadian roasters</h1>
    <p class="lead">Organic, Fair Trade, Rainforest Alliance, and Women's Producer — every certification we carry is documented, traceable to the producer cooperative, and available at all three Canadian warehouses.</p>
    <div class="cta-row">
      <a href="/#finder" class="lp-cta lp-cta-primary">Filter Catalogue by Certification &rarr;</a>
      <a href="/contact.html" class="lp-cta lp-cta-ghost">Request Documentation</a>
    </div>
  </div>
</section>
<section class="lp-section">
  <div class="lp-container">
    <h2>Certified <em>Organic</em></h2>
    <p>USDA Organic / Canada Organic Regime certification means no synthetic pesticides, no synthetic fertilizers, and a verifiable organic management system from the farm to the export container. Root 86 stocks certified organic lots from <a href="/origins/mexico.html">Mexico</a>, <a href="/origins/peru.html">Peru</a>, <a href="/origins/ethiopia.html">Ethiopia</a>, <a href="/origins/colombia.html">Colombia</a>, <a href="/origins/honduras.html">Honduras</a>, <a href="/origins/guatemala.html">Guatemala</a>, <a href="/origins/nicaragua.html">Nicaragua</a>, <a href="/origins/rwanda.html">Rwanda</a>, and <a href="/origins/indonesia.html">Indonesia</a>.</p>
    <h2>Fair Trade (FLO)</h2>
    <p>Fair Trade certification requires a minimum floor price paid to producers, a social premium paid to the cooperative, and democratic cooperative governance. Our Fair Trade lots reliably come from <a href="/origins/nicaragua.html">Nicaragua</a> (Jinotega cooperatives), <a href="/origins/ethiopia.html">Ethiopia</a> (Guji cooperatives), and <a href="/origins/colombia.html">Colombia</a> (Huila and Nariño cooperatives). Fair Trade is a cooperative-producer model — you're buying coffee through a cooperative, not a private estate.</p>
    <h2>Rainforest Alliance (RFA)</h2>
    <p>Rainforest Alliance certification emphasizes biodiversity, forest conservation, soil health, and fair labour practices. Our RFA lots include <a href="/origins/uganda.html">Uganda Mt. Elgon AA</a>, <a href="/origins/indonesia.html">Indonesia Flores Organic RFA</a>, and <a href="/origins/colombia.html">Colombia Cundinamarca Excelso RFA</a>. RFA is popular with Canadian roasters whose brand story emphasizes environmental stewardship.</p>
    <h2>Women's Producer lots</h2>
    <p>Women's Producer designation identifies lots produced by women-led farms or women's sub-cooperatives within a larger cooperative. Purchases directly fund the women producer members. Our Women's Producer lineup includes <a href="/coffees/rwanda-nyampinga-organic-womens-coop.html">Rwanda Nyampinga</a>, <a href="/coffees/colombia-huila-terra-rosa-women-s-lot.html">Colombia Huila Terra Rosa</a>, <a href="/coffees/colombia-narino-ecoterra-women-s-lot.html">Colombia Nariño EcoTerra</a>, <a href="/coffees/colombia-tolima-planadas-organic-womens-coop.html">Colombia Tolima Planadas Organic Women's Coop</a>, and <a href="/coffees/indonesia-sumatra-mandheling-g1-women-s-producer-organic.html">Sumatra Mandheling Women's Producer Organic</a>.</p>
    <h2>Swiss Water &amp; Mountain Water Process decaf</h2>
    <p>Chemical-free decaffeination is an important certification-adjacent category for Canadian specialty roasters. We carry <a href="/coffees/swp-premium-espresso-blend-decaf.html">Swiss Water Process Espresso Blend Decaf</a>, <a href="/coffees/swp-peru-decaf-organic.html">SWP Peru Decaf Organic</a>, <a href="/coffees/swp-brazil-decaf.html">SWP Brazil Decaf</a>, and <a href="/coffees/mexico-water-process-decaf-mwp-organic.html">Mexican Mountain Water Process Decaf Organic</a>. Neither SWP nor MWP uses solvents — both rely on water-only extraction processes.</p>
  </div>
</section>
{faq_html}
<section class="lp-contact-band">
  <div class="lp-container">
    <h2>Build your <em style="color:var(--red);">certified</em> coffee program</h2>
    <p>Request certification documentation for any in-stock lot. We send the certificate with your sample — always.</p>
    <div style="display:flex; gap:12px; justify-content:center; flex-wrap:wrap;">
      <a href="/#finder" class="lp-cta lp-cta-primary">Browse Certified Lots</a>
      <a href="/contact.html" class="lp-cta lp-cta-ghost">Contact Us</a>
    </div>
  </div>
</section>
{FOOTER_HTML}
</body>
</html>'''


WHOLESALE_FAQS = [
    ("What is Root 86's minimum order?",
     "<p>Our minimum order is one half-bag (66 lbs) for most origins. For specific microlots and estate selections, the MOQ is the full single-bag (typically 132-152 lbs depending on origin). Contact us for exact MOQ on any specific coffee.</p>"),
    ("What are your wholesale payment terms?",
     "<p>New accounts typically pay by credit card or EFT on first order. Established wholesale accounts can be offered Net 15 or Net 30 terms after a credit review. Québec and Ontario roasters can be invoiced directly from our Lévis warehouse.</p>"),
    ("Do you offer volume discounts?",
     "<p>Yes — volume pricing is available for ongoing wholesale accounts committing to monthly or quarterly contract volumes. Contact us with your projected annual volume for a specific quote.</p>"),
    ("Can I lock in a price on a specific lot?",
     "<p>For committed volume buyers, we can reserve a specific number of bags from an in-stock lot at a fixed price for 30-60 days. This is most relevant for coffees you intend to feature on a signature blend or single-origin menu position.</p>"),
    ("Do you handle private-label or white-label bagging?",
     "<p>Root 86 imports green coffee only — roasting, bagging, and branding happen at your roastery. We can refer you to Canadian co-packers if white-label roasted coffee is what you're after.</p>"),
] + BASE_FAQS[:3]

def build_wholesale_page():
    url = f"{SITE_URL}/wholesale.html"
    title = "Buy Green Coffee Wholesale in Canada | Root 86 Coffee Importer"
    meta_desc = "Buy green coffee wholesale in Canada. Root 86 supplies micro-roasters, cafes, and wholesale accounts with 50+ origins in CAD, shipping from three Canadian warehouses. Volume pricing available."
    faq_html, faq_schema = build_faq_block(WHOLESALE_FAQS,
        heading="Wholesale green coffee in Canada — FAQ")
    breadcrumb = f'''<script type="application/ld+json">{{
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      {{ "@type": "ListItem", "position": 1, "name": "Home", "item": "{SITE_URL}/" }},
      {{ "@type": "ListItem", "position": 2, "name": "Wholesale", "item": "{url}" }}
    ]
  }}</script>'''
    return _basic_lp_head(title, meta_desc, url, breadcrumb + faq_schema) + f'''
<body>
{NAV_HTML}
<nav class="lp-breadcrumb"><a href="/">Home</a> &rsaquo; <span>Wholesale</span></nav>
<section class="lp-hero">
  <div class="lp-container">
    <span class="lp-eyebrow">Wholesale Green Coffee Canada</span>
    <h1>Buy <em>green coffee wholesale</em> in Canada</h1>
    <p class="lead">Root 86 Coffee supplies wholesale green coffee to Canadian micro-roasters, cafes, and commercial buyers. 50+ origins in stock at three Canadian warehouses, invoiced in CAD, shipped on domestic freight.</p>
    <div class="cta-row">
      <a href="/contact.html" class="lp-cta lp-cta-primary">Open a Wholesale Account &rarr;</a>
      <a href="/#finder" class="lp-cta lp-cta-ghost">Browse Catalogue</a>
    </div>
  </div>
</section>
<section class="lp-section">
  <div class="lp-container">
    <h2>Wholesale green coffee, <em>Canadian-stocked</em></h2>
    <p>Every wholesale order ships from one of our three climate-controlled Canadian warehouses: <a href="/green-coffee-vancouver.html">Vancouver, BC</a>, <a href="/green-coffee-vancouver-island.html">Parksville, BC</a>, or <a href="/green-coffee-quebec.html">Lévis, QC</a>. Your freight stays domestic, your prices stay in CAD, and your inventory doesn't sit on the water.</p>
    <h3>Bag sizes &amp; minimums</h3>
    <ul>
      <li><strong>Half bag (66 lbs)</strong> — available on most origins. Ideal MOQ for smaller micro-roasters.</li>
      <li><strong>Full bag (132-152 lbs)</strong> — standard specialty-grade bag size. Most competitive pricing per pound.</li>
      <li><strong>Multi-bag / pallet orders</strong> — volume pricing available on ongoing contract volume.</li>
    </ul>
    <h3>Pricing model</h3>
    <p>Pricing is per-pound in CAD and includes inbound import costs and Canadian warehouse handling. Outbound freight is quoted separately based on destination, typically via Day &amp; Ross, Loomis, or Purolator for LTL, or UPS/FedEx for smaller shipments. We always quote freight from the closest warehouse to minimize cost.</p>
    <p>Contract volume buyers (quarterly or annual commitments) receive volume pricing tiers and can reserve specific lots at fixed prices. <a href="/contact.html">Contact us</a> with your annual volume projection for a tailored quote.</p>
    <h3>Payment terms</h3>
    <p>New accounts typically pay by credit card or EFT on first order. Established wholesale accounts can be offered Net 15 or Net 30 after a quick credit review. Québec-based accounts can be invoiced directly from our Lévis warehouse; BC/Alberta accounts from Vancouver.</p>
    <h3>Opening an account</h3>
    <p>Send your business information, projected monthly volume, and roasting focus to <a href="/contact.html">Root 86 Coffee</a>. Most Canadian wholesale accounts are approved within one business day and receive their first sample shipment within 48 hours.</p>
  </div>
</section>
{faq_html}
<section class="lp-contact-band">
  <div class="lp-container">
    <h2>Open a <em style="color:var(--red);">wholesale account</em></h2>
    <p>Tell us what you're roasting and your projected volume. We'll send a tailored pricing sheet and sample kit.</p>
    <div style="display:flex; gap:12px; justify-content:center; flex-wrap:wrap;">
      <a href="/contact.html" class="lp-cta lp-cta-primary">Open Wholesale Account</a>
      <a href="/#finder" class="lp-cta lp-cta-ghost">Browse Catalogue</a>
    </div>
  </div>
</section>
{FOOTER_HTML}
</body>
</html>'''


def build_resources_index():
    url = f"{SITE_URL}/resources/"
    title = "Coffee Resources for Canadian Roasters | Root 86 Coffee"
    meta_desc = "Green coffee resources for Canadian micro-roasters — processing, variety, storage, and buying guides. Root 86 Coffee."
    breadcrumb = f'''<script type="application/ld+json">{{
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      {{ "@type": "ListItem", "position": 1, "name": "Home", "item": "{SITE_URL}/" }},
      {{ "@type": "ListItem", "position": 2, "name": "Resources", "item": "{url}" }}
    ]
  }}</script>'''
    return _basic_lp_head(title, meta_desc, url, breadcrumb) + f'''
<body>
{NAV_HTML}
<nav class="lp-breadcrumb"><a href="/">Home</a> &rsaquo; <span>Resources</span></nav>
<section class="lp-hero">
  <div class="lp-container">
    <span class="lp-eyebrow">Green Coffee Resources</span>
    <h1>Resources for <em>Canadian micro-roasters</em></h1>
    <p class="lead">Guides, explainers, and reference material on green coffee — sourcing, processing, varieties, storage, and the Canadian roasting trade.</p>
    <div class="cta-row">
      <a href="/#finder" class="lp-cta lp-cta-primary">Browse Catalogue &rarr;</a>
      <a href="/contact.html" class="lp-cta lp-cta-ghost">Ask Us a Question</a>
    </div>
  </div>
</section>
<section class="lp-section">
  <div class="lp-container">
    <h2>Reference pages</h2>
    <ul>
      <li><a href="/process.html">How Root 86 imports green coffee</a> — our four-stage import process from origin to Canadian warehouse.</li>
      <li><a href="/certifications.html">Certified green coffee</a> — Organic, Fair Trade, Rainforest Alliance, Women's Producer explained.</li>
      <li><a href="/wholesale.html">Buying green coffee wholesale in Canada</a> — MOQ, pricing, payment terms, account setup.</li>
      <li><a href="/roasters.html">Canadian roaster directory</a> — independent roasters across Canada using Root 86 green coffee.</li>
    </ul>
    <h2>Origin guides</h2>
    <p>Deep origin-by-origin guides covering growing regions, varieties, processing methods, harvest calendars, cupping profiles, and Canadian roasting guidance:</p>
    <ul>
      <li><a href="/origins/ethiopia.html">Ethiopian green coffee</a></li>
      <li><a href="/origins/colombia.html">Colombian green coffee</a></li>
      <li><a href="/origins/brazil.html">Brazilian green coffee</a></li>
      <li><a href="/origins/guatemala.html">Guatemalan green coffee</a></li>
      <li><a href="/origins/costa-rica.html">Costa Rican green coffee</a></li>
      <li><a href="/origins/kenya.html">Kenyan green coffee</a></li>
      <li><a href="/origins/honduras.html">Honduran green coffee</a></li>
      <li><a href="/origins/mexico.html">Mexican green coffee</a></li>
      <li><a href="/origins/peru.html">Peruvian green coffee</a></li>
      <li><a href="/origins/rwanda.html">Rwandan green coffee</a></li>
      <li><a href="/origins/tanzania.html">Tanzanian green coffee</a></li>
      <li><a href="/origins/uganda.html">Ugandan green coffee</a></li>
      <li><a href="/origins/indonesia.html">Indonesian green coffee</a></li>
      <li><a href="/origins/panama.html">Panamanian green coffee</a></li>
      <li><a href="/origins/nicaragua.html">Nicaraguan green coffee</a></li>
      <li><a href="/origins/papua-new-guinea.html">Papua New Guinea green coffee</a></li>
    </ul>
    <h2>Articles &amp; guides</h2>
    <p>More in-depth articles coming soon. Topics in the pipeline include: Arabica vs Robusta for Canadian roasters, how to store green coffee in BC humidity, washed vs natural vs honey processing, and reading a coffee contract.</p>
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
        (SITE_URL + "/about.html", "0.7", "monthly"),
        (SITE_URL + "/contact.html", "0.7", "monthly"),
        (SITE_URL + "/roasters.html", "0.6", "monthly"),
        (SITE_URL + "/process.html", "0.8", "monthly"),
        (SITE_URL + "/certifications.html", "0.8", "monthly"),
        (SITE_URL + "/wholesale.html", "0.9", "monthly"),
        (SITE_URL + "/resources/", "0.6", "monthly"),
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

    # Write commercial-intent + informational landing pages
    (ROOT / "process.html").write_text(build_process_page(), encoding="utf-8")
    (ROOT / "certifications.html").write_text(build_certifications_page(), encoding="utf-8")
    (ROOT / "wholesale.html").write_text(build_wholesale_page(), encoding="utf-8")
    (ROOT / "resources").mkdir(exist_ok=True)
    (ROOT / "resources" / "index.html").write_text(build_resources_index(), encoding="utf-8")
    print("Wrote process / certifications / wholesale / resources pages", file=sys.stderr)

    # Write sitemap
    (ROOT / "sitemap.xml").write_text(build_sitemap(coffees, origins), encoding="utf-8")
    print("Wrote sitemap.xml", file=sys.stderr)

    # Write _redirects (Cloudflare Pages 301 map for old Wix URLs)
    (ROOT / "_redirects").write_text(build_redirects(coffees), encoding="utf-8")
    print("Wrote _redirects", file=sys.stderr)

    print("Done.", file=sys.stderr)

if __name__ == "__main__":
    main()
