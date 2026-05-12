"""
Convert SEMANTIC_RAG_ENGINE_WHITEPAPER.md → SEMANTIC_RAG_ENGINE_WHITEPAPER.pdf
Uses: markdown, weasyprint, pygments, matplotlib

Run:
    uv run --with markdown --with weasyprint --with pygments --with matplotlib \
        scripts/build_pdf.py
"""

import base64
import io
import re
import warnings
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import markdown
from weasyprint import HTML, CSS

matplotlib.use("Agg")
warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "SEMANTIC_RAG_ENGINE_WHITEPAPER.md"
OUTPUT = ROOT / "SEMANTIC_RAG_ENGINE_WHITEPAPER.pdf"


# ── render a LaTeX formula to a base64 PNG <img> ─────────────────────────────

def _latex_to_img_tag(formula: str, display: bool) -> str:
    expr = f"${formula.strip()}$"
    fontsize = 11 if display else 9
    MAX_WIDTH_IN = 6.4   # A4 content width (210 - 42 mm margins)
    try:
        fig = plt.figure(figsize=(0.01, 0.01))
        fig.patch.set_alpha(0)
        text = fig.text(0, 0, expr, fontsize=fontsize, color="#1f2937", usetex=False)
        fig.canvas.draw()
        bbox = text.get_window_extent(renderer=fig.canvas.get_renderer())
        pad = 4
        w_in = (bbox.width  + pad * 2) / fig.dpi
        h_in = (bbox.height + pad * 2) / fig.dpi
        if not display and w_in > MAX_WIDTH_IN * 0.6:
            display = True
        if w_in > MAX_WIDTH_IN:
            h_in = h_in * (MAX_WIDTH_IN / w_in)
            w_in = MAX_WIDTH_IN
        fig.set_size_inches(max(w_in, 0.5), max(h_in, 0.3))
        text.set_position((pad / (fig.get_figwidth()  * fig.dpi),
                           pad / (fig.get_figheight() * fig.dpi)))
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=300,
                    bbox_inches="tight", transparent=True, pad_inches=0.04)
        plt.close(fig)
        b64 = base64.b64encode(buf.getvalue()).decode()
        style = (
            'display:block;margin:8pt auto;max-width:100%;height:auto'
            if display else
            'vertical-align:middle;margin:0 2pt;max-width:100%;height:auto'
        )
        return f'<img src="data:image/png;base64,{b64}" style="{style}" alt="{formula.strip()}">'
    except Exception:
        plt.close("all")
        tag = "p" if display else "code"
        return f'<{tag} style="font-family:monospace;color:#be185d">{formula.strip()}</{tag}>'


def _replace_math(raw: str) -> str:
    def _block(m):
        return "\n" + _latex_to_img_tag(m.group(1), display=True) + "\n"
    raw = re.sub(r"\$\$(.+?)\$\$", _block, raw, flags=re.DOTALL)

    def _inline(m):
        content = m.group(1)
        if re.fullmatch(r"[\d,. ]+", content):
            return m.group(0)
        return _latex_to_img_tag(content, display=False)
    raw = re.sub(r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)", _inline, raw)
    return raw


# ── pre-process markdown ─────────────────────────────────────────────────────

_EMOJI_MAP = {
    "✅": '<span class="emoji-ok">✓</span>',
    "❌": '<span class="emoji-ko">✗</span>',
    "⚠️": '<span class="emoji-warn">⚠</span>',
    "🔄": '<span class="emoji-info">↻</span>',
    "🟢": '<span class="emoji-ok">●</span>',
    "🔴": '<span class="emoji-ko">●</span>',
}

def _replace_emoji(raw: str) -> str:
    for emoji, html in _EMOJI_MAP.items():
        raw = raw.replace(emoji, html)
    return raw


def _preprocess(raw: str) -> str:
    """Typographic pre-processing before markdown parsing."""
    # 0. Replace emoji with styled spans WeasyPrint can render
    raw = _replace_emoji(raw)
    # 1. Replace sequences of <br> spacers with a single div spacer
    raw = re.sub(r"(<br\s*/?>[\s\n]*){2,}", '\n<div class="spacer"></div>\n', raw)
    # 2. Wrap the cover block (everything before ## Table of Contents) in a cover div
    toc_pos = raw.find("## Table of Contents")
    if toc_pos != -1:
        cover = raw[:toc_pos].strip()
        rest  = raw[toc_pos:]
        raw = f'<div class="cover">\n\n{cover}\n\n</div>\n\n{rest}'
    return raw


