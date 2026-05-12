"""
Convert SEMANTIC_RAG_ENGINE_WHITEPAPER.md → SEMANTIC_RAG_ENGINE_WHITEPAPER.pdf
Pipeline: MD → Typst (.typ) via pandoc → PDF via typst compiler

Run:
    uv run --with pypandoc_binary --with typst scripts/build_pdf_typst.py
"""

import re
import tempfile
from pathlib import Path

import pypandoc
import typst

ROOT   = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "SEMANTIC_RAG_ENGINE_WHITEPAPER.md"
OUTPUT = ROOT / "SEMANTIC_RAG_ENGINE_WHITEPAPER.pdf"

# ── Typst template ────────────────────────────────────────────────────────────
TYPST_TEMPLATE = r"""
// ── Page & fonts ──────────────────────────────────────────────────────────────
#set page(
  paper: "a4",
  margin: (top: 28mm, bottom: 30mm, left: 25mm, right: 22mm),
  numbering: "1",
  number-align: center,
  header: context {
    if counter(page).get().first() > 1 [
      #set text(8pt, fill: luma(160))
      #h(1fr) Semantic RAG Engine — Technical Whitepaper
      #line(length: 100%, stroke: 0.4pt + luma(200))
    ]
  },
  footer: context {
    if counter(page).get().first() > 1 [
      #set text(9pt, fill: luma(160))
      #h(1fr) #counter(page).display()  #h(1fr)
    ]
  },
)

#set text(
  font: ("Times New Roman", "TeX Gyre Termes", "Liberation Serif", "serif"),
  size: 11pt,
  lang: "en",
  hyphenate: true,
)

#set par(
  justify: true,
  leading: 0.78em,
  spacing: 0.95em,
)

// ── Headings ─────────────────────────────────────────────────────────────────
#show heading.where(level: 1): it => {
  pagebreak(weak: true)
  v(2em)
  text(20pt, weight: 700, fill: rgb("#0f2040"), it.body)
  v(0.2em)
  line(length: 100%, stroke: 2pt + rgb("#2563eb"))
  v(0.8em)
}

#show heading.where(level: 2): it => {
  v(1.2em)
  text(13pt, weight: 700, fill: rgb("#1d4ed8"), it.body)
  v(0.1em)
  line(length: 100%, stroke: 0.8pt + rgb("#bfdbfe"))
  v(0.4em)
}

#show heading.where(level: 3): it => {
  v(0.9em)
  text(11.5pt, weight: 600, fill: rgb("#1e40af"), it.body)
  v(0.3em)
}

#show heading.where(level: 4): it => {
  v(0.7em)
  text(11pt, weight: 600, fill: rgb("#374151"), it.body)
  v(0.2em)
}

// ── Code ─────────────────────────────────────────────────────────────────────
#show raw.where(block: false): it => {
  text(
    font: ("Courier New", "DejaVu Sans Mono", "monospace"),
    size: 8.8pt,
    fill: rgb("#be185d"),
    it
  )
}

#show raw.where(block: true): it => {
  block(
    fill: rgb("#0f172a"),
    stroke: (left: 3pt + rgb("#2563eb")),
    inset: 12pt,
    radius: 5pt,
    width: 100%,
    breakable: true,
    text(font: ("Courier New", "DejaVu Sans Mono", "monospace"),
         size: 8.2pt, fill: rgb("#e2e8f0"), it)
  )
}

// ── Tables ───────────────────────────────────────────────────────────────────
#set table(
  fill: (_, y) => if y == 0 { rgb("#0f2040") } else if calc.odd(y) { white } else { rgb("#f8fafc") },
  stroke: (_, y) => if y == 0 { none } else { (bottom: 0.5pt + rgb("#e5e7eb")) },
  inset: (x: 10pt, y: 6pt),
)

#show table.cell.where(y: 0): it => {
  set text(weight: 700, fill: white, size: 9pt)
  it
}

#show table: it => {
  set text(size: 9.5pt)
  block(width: 100%, breakable: true, it)
}

// ── Blockquotes (pandoc renders as #quote) ───────────────────────────────────
#show quote: it => {
  block(
    fill: rgb("#eff6ff"),
    stroke: (left: 3pt + rgb("#2563eb")),
    inset: (left: 14pt, top: 8pt, bottom: 8pt, right: 8pt),
    radius: (right: 4pt),
    width: 100%,
    text(style: "italic", fill: rgb("#1e40af"), it.body)
  )
}

// ── Pandoc-generated helpers ─────────────────────────────────────────────────
#let horizontalrule = {
  v(4pt)
  line(length: 100%, stroke: 0.75pt + rgb("#e5e7eb"))
  v(4pt)
}

// ── Links ────────────────────────────────────────────────────────────────────
#show link: it => {
  set text(fill: rgb("#2563eb"))
  it
}

// ── Strong / emph ────────────────────────────────────────────────────────────
#show strong: it => text(weight: 700, fill: rgb("#111827"), it)

// ── Cover page ───────────────────────────────────────────────────────────────
#page(
  margin: (top: 35mm, bottom: 30mm, left: 30mm, right: 30mm),
  header: none,
  footer: none,
)[
  #v(1fr)
  #align(center)[
    #set text(hyphenate: false)
    #set par(justify: false)
    #text(32pt, weight: 700, fill: rgb("#0f2040"))[SEMANTIC RAG ENGINE]
    #v(4mm)
    #line(length: 60mm, stroke: 2pt + rgb("#2563eb"))
    #v(6mm)
    #text(12pt, fill: rgb("#4b5563"), style: "italic")[
      Architecture, Implementation and Research Foundations \
      of a Vertical Retrieval-Augmented Generation System \
      for PDF Documents
    ]
    #v(16mm)
    #table(
      columns: (auto, auto),
      align: (left, left),
      fill: (_, y) => none,
      stroke: (_, y) => if y == 0 { (bottom: 1.5pt + rgb("#1d4ed8")) } else { (bottom: 0.5pt + rgb("#e5e7eb")) },
      inset: (x: 12pt, y: 6pt),
      table.header([*Field*], [*Value*]),
      [*Version*],        [1.0],
      [*Date*],           [May 2026],
      [*Author*],         [Vincenzo Calabrese],
      [*Contact*],        [vincenzo.calabrese\@gmail.com],
    )
    #v(14mm)
    #block(width: 140mm)[
      #set text(12pt, style: "italic", fill: rgb("#1d4ed8"))
      "The gap between what language models know and what enterprises \
       need is not a parameter problem — it is a retrieval problem."
    ]
  ]
  #v(1fr)
]

$body$
"""

