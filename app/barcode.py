# SPDX-License-Identifier: AGPL-3.0-or-later
"""
barcode.py - Barcode generation for in-house items.

Shared by admin UI and the gen_barcode CLI script.
"""

import re
import barcode as _barcode_lib
from barcode.writer import SVGWriter
from pathlib import Path
import sqlite3


OUTPUT_DIR = Path("barcodes")


def generate_svg(barcode_number: str, item_name: str, price: float | None) -> Path:
    """Generate an EAN-13 SVG label for an in-house item. Returns the saved path."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in item_name)
    item_num = int(barcode_number[7:12])
    filename = OUTPUT_DIR / f"{item_num:05d}_{safe_name}"

    price_label = f"€{price:.2f}" if price else ""
    options = {
        "module_width": 0.8,
        "module_height": 25.0,
        "font_size": 8,
        "text_distance": 3.5,
        "quiet_zone": 6.5,
        "write_text": True,
    }

    ean = _barcode_lib.get("ean13", barcode_number[:12], writer=SVGWriter())
    saved = ean.save(str(filename), options=options)

    svg_path = Path(saved)
    svg_text = svg_path.read_text()

    # Add a comment header so the file is self-documenting
    label_comment = f"  <!-- {item_name}{' — ' + price_label if price_label else ''} -->\n"
    svg_text = svg_text.replace("<svg ", f"{label_comment}<svg ", 1)

    # Expand SVG height to fit an item-name/price label line below the barcode number
    # (python-barcode places the EAN number at y≈29.5 mm; we need ~6 mm more)
    NEW_HEIGHT_MM = 38.0
    w_match = re.search(r'width="([\d.]+)mm"', svg_text)
    orig_width_mm = float(w_match.group(1)) if w_match else 89.0
    svg_text = re.sub(r'height="[\d.]+mm"', f'height="{NEW_HEIGHT_MM:.3f}mm"', svg_text, count=1)

    # Add a viewBox that matches the SVG's user-unit coordinate space.
    # Without this, CSS `width: 75mm` CLIPS the SVG at 75 mm instead of scaling it,
    # slicing off the right-hand guard bars (x ≈ 80–82 mm) and making the
    # code unreadable by any scanner.
    # With viewBox, CSS scaling shrinks the whole barcode proportionally.
    PX_PER_MM = 96 / 25.4   # CSS reference pixel density
    viewbox = (f"0 0 {orig_width_mm * PX_PER_MM:.2f} "
               f"{NEW_HEIGHT_MM * PX_PER_MM:.2f}")
    svg_text = svg_text.replace(
        'xmlns="http://www.w3.org/2000/svg"',
        f'xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}"',
        1
    )

    # Add the human-readable label at the bottom, visible in any SVG viewer.
    label = f"{item_name}{' — ' + price_label if price_label else ''}"
    label_svg = (
        f'    <text x="44.500mm" y="35.000mm" '
        f'style="fill:black;font-size:7pt;text-anchor:middle;">'
        f'{label}</text>\n'
    )
    svg_text = svg_text.replace('</svg>', label_svg + '</svg>')

    svg_path.write_text(svg_text)
    return svg_path


def generate_sheet(conn: sqlite3.Connection, inhouse_prefix: str, shop_name: str = "Bookshop") -> Path:
    """Generate a printable A4 HTML sheet of all in-house item barcodes,
    with checkboxes so the user can choose which ones to print."""
    rows = conn.execute(
        "SELECT barcode, title, price FROM catalog WHERE barcode LIKE ? ORDER BY barcode",
        (inhouse_prefix + "%",)
    ).fetchall()

    items_html = ""
    for row in rows:
        barcode_number = row["barcode"]
        name = row["title"]
        price = row["price"]
        price_str = f"€{price:.2f}" if price else "enter price at counter"

        svg_path = generate_svg(barcode_number, name, price)
        svg_content = svg_path.read_text()
        svg_start = svg_content.find("<svg")
        if svg_start > 0:
            svg_content = svg_content[svg_start:]

        items_html += f"""
        <div class="item" data-code="{barcode_number}">
            <div class="item-name">{name}</div>
            <div class="item-price">{price_str}</div>
            <label class="item-select-wrap">
                <input type="checkbox" class="item-cb" checked
                       onchange="toggleItem(this)">
                <span class="item-cb-label">include in print</span>
            </label>
            <div class="barcode">{svg_content}</div>
            <div class="item-code">{barcode_number}</div>
        </div>
