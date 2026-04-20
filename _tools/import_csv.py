#!/usr/bin/env python3
"""
Import Wix CSV export into Root 86 coffees.js
Usage: python import_csv.py <path-to-csv> > ../js/coffees.js
"""
import csv, json, sys, re

CSV = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Vandu\Downloads\Wine List\QUME 380\R86Coffees.csv"

WAREHOUSE_MAP = {
    "Vancouver": "Vancouver, BC",
    "Parksville": "Parksville, BC",
    "Quebec": "Lévis, QC",
}

def parse_json_list(s):
    if not s: return []
    try: return json.loads(s)
    except: return []

def clean_list(arr, drop={"Any"}):
    return [x for x in arr if x and x not in drop]

def wix_to_url(wix):
    """wix:image://v1/abc~mv2.png/Foo.png#... -> https://static.wixstatic.com/media/abc~mv2.png"""
    if not wix: return ""
    m = re.match(r"wix:image://v1/([^/]+)", wix)
    if not m: return wix
    return f"https://static.wixstatic.com/media/{m.group(1)}"

def normalize_process(s):
    if not s: return ""
    t = s.lower()
    if "swiss water" in t or "swp" in t: return "Swiss Water Process (Decaf)"
    if "mwp" in t or "mountain water" in t: return "Mountain Water Process (Decaf)"
    if "decaf" in t: return "Decaf"
    if "wet hull" in t or "giling" in t: return "Wet-Hulled"
    if "honey" in t: return "Honey"
    if "natural" in t: return "Natural"
    if "wash" in t: return "Washed"
    # Fall back to original trimmed
    return s.split("\n")[0].strip()

def strip_prefix(s, prefix):
    if not s: return ""
    s = s.strip()
    if s.lower().startswith(prefix.lower()):
        s = s[len(prefix):].strip()
        if s.startswith(":"): s = s[1:].strip()
    return s

def parse_bag(s):
    if not s: return 152
    m = re.search(r"(\d+)", s)
    return int(m.group(1)) if m else 152

def parse_warehouses(arr):
    if not arr: return []
    # "Sold out, épuisé" placeholder => no warehouse
    if len(arr) == 1 and "sold out" in arr[0].lower():
        return []
    out = []
    for w in arr:
        wl = w.lower()
        if "québec seulement" in wl or "quebec only" in wl:
            out.append("Lévis, QC")
        elif "vancouver seulement" in wl or "vancouver only" in wl:
            out.append("Vancouver, BC")
        elif "parksville seulement" in wl or "parksville only" in wl:
            out.append("Parksville, BC")
        else:
            out.append(WAREHOUSE_MAP.get(w, w))
    # dedupe preserving order
    seen, dedup = set(), []
    for w in out:
        if w not in seen: seen.add(w); dedup.append(w)
    return dedup

def clean_text(s):
    if not s: return ""
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    # collapse 3+ newlines
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def extract_varietal(info):
    """Pull Varietal line from Info text blob."""
    if not info: return ""
    m = re.search(r"Varietals?:\s*([^\n]+)", info, re.I)
    return m.group(1).strip() if m else ""

def extract_notes(info, fallback):
    """Try to pull cupping-notes line from Info, else use fallback."""
    if info:
        m = re.search(r"(?:Cupping )?Notes?:\s*([^\n]+)", info, re.I)
        if m: return m.group(1).strip()
    return (fallback or "").strip()

def to_js_string(s):
    """JSON-encode a string for embedding in JS source."""
    return json.dumps(s or "", ensure_ascii=False)

