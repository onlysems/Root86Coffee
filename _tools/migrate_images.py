#!/usr/bin/env python3
"""
One-shot migration: download every Wix-hosted image referenced in
js/coffees.js, convert to WebP, commit to /images/coffees/<slug>.webp,
and rewrite coffees.js so each coffee points at its local file.

Re-running is safe — already-local URLs are skipped.

Usage:  python _tools/migrate_images.py
"""
import io, re, sys, pathlib, urllib.request, urllib.parse, hashlib
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "images" / "coffees"
OUT.mkdir(parents=True, exist_ok=True)

# Borrow slugify from the generator so naming stays in sync.
sys.path.insert(0, str(ROOT / "_tools"))
from generate_seo import slugify, load_coffees  # noqa: E402

UA = "Mozilla/5.0 (compatible; Root86Migrate/1.0)"

def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()

def to_webp(raw: bytes, quality: int = 82, max_w: int = 1400) -> bytes:
    im = Image.open(io.BytesIO(raw))
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
    if im.width > max_w:
        new_h = int(im.height * (max_w / im.width))
        im = im.resize((max_w, new_h), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=quality, method=6)
    return buf.getvalue()

def main():
    src_js = (ROOT / "js" / "coffees.js").read_text(encoding="utf-8")
    coffees = load_coffees()

    # URL → local relative path. Dedupe so shared URLs download once.
    url_to_local: dict[str, str] = {}
    skipped, downloaded, failed = 0, 0, 0

    for c in coffees:
        url = c.get("image", "") or ""
        if not url:
            continue
        if not url.startswith("http"):
            skipped += 1
            continue  # already local
        if url in url_to_local:
            continue

        slug = slugify(c["name"])
        out_path = OUT / f"{slug}.webp"
        try:
            raw = fetch(url)
            webp = to_webp(raw)
            out_path.write_bytes(webp)
            local_rel = f"/images/coffees/{slug}.webp"
            url_to_local[url] = local_rel
            downloaded += 1
            print(f"  OK  {slug}.webp  ({len(webp)//1024} KB)  ← {url[:60]}…")
        except Exception as e:
            failed += 1
            print(f"  FAIL {slug}  {e}  ({url})", file=sys.stderr)

    # Rewrite coffees.js in-place.
    new_js = src_js
    changes = 0
    for old_url, new_rel in url_to_local.items():
        # Match the URL as a JS string literal (double-quoted).
        pattern = re.escape(old_url)
        before = new_js
        new_js = re.sub(f'"{pattern}"', f'"{new_rel}"', new_js)
        if new_js != before:
            changes += 1

    (ROOT / "js" / "coffees.js").write_text(new_js, encoding="utf-8")

    print(f"\nSummary: {downloaded} downloaded, {skipped} already-local skipped, "
          f"{failed} failed, {changes} URL occurrences rewritten in coffees.js")

if __name__ == "__main__":
    main()