"""

    total = len(rows)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{shop_name} — In-House Barcodes</title>
<style>
  @page {{ size: A4 portrait; margin: 15mm; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
          background: white; color: black; margin: 0; padding: 0 10mm; }}

  /* ── Controls bar (screen only) ───────────────────────────── */
  .controls {{
    position: sticky; top: 0; background: white; z-index: 20;
    padding: 8pt 0 6pt; border-bottom: 2px solid #ccc;
    margin-bottom: 14pt; display: flex; align-items: center;
    flex-wrap: wrap; gap: 6pt;
  }}
  .controls h1 {{
    font-family: Georgia, serif;   /* keep a touch of literary character on the title */
    font-size: 12pt; margin: 0; flex: 1 1 auto;
    letter-spacing: 0.05em;
  }}
  .btn {{
    font-family: inherit; font-size: 9pt;
    border: 1px solid #888; border-radius: 3px;
    padding: 3pt 9pt; cursor: pointer; background: #f5f5f5;
  }}
  .btn:hover {{ background: #e8e8e8; }}
  .btn-print {{
    background: #1a1a1a; color: white; border-color: #1a1a1a;
    font-weight: bold;
  }}
  .btn-print:hover {{ background: #333; }}
  .sel-count {{
    font-size: 8.5pt; color: #666; margin-left: 4pt;
  }}

  /* ── Grid ─────────────────────────────────────────────────── */
  .sheet {{
    display: flex; flex-wrap: wrap;
    gap: 10mm; justify-content: flex-start;
  }}

  /* ── Individual item card ─────────────────────────────────── */
  .item {{
    border: 1px solid #aaa; padding: 5mm 5mm 3mm 5mm;
    width: 85mm; page-break-inside: avoid; text-align: center;
    transition: opacity 0.15s;
  }}
  .item.deselected {{
    opacity: 0.35; border-style: dashed;
  }}
  .item-select-wrap {{
    display: flex; align-items: center; justify-content: center;
    gap: 5pt; cursor: pointer; margin: 2pt 0;
  }}
  .item-cb {{ cursor: pointer; width: 13px; height: 13px; }}
  .item-cb-label {{ font-size: 8pt; color: #888; }}
  .item-name {{ font-size: 11pt; font-weight: bold; margin-bottom: 1pt; }}
  .item-price {{ font-size: 10pt; color: #444; margin-bottom: 4pt; }}
  .barcode svg {{ width: 75mm; height: auto; display: block; margin: 0 auto; }}
  .item-code {{ font-size: 7pt; color: #999; font-family: monospace; margin-top: 2pt; }}

  /* ── Print overrides ──────────────────────────────────────── */
  @media print {{
    .controls {{ display: none; }}
    .item.deselected {{ display: none; }}
    .item-select-wrap {{ display: none; }}   /* hides checkbox only — name is outside this */
    body {{ padding: 0; }}
  }}
</style>
</head>
<body>

<div class="controls">
  <h1>✦ {shop_name.upper()} — IN-HOUSE BARCODES</h1>
  <button class="btn" onclick="selectAll()">✓ All</button>
  <button class="btn" onclick="selectNone()">✗ None</button>
  <button class="btn btn-print" onclick="window.print()">🖨 Print Selected</button>
  <span class="sel-count" id="sel-count">{total} / {total} selected</span>
</div>

<div class="sheet">
{items_html}
</div>

<script>
  function countSelected() {{
    const total = document.querySelectorAll('.item').length;
    const on    = document.querySelectorAll('.item:not(.deselected)').length;
    document.getElementById('sel-count').textContent = on + ' / ' + total + ' selected';
  }}

  function toggleItem(cb) {{
    const item = cb.closest('.item');
    item.classList.toggle('deselected', !cb.checked);
    countSelected();
  }}

  function selectAll() {{
    document.querySelectorAll('.item').forEach(i => i.classList.remove('deselected'));
    document.querySelectorAll('.item-cb').forEach(cb => cb.checked = true);
    countSelected();
  }}

  function selectNone() {{
    document.querySelectorAll('.item').forEach(i => i.classList.add('deselected'));
    document.querySelectorAll('.item-cb').forEach(cb => cb.checked = false);
    countSelected();
  }}
</script>
</body>
</html>
"""

    OUTPUT_DIR.mkdir(exist_ok=True)
    sheet_path = OUTPUT_DIR / "print_sheet.html"
    sheet_path.write_text(html)
    return sheet_path
