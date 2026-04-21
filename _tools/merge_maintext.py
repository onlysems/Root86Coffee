"""
Read the original Wix CSV export and merge the "Main text" column into
js/coffees.js as a new `mainText` field per coffee.

Matches coffees by normalized name. Reports any misses.
"""
import csv, re, sys, io, json, pathlib

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

CSV_PATH = r"C:\Users\Vandu\Downloads\extra\R86Coffees.csv"
JS_PATH  = pathlib.Path(r"C:\Users\Vandu\root86coffee\js\coffees.js")

def norm(s):
    s = s or ""
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s

# Build name -> main text map
main_map = {}
with open(CSV_PATH, "r", encoding="utf-8-sig", newline="") as f:
    for row in csv.DictReader(f):
        name = (row.get("Product Name") or "").strip()
        mt   = (row.get("Main text") or "").strip()
        if name:
            main_map[norm(name)] = mt

src = JS_PATH.read_text(encoding="utf-8")

# Iterate each coffee block: { ... name: "...", ... description: "...", ... image: "..." ... }
# We'll find blocks by scanning for `name: "..."` then inject mainText after `description: "..."` line.

# Pattern: `    description: "....",\n` (single-line JS string, escaped quotes handled with .*?)
def find_blocks(js):
    # match indexed coffee blocks
    pattern = re.compile(r"\{\s*id:\s*\d+,.*?\n  \}", re.DOTALL)
    return [(m.start(), m.end(), m.group(0)) for m in pattern.finditer(js)]

blocks = find_blocks(src)
print(f"Found {len(blocks)} coffee blocks in coffees.js")

# For each block, extract name and replace if possible
new_src = src
offset = 0
miss = []
hit = 0
skipped_empty = 0
already = 0
for start, end, block in blocks:
    nm_match = re.search(r'name:\s*"((?:[^"\\]|\\.)*)"', block)
    if not nm_match:
        continue
    name = bytes(nm_match.group(1), "utf-8").decode("unicode_escape")
    key = norm(name)
    if key not in main_map:
        miss.append(name)
        continue
    mt = main_map[key]
    if not mt:
        skipped_empty += 1
        continue
    # Skip if block already has mainText
    if re.search(r'\n\s*mainText:\s*"', block):
        already += 1
        continue
    # Escape for JS string
    mt_escaped = mt.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")
    # Insert a new line after the `description: "...",` line
    desc_match = re.search(r'(\n(\s*)description:\s*"(?:[^"\\]|\\.)*",?)', block)
    if not desc_match:
        # fallback: insert before image line
        img_match = re.search(r'(\n(\s*)image:\s*"(?:[^"\\]|\\.)*",?)', block)
        if not img_match:
            miss.append(name + " (no anchor)")
            continue
        insert_after = img_match.end()
        indent = img_match.group(2)
    else:
        insert_after = desc_match.end()
        indent = desc_match.group(2)
    new_block = block[:insert_after] + f'\n{indent}mainText: "{mt_escaped}",' + block[insert_after:]
    # Commit to new_src using updated offset
    s = start + offset
    e = end + offset
    new_src = new_src[:s] + new_block + new_src[e:]
    offset += len(new_block) - len(block)
    hit += 1

JS_PATH.write_text(new_src, encoding="utf-8")
print(f"Injected mainText into {hit} blocks")
print(f"Skipped (already had mainText): {already}")
print(f"Skipped (empty CSV main text): {skipped_empty}")
if miss:
    print(f"NO MATCH ({len(miss)}):")
    for n in miss:
        print(f"  - {n}")