# ── Pre-process markdown ──────────────────────────────────────────────────────
print("Pre-processing markdown …", flush=True)
raw = SOURCE.read_text(encoding="utf-8")

# Strip YAML front-matter
if raw.startswith("---"):
    end = raw.index("---", 3)
    raw = raw[end + 3:].lstrip("\n")

# Remove the hand-crafted cover block (everything before ## Table of Contents)
# pandoc will handle the body; our Typst template provides the cover
toc_pos = raw.find("## Table of Contents")
if toc_pos != -1:
    raw = raw[toc_pos:]

# Remove the ToC section itself — Typst outline handles it
toc_end = re.search(r"\n(?=# Part|\n# )", raw)
if not toc_end:
    # fallback: find first Part heading
    toc_end = re.search(r"\n# Part", raw)
if toc_end:
    toc_raw  = raw[:toc_end.start()]
    body_raw = raw[toc_end.start():]
else:
    body_raw = raw

# Replace ✓ ✗ ► ▼ with Typst-safe text equivalents
CHAR_MAP = {
    "►": "→",
    "▼": "↓",
    "║": "|",
}
for k, v in CHAR_MAP.items():
    body_raw = body_raw.replace(k, v)

# Write cleaned markdown to temp file
with tempfile.NamedTemporaryFile(suffix=".md", mode="w",
                                  encoding="utf-8", delete=False) as tmp_md:
    tmp_md.write(body_raw)
    tmp_md_path = tmp_md.name

# Write template to temp file
with tempfile.NamedTemporaryFile(suffix=".typ", mode="w",
                                  encoding="utf-8", delete=False) as tmp_tpl:
    tmp_tpl.write(TYPST_TEMPLATE)
    tmp_tpl_path = tmp_tpl.name

# Write Typst output path
typ_path = ROOT / "SEMANTIC_RAG_ENGINE_WHITEPAPER.typ"

# ── MD → Typst via pandoc ─────────────────────────────────────────────────────
print("Converting MD → Typst (pandoc) …", flush=True)
pypandoc.convert_file(
    tmp_md_path,
    "typst",
    outputfile=str(typ_path),
    extra_args=[
        f"--template={tmp_tpl_path}",
        "--wrap=none",
        "--standalone",
    ],
)
print(f"  .typ written ({typ_path.stat().st_size // 1024} KB)", flush=True)