# ── strip YAML front-matter ──────────────────────────────────────────────────
raw = SOURCE.read_text(encoding="utf-8")
if raw.startswith("---"):
    end = raw.index("---", 3)
    raw = raw[end + 3:].lstrip("\n")

# ── render math BEFORE markdown parsing ─────────────────────────────────────
print("Rendering math formulas …", flush=True)
raw = _replace_math(raw)
raw = _preprocess(raw)

# ── markdown → HTML body ─────────────────────────────────────────────────────
md = markdown.Markdown(
    extensions=[
        "tables",
        "fenced_code",
        "codehilite",
        "toc",
        "attr_list",
        "def_list",
        "footnotes",
        "sane_lists",
    ],
    extension_configs={
        "codehilite": {"css_class": "highlight", "guess_lang": False},
        "toc": {"permalink": False},
    },
)
body_html = md.convert(raw)

# ── full HTML document ───────────────────────────────────────────────────────
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Semantic RAG Engine — Whitepaper</title>
</head>
<body>
{body}
</body>
</html>"""

full_html = HTML_TEMPLATE.format(body=body_html)

# ── CSS ───────────────────────────────────────────────────────────────────────
CSS_STYLE = """
/* ── System fonts (no external import — WeasyPrint safe) ── */

/* ── Page setup ── */
@page {
    size: A4;
    margin: 25mm 22mm 28mm 25mm;
    @bottom-center {
        content: counter(page);
        font-family: "Segoe UI", Helvetica, Arial, sans-serif;
        font-size: 9pt;
        color: #9ca3af;
    }
    @top-right {
        content: "Semantic RAG Engine — Technical Whitepaper";
        font-family: "Segoe UI", Helvetica, Arial, sans-serif;
        font-size: 8pt;
        color: #9ca3af;
        border-bottom: 0.5pt solid #e5e7eb;
        padding-bottom: 3pt;
    }
}

/* Cover page: no running header/footer */
@page :first {
    @bottom-center { content: none; }
    @top-right     { content: none; }
    margin: 30mm 25mm 30mm 25mm;
}

/* ── Base ── */
* { box-sizing: border-box; }

body {
    font-family: "Segoe UI", "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.6;
    color: #1f2937;
    background: #ffffff;
}

/* ── Cover page ── */
.cover {
    page: cover-page;
    text-align: center;
    padding-top: 30mm;
}

.cover h1 {
    font-size: 32pt;
    font-weight: 700;
    color: #0f2040;
    border: none;
    margin: 0 0 6mm 0;
    padding: 0;
    letter-spacing: -0.5pt;
    page-break-before: avoid;
}

.cover h3 {
    font-size: 12pt;
    font-weight: 400;
    color: #4b5563;
    margin: 0 0 16mm 0;
    line-height: 1.5;
    border: none;
}

/* Cover metadata table — clean, no dark header */
.cover table {
    width: auto;
    margin: 0 auto 10mm auto;
    border-collapse: collapse;
    font-size: 10pt;
}

.cover table thead tr {
    background: transparent !important;
    color: #1f2937 !important;
    border-bottom: 1.5pt solid #1d4ed8;
}

.cover table thead th {
    color: #1f2937 !important;
    font-weight: 600;
    padding: 5pt 16pt;
    letter-spacing: 0.2pt;
}

.cover table tbody tr {
    background: transparent !important;
    border-bottom: 0.5pt solid #e5e7eb;
}

.cover table tbody td {
    padding: 5pt 16pt;
    color: #374151;
}

/* Cover blockquote — the epigraph */
.cover blockquote {
    border: none;
    background: transparent;
    font-size: 12pt;
    font-style: italic;
    color: #1d4ed8;
    margin: 16mm auto 12mm auto;
    max-width: 130mm;
    padding: 0;
    text-align: center;
}
.cover blockquote p { margin: 0; }

/* Cover intro paragraph (italic) */
.cover em {
    font-size: 10pt;
    color: #6b7280;
    display: block;
    margin: 0 auto;
    max-width: 140mm;
}