with open(CSV, encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

coffees = []
for i, r in enumerate(rows, 1):
    name = (r.get("Product Name") or "").replace("\n", " ").strip()
    name = re.sub(r"\s+", " ", name)
    origins = clean_list(parse_json_list(r.get("Origin") or ""))
    certs   = clean_list(parse_json_list(r.get("Certa") or ""))
    types   = clean_list(parse_json_list(r.get("Type / Process") or ""), drop={"All"})
    whs     = parse_warehouses(parse_json_list(r.get("Warehouse") or ""))

    favourite = (r.get("R86 Favourite") or "").lower() == "true"
    on_sale   = (r.get("Sale") or "").lower() == "true"
    sold_out  = (r.get("Sold Out") or "").lower() == "true"
    hidden    = (r.get("Hidden") or "").lower() == "true"

    image = wix_to_url(r.get("Image-1") or "")
    info  = clean_text(r.get("Info") or "")
    elevation = strip_prefix(r.get("Elevation") or "", "Elevation")
    process_raw = strip_prefix(r.get("Process") or "", "Process")
    if not process_raw and types:
        process_raw = types[0]
    process = normalize_process(process_raw)
    cupping = clean_text(r.get("cuppingNotes") or "")
    cupping = extract_notes(info, cupping)
    region = (r.get("Region") or "").strip()
    region = re.sub(r"^Region:\s*", "", region, flags=re.I).strip()
    # Also try pulling region from info blob if missing
    if not region and info:
        m = re.search(r"Region:\s*([^\n]+)", info, re.I)
        if m: region = m.group(1).strip()
    main_text = clean_text(r.get("Main text") or "")
    bag = parse_bag(r.get("Bag Size") or "")
    varietal = extract_varietal(info)

    origin = origins[0] if origins else "Blend"
    # Normalize common typo
    if origin.lower() == "columbia": origin = "Colombia"
    if origin.upper() == "PNG": origin = "Papua New Guinea"
    # If origin is the same as product's first word, skip region duplication
    if not region:
        # attempt to parse region from product name (word after origin)
        # keep empty; admin can fill in
        region = ""

    description = info or main_text or ""
    # Avoid Main text duplicating product name on first line
    if description.lower().startswith(name.lower()):
        description = description[len(name):].lstrip("\n ").strip()

    coffees.append({
        "id": i,
        "name": name,
        "origin": origin,
        "region": region,
        "process": process,
        "certifications": certs,
        "bagWeight": bag,
        "warehouses": whs,
        "available": not sold_out,
        "grade": "",
        "variety": varietal,
        "altitude": elevation,
        "tastingNotes": cupping,
        "description": description,
        "image": image,
        "favourite": favourite,
        "onSale": on_sale,
        "soldOut": sold_out,
        "hidden": hidden,
    })

# Build output
def emit_coffee(c):
    lines = []
    lines.append(f"    id: {c['id']}")
    lines.append(f"    name: {to_js_string(c['name'])}")
    lines.append(f"    origin: {to_js_string(c['origin'])}")
    lines.append(f"    region: {to_js_string(c['region'])}")
    lines.append(f"    process: {to_js_string(c['process'])}")
    lines.append(f"    certifications: {json.dumps(c['certifications'], ensure_ascii=False)}")
    lines.append(f"    bagWeight: {c['bagWeight']}")
    lines.append(f"    warehouses: {json.dumps(c['warehouses'], ensure_ascii=False)}")
    lines.append(f"    available: {'true' if c['available'] else 'false'}")
    lines.append(f"    grade: {to_js_string(c['grade'])}")
    lines.append(f"    variety: {to_js_string(c['variety'])}")
    lines.append(f"    altitude: {to_js_string(c['altitude'])}")
    lines.append(f"    tastingNotes: {to_js_string(c['tastingNotes'])}")
    lines.append(f"    description: {to_js_string(c['description'])}")
    lines.append(f"    image: {to_js_string(c['image'])}")
    if c['favourite']: lines.append("    favourite: true")
    if c['onSale']:    lines.append("    onSale: true")
    if c['soldOut']:   lines.append("    soldOut: true")
    if c['hidden']:    lines.append("    hidden: true")
    return "  {\n" + ",\n".join(lines) + "\n  }"

origins_all = sorted({c["origin"] for c in coffees if c["origin"]})
processes_all = sorted({c["process"] for c in coffees if c["process"]})
certs_all = sorted({x for c in coffees for x in c["certifications"]})
whs_all = sorted({w for c in coffees for w in c["warehouses"]})

output = f"""// ============================================================
//  ROOT 86 COFFEE - Coffee Data File
//  Imported from Wix export on {__import__('datetime').date.today()}.
//  Edit via admin.html. Fields marked hidden:true are kept in
//  the data but not shown on the public site.
// ============================================================

const COFFEES = [
{','.join(emit_coffee(c) for c in coffees)}
];

// ============================================================
//  FILTER OPTIONS
// ============================================================

const FILTER_OPTIONS = {{
  origins: {json.dumps(origins_all, ensure_ascii=False)},
  processes: {json.dumps(processes_all, ensure_ascii=False)},
  certifications: {json.dumps(certs_all, ensure_ascii=False)},
  warehouses: {json.dumps(whs_all, ensure_ascii=False)}
}};

// ============================================================
//  SITE SETTINGS
// ============================================================

const SITE_SETTINGS = {{
  companyName: "Root 86 Coffee",
  email: "root86coffee@gmail.com",
  phone: "1-855-908-0086",
  address: "PO Box 60008, Nanaimo, BC V9S 0A5",
  tagline: "Green Coffee Specialists. Proudly Supplying Canada's Micro-Roasters.",
  emailjsServiceId: "YOUR_SERVICE_ID",
  emailjsTemplateId: "YOUR_TEMPLATE_ID",
  emailjsPublicKey: "YOUR_PUBLIC_KEY"
}};
"""
# On Windows, stdout defaults to cp1252; write bytes
sys.stdout.buffer.write(output.encode("utf-8"))