# ── Post-process .typ: unwrap #block[...] that contain headings ───────────────
# Pandoc wraps some content in #block[] which forbids pagebreaks inside.
typ_src = typ_path.read_text(encoding="utf-8")

def _unwrap_blocks_with_headings(src: str) -> str:
    """Remove #block[ ... ] wrappers whose content contains = headings."""
    result = []
    i = 0
    lines = src.splitlines(keepends=True)
    while i < len(lines):
        line = lines[i]
        if line.strip() == "#block[":
            # collect until matching ]
            block_lines = []
            depth = 1
            j = i + 1
            while j < len(lines) and depth > 0:
                l = lines[j]
                if l.strip() == "#block[":
                    depth += 1
                elif l.strip() == "]" and depth > 0:
                    depth -= 1
                    if depth == 0:
                        break
                block_lines.append(l)
                j += 1
            # Check if any line inside is a heading
            has_heading = any(
                bl.lstrip().startswith("= ") or
                bl.lstrip().startswith("== ") or
                bl.lstrip().startswith("=== ")
                for bl in block_lines
            )
            if has_heading:
                result.extend(block_lines)  # emit content without wrapper
                i = j + 1  # skip closing ]
            else:
                result.append(line)         # keep #block[ as-is
                i += 1
        else:
            result.append(line)
            i += 1
    return "".join(result)

typ_src = _unwrap_blocks_with_headings(typ_src)

# ── Post-process .typ: fix table column widths ───────────────────────────────
# Pandoc emits equal-fraction columns; give Notes/last column more space.
# 3-col tables: Component(35%) | Status(15%) | Notes(50%)
typ_src = typ_src.replace(
    "columns: (33.33%, 33.33%, 33.33%),",
    "columns: (35%, 15%, 50%),"
)
# Also fix pandoc's bare `columns: 3` (no widths)
typ_src = re.sub(
    r"columns: 3,",
    "columns: (35%, 15%, 50%),",
    typ_src
)
# 4-col equal tables — give last col more room
typ_src = typ_src.replace(
    "columns: (25%, 25%, 25%, 25%),",
    "columns: (30%, 20%, 20%, 30%),"
)
# 2-col equal tables — keep 50/50 but enforce fr so text wraps
typ_src = typ_src.replace(
    "columns: (50%, 50%),",
    "columns: (1fr, 1fr),"
)

typ_path.write_text(typ_src, encoding="utf-8")

# ── Post-process .typ: unwrap #figure(align(center)[#table(...)]) ────────────
# pandoc wraps every table in #figure which is non-breakable by default.
# Replace with a plain block so long tables can span pages.
def _unwrap_figure_tables(src: str) -> str:
    lines = src.splitlines(keepends=True)
    result = []
    i = 0
    while i < len(lines):
        # Detect start of figure-wrapped table
        if (lines[i].strip() == "#figure(" and
                i + 1 < len(lines) and
                lines[i + 1].strip().startswith("align(center)[#table(")):
            # Find the closing pattern: a line that is just ")]" or "  )]"
            # followed by ", kind: table" or "  , kind: table"
            j = i + 2
            depth = 1  # we are inside align(center)[...
            table_lines = [lines[i + 1].replace("align(center)[#table(", "#table(", 1)]
            while j < len(lines) and depth > 0:
                l = lines[j]
                stripped = l.strip()
                if stripped.endswith("["):
                    depth += 1
                if stripped in (")]", ")]") or stripped.startswith(")]"):
                    depth -= 1
                    if depth == 0:
                        # closing )] of align(center)[...] → replace with )
                        table_lines.append(l.replace(")]", ")", 1))
                        j += 1
                        # skip ", kind: table" and "  )" lines
                        while j < len(lines) and lines[j].strip() in (",  kind: table", ", kind: table", ")"):
                            j += 1
                        break
                else:
                    table_lines.append(l)
                j += 1
            result.extend(table_lines)
            i = j
        else:
            result.append(lines[i])
            i += 1
    return "".join(result)

typ_src = typ_path.read_text(encoding="utf-8")
typ_src = _unwrap_figure_tables(typ_src)
typ_path.write_text(typ_src, encoding="utf-8")

# ── Typst → PDF ───────────────────────────────────────────────────────────────
print("Compiling Typst → PDF …", flush=True)
typst.compile(str(typ_path), output=str(OUTPUT))

print(f"\n✓ PDF written → {OUTPUT}")
print(f"  Size: {OUTPUT.stat().st_size / 1024:.0f} KB")

# Cleanup temp files
Path(tmp_md_path).unlink(missing_ok=True)
Path(tmp_tpl_path).unlink(missing_ok=True)