/* Cover horizontal rules */
.cover hr {
    border: none;
    border-top: 1.5pt solid #2563eb;
    margin: 8mm auto;
    width: 60mm;
}

/* Spacer div */
.spacer { height: 6mm; }

/* ── Part headings (# Part …) ── */
h1 {
    font-size: 20pt;
    font-weight: 700;
    color: #0f2040;
    border-bottom: 2.5pt solid #2563eb;
    padding-bottom: 5pt;
    margin-top: 0;
    margin-bottom: 10pt;
    page-break-before: always;
    page-break-after: avoid;
}

/* First h1 in document body (after cover) */
.cover + h1,
body > h1:first-of-type {
    page-break-before: always;
}

/* ── Section headings ── */
h2 {
    font-size: 13.5pt;
    font-weight: 700;
    color: #1d4ed8;
    border-bottom: 1pt solid #bfdbfe;
    padding-bottom: 3pt;
    margin-top: 18pt;
    margin-bottom: 8pt;
    page-break-after: avoid;
}

h3 {
    font-size: 11pt;
    font-weight: 600;
    color: #1e40af;
    margin-top: 14pt;
    margin-bottom: 4pt;
    page-break-after: avoid;
}

h4 {
    font-size: 10.5pt;
    font-weight: 600;
    color: #374151;
    margin-top: 10pt;
    margin-bottom: 3pt;
    page-break-after: avoid;
}

h5, h6 {
    font-size: 10pt;
    font-weight: 500;
    color: #6b7280;
    margin-top: 8pt;
    margin-bottom: 2pt;
}

/* ── Paragraphs & lists ── */
p {
    margin: 0 0 7pt 0;
    orphans: 3;
    widows: 3;
}

ul, ol {
    margin: 4pt 0 8pt 0;
    padding-left: 16pt;
}

li {
    margin-bottom: 3pt;
    line-height: 1.55;
}

li > ul, li > ol {
    margin-top: 2pt;
    margin-bottom: 2pt;
}

/* ToC list — less dense, better spacing */
.toc ul, body > ul:first-of-type {
    list-style: none;
    padding-left: 0;
}

/* ── Links ── */
a {
    color: #2563eb;
    text-decoration: none;
}

/* ── Inline code ── */
code {
    font-family: "Courier New", "DejaVu Sans Mono", monospace;
    font-size: 8.8pt;
    background: #f1f5f9;
    color: #be185d;
    padding: 1pt 4pt;
    border-radius: 3pt;
    border: 0.5pt solid #e2e8f0;
}

/* ── Code blocks ── */
pre {
    background: #0f172a;
    border-radius: 5pt;
    padding: 10pt 14pt;
    margin: 8pt 0 12pt 0;
    page-break-inside: avoid;
    border-left: 3pt solid #2563eb;
    white-space: pre-wrap;       /* ← wrap long lines */
    word-break: break-all;
    overflow-wrap: break-word;
}

pre code {
    font-family: "Courier New", "DejaVu Sans Mono", monospace;
    font-size: 8.2pt;
    background: transparent;
    color: #e2e8f0;
    padding: 0;
    border: none;
    border-radius: 0;
    white-space: pre-wrap;
    word-break: break-all;
}

/* ── Syntax highlight ── */
.highlight { background: #0f172a !important; border-radius: 5pt; }
.highlight .k  { color: #93c5fd; font-weight: 500; }
.highlight .s, .highlight .s1, .highlight .s2 { color: #86efac; }
.highlight .c1, .highlight .cm { color: #6b7280; font-style: italic; }
.highlight .n  { color: #e2e8f0; }
.highlight .mi { color: #fca5a5; }
.highlight .nb { color: #c4b5fd; }
.highlight .nf { color: #67e8f9; }
.highlight .o  { color: #93c5fd; }
.highlight .p  { color: #e2e8f0; }
.highlight .kn { color: #93c5fd; }
.highlight .nn { color: #fde68a; }

/* ── Tables ── */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 8pt 0 12pt 0;
    font-size: 9.5pt;
    page-break-inside: avoid;
    table-layout: fixed;
    word-break: break-word;
    overflow-wrap: break-word;
}

thead tr {
    background: #0f2040;
    color: #ffffff;
}

thead th {
    padding: 6pt 10pt;
    text-align: left;
    font-weight: 600;
    font-size: 9pt;
    letter-spacing: 0.3pt;
    word-break: break-word;
}

tbody tr {
    border-bottom: 0.5pt solid #e5e7eb;
}

tbody tr:nth-child(even) {
    background: #f8fafc;
}

tbody td {
    padding: 5pt 10pt;
    vertical-align: top;
    word-break: break-word;
    overflow-wrap: break-word;
}

/* ── Blockquotes ── */
blockquote {
    border-left: 3pt solid #2563eb;
    background: #eff6ff;
    margin: 8pt 0 10pt 0;
    padding: 8pt 14pt;
    border-radius: 0 4pt 4pt 0;
    font-style: italic;
    color: #1e40af;
}
blockquote p { margin: 0; }

/* ── Horizontal rule ── */
hr {
    border: none;
    border-top: 0.75pt solid #e5e7eb;
    margin: 12pt 0;
}

/* ── Math & images ── */
img {
    max-width: 100%;
    height: auto;
}

/* ── Strong & em ── */
strong { font-weight: 700; color: #111827; }
em     { font-style: italic; color: #374151; }

/* ── Emoji replacements ── */
.emoji-ok   { color: #16a34a; font-weight: 700; }
.emoji-ko   { color: #dc2626; font-weight: 700; }
.emoji-warn { color: #d97706; font-weight: 700; }
.emoji-info { color: #2563eb; font-weight: 700; }

/* ── Page break helpers ── */
table, figure, pre { page-break-inside: avoid; }
"""

print(f"Converting {SOURCE.name} …", flush=True)

html_obj = HTML(string=full_html, base_url=str(ROOT))
css_obj  = CSS(string=CSS_STYLE)

html_obj.write_pdf(str(OUTPUT), stylesheets=[css_obj])

print(f"✓ PDF written → {OUTPUT}")
print(f"  Size: {OUTPUT.stat().st_size / 1024:.0f} KB")

import base64
import io
import re
import warnings
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import markdown
from weasyprint import HTML, CSS

matplotlib.use("Agg")
warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "SEMANTIC_RAG_ENGINE_WHITEPAPER.md"
OUTPUT = ROOT / "SEMANTIC_RAG_ENGINE_WHITEPAPER.pdf"


# ── render a LaTeX formula to an inline SVG data URI ─────────────────────────

def _latex_to_img_tag(formula: str, display: bool) -> str:
    """Render *formula* (LaTeX) with matplotlib mathtext → base64 PNG <img>."""
    # matplotlib mathtext needs $ delimiters
    expr = f"${formula.strip()}$"
    fontsize = 11 if display else 9
    # A4 content width = 210mm - 42mm margins ≈ 168mm = 6.6 in
    MAX_WIDTH_IN = 6.4
    try:
        fig = plt.figure(figsize=(0.01, 0.01))
        fig.patch.set_alpha(0)
        text = fig.text(0, 0, expr, fontsize=fontsize,
                        color="#1f2937",
                        usetex=False)
        # measure natural size
        fig.canvas.draw()
        bbox = text.get_window_extent(renderer=fig.canvas.get_renderer())
        pad = 4
        w_in = (bbox.width  + pad * 2) / fig.dpi
        h_in = (bbox.height + pad * 2) / fig.dpi

        # if inline formula is too wide → promote to display block
        if not display and w_in > MAX_WIDTH_IN * 0.6:
            display = True

        # hard cap: never exceed page width
        if w_in > MAX_WIDTH_IN:
            scale = MAX_WIDTH_IN / w_in
            w_in  = MAX_WIDTH_IN
            h_in  = h_in * scale

        fig.set_size_inches(max(w_in, 0.5), max(h_in, 0.3))
        text.set_position((pad / (fig.get_figwidth()  * fig.dpi),
                           pad / (fig.get_figheight() * fig.dpi)))
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=300,
                    bbox_inches="tight", transparent=True,
                    pad_inches=0.04)
        plt.close(fig)
        b64 = base64.b64encode(buf.getvalue()).decode()
        style = (
            'display:block;margin:10pt auto;max-width:100%;height:auto'
            if display else
            'vertical-align:middle;margin:0 2pt;max-width:100%;height:auto'
        )
        return f'<img src="data:image/png;base64,{b64}" style="{style}" alt="{formula.strip()}">'
    except Exception as exc:
        plt.close("all")
        tag = "p" if display else "code"
        return f'<{tag} style="font-family:monospace;color:#be185d">{formula.strip()}</{tag}>'


def _replace_math(raw: str) -> str:
    """Replace $$...$$ and $...$ blocks with rendered images."""
    # Block math  $$...$$  (possibly multi-line)
    def _block(m):
        return _latex_to_img_tag(m.group(1), display=True)
    raw = re.sub(r"\$\$(.+?)\$\$", _block, raw, flags=re.DOTALL)

    # Inline math  $...$  — skip lone $ signs (prices, etc.)
    def _inline(m):
        content = m.group(1)
        # skip if it's a plain number or currency
        if re.fullmatch(r"[\d,. ]+", content):
            return m.group(0)
        return _latex_to_img_tag(content, display=False)
    raw = re.sub(r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)", _inline, raw)
    return raw


# ── strip YAML front-matter ──────────────────────────────────────────────────
raw = SOURCE.read_text(encoding="utf-8")
if raw.startswith("---"):
    end = raw.index("---", 3)
    raw = raw[end + 3:].lstrip("\n")

# ── render math BEFORE markdown parsing ─────────────────────────────────────
print("Rendering math formulas …", flush=True)
raw = _replace_math(raw)

# ── markdown → HTML body ─────────────────────────────────────────────────────
md = markdown.Markdown(
    extensions=[
        "tables",
        "fenced_code",
        "codehilite",
        "toc",
        "attr_list",
        "def_list",
        "footnotes",
        "admonition",
        "nl2br",
        "sane_lists",
    ],
    extension_configs={
        "codehilite": {"css_class": "highlight", "guess_lang": False},
        "toc": {"permalink": False},
    },
)
body_html = md.convert(raw)

# ── full HTML document ───────────────────────────────────────────────────────
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Semantic RAG Engine — Whitepaper</title>
</head>
<body>
{body}
</body>
</html>"""

full_html = HTML_TEMPLATE.format(body=body_html)

# ── CSS — professional technical document style ──────────────────────────────
CSS_STYLE = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Page setup ── */
@page {
    size: A4;
    margin: 22mm 20mm 25mm 22mm;
    @bottom-center {
        content: counter(page);
        font-family: Inter, sans-serif;
        font-size: 9pt;
        color: #9ca3af;
    }
    @top-right {
        content: "Semantic RAG Engine";
        font-family: Inter, sans-serif;
        font-size: 8pt;
        color: #9ca3af;
    }
}

@page :first {
    @bottom-center { content: none; }
    @top-right     { content: none; }
}

/* ── Base ── */
* { box-sizing: border-box; }

body {
    font-family: Inter, "Segoe UI", Helvetica, Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.65;
    color: #1f2937;
    background: #ffffff;
}

/* ── Cover page trick: first h1 gets cover treatment ── */
body > h1:first-of-type {
    page-break-before: avoid;
    text-align: center;
    font-size: 28pt;
    font-weight: 700;
    color: #111827;
    margin-top: 60mm;
    margin-bottom: 6mm;
    letter-spacing: -0.5pt;
    border: none;
    padding: 0;
}

/* ── Part headings (# Part …) ── */
h1 {
    font-size: 18pt;
    font-weight: 700;
    color: #1e3a5f;
    border-bottom: 2.5pt solid #2563eb;
    padding-bottom: 4pt;
    margin-top: 18pt;
    margin-bottom: 8pt;
    page-break-before: always;
}
h1:first-of-type { page-break-before: avoid; }

/* ── Section headings ── */
h2 {
    font-size: 14pt;
    font-weight: 600;
    color: #1d4ed8;
    border-bottom: 1pt solid #bfdbfe;
    padding-bottom: 3pt;
    margin-top: 16pt;
    margin-bottom: 6pt;
}

h3 {
    font-size: 11.5pt;
    font-weight: 600;
    color: #1e40af;
    margin-top: 12pt;
    margin-bottom: 4pt;
}

h4 {
    font-size: 10.5pt;
    font-weight: 600;
    color: #374151;
    margin-top: 10pt;
    margin-bottom: 3pt;
}

h5, h6 {
    font-size: 10pt;
    font-weight: 500;
    color: #6b7280;
    margin-top: 8pt;
    margin-bottom: 2pt;
}

/* ── Paragraphs & lists ── */
p {
    margin: 0 0 7pt 0;
    orphans: 3;
    widows: 3;
}

ul, ol {
    margin: 4pt 0 8pt 0;
    padding-left: 18pt;
}

li {
    margin-bottom: 3pt;
    line-height: 1.55;
}

li > ul, li > ol {
    margin-top: 2pt;
    margin-bottom: 2pt;
}

/* ── Links ── */
a {
    color: #2563eb;
    text-decoration: none;
}
a:hover { text-decoration: underline; }

/* ── Inline code ── */
code {
    font-family: "JetBrains Mono", "Fira Code", "Courier New", monospace;
    font-size: 9pt;
    background: #f1f5f9;
    color: #be185d;
    padding: 1pt 4pt;
    border-radius: 3pt;
    border: 0.5pt solid #e2e8f0;
}

/* ── Code blocks ── */
pre {
    background: #0f172a;
    border-radius: 6pt;
    padding: 10pt 14pt;
    margin: 8pt 0 12pt 0;
    overflow-x: auto;
    page-break-inside: avoid;
    border-left: 3pt solid #2563eb;
}

pre code {
    font-family: "JetBrains Mono", "Fira Code", monospace;
    font-size: 8.5pt;
    background: transparent;
    color: #e2e8f0;
    padding: 0;
    border: none;
    border-radius: 0;
}

/* ── Syntax highlight (codehilite) ── */
.highlight { background: #0f172a !important; border-radius: 6pt; }
.highlight .k  { color: #93c5fd; font-weight: 500; }
.highlight .s  { color: #86efac; }
.highlight .s1 { color: #86efac; }
.highlight .s2 { color: #86efac; }
.highlight .c1 { color: #6b7280; font-style: italic; }
.highlight .cm { color: #6b7280; font-style: italic; }
.highlight .n  { color: #e2e8f0; }
.highlight .mi { color: #fca5a5; }
.highlight .nb { color: #c4b5fd; }
.highlight .nf { color: #67e8f9; }
.highlight .o  { color: #93c5fd; }
.highlight .p  { color: #e2e8f0; }
.highlight .kn { color: #93c5fd; }
.highlight .nn { color: #fde68a; }

/* ── Tables ── */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 8pt 0 12pt 0;
    font-size: 9.5pt;
    page-break-inside: avoid;
}

thead tr {
    background: #1e3a5f;
    color: #ffffff;
}

thead th {
    padding: 6pt 10pt;
    text-align: left;
    font-weight: 600;
    font-size: 9pt;
    letter-spacing: 0.3pt;
}

tbody tr {
    border-bottom: 0.5pt solid #e5e7eb;
}

tbody tr:nth-child(even) {
    background: #f8fafc;
}

tbody td {
    padding: 5pt 10pt;
    vertical-align: top;
}

/* ── Blockquotes ── */
blockquote {
    border-left: 3pt solid #2563eb;
    background: #eff6ff;
    margin: 8pt 0 10pt 0;
    padding: 8pt 14pt;
    border-radius: 0 4pt 4pt 0;
    font-style: italic;
    color: #1e40af;
}

blockquote p { margin: 0; }

/* ── Horizontal rule ── */
hr {
    border: none;
    border-top: 1pt solid #e5e7eb;
    margin: 14pt 0;
}

/* ── Math (KaTeX fallback — render as monospace) ── */
.math { font-family: "JetBrains Mono", monospace; }

/* ── Math images ── */
img {
    max-width: 100%;
    height: auto;
}

/* ── Strong & em ── */
strong { font-weight: 600; color: #111827; }
em     { font-style: italic; color: #374151; }

/* ── Page break helpers ── */
h1, h2 { page-break-after: avoid; }
table, figure, pre { page-break-inside: avoid; }
"""

print(f"Converting {SOURCE.name} …", flush=True)

html_obj = HTML(string=full_html, base_url=str(ROOT))
css_obj  = CSS(string=CSS_STYLE)

html_obj.write_pdf(str(OUTPUT), stylesheets=[css_obj])

print(f"✓ PDF written → {OUTPUT}")
print(f"  Size: {OUTPUT.stat().st_size / 1024:.0f} KB")
