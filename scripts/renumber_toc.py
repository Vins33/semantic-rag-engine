"""
Renumber whitepaper sections so each Part resets to 1,
with subsections following the N.M pattern.
Also rebuilds the ToC fully expanded with all subsections.
"""
import re, sys

WHITEPAPER = "/home/vins/semantic-rag-engine/SEMANTIC_RAG_ENGINE_WHITEPAPER.md"

# Old global section number → new per-part number
SECTION_MAP = {
    1: 1,   # Part I
    2: 2,   # Part I
    3: 1,   # Part II
    4: 2,   # Part II
    5: 3,   # Part II
    6: 4,   # Part II
    7: 5,   # Part II
    8: 1,   # Part III
    9: 2,   # Part III
    10: 3,  # Part III
    11: 4,  # Part III
    12: 1,  # Part IV
    13: 1,  # Part V
    14: 2,  # Part V
    15: 3,  # Part V
    16: 1,  # Part VI
    17: 2,  # Part VI
    18: 3,  # Part VI
    19: 4,  # Part VI
}

# ── anchor helpers ──────────────────────────────────────────────────────────

def heading_to_anchor(text: str) -> str:
    """Approximate GitHub-flavoured Markdown anchor from heading text.
    Rules: lowercase → remove chars that are not word-chars / spaces / hyphens
           → replace every space with a hyphen (not collapsed).
    """
    text = text.lower()
    text = re.sub(r"[^\w\s\-]", "", text, flags=re.UNICODE)
    text = text.replace(" ", "-")
    text = text.strip("-")
    return text


# ── heading transformations ──────────────────────────────────────────────────

with open(WHITEPAPER, "r", encoding="utf-8") as fh:
    content = fh.read()

# 1. Rename  ### N.M  /  #### N.M  headings  (more specific — do FIRST)
def _sub_heading(m):
    hashes = m.group(1)
    major  = int(m.group(2))
    minor  = m.group(3)
    rest   = m.group(4)
    return f"{hashes} {SECTION_MAP.get(major, major)}.{minor} {rest}"

content = re.sub(
    r"^(#{3,4}) (\d+)\.(\d+) (.*)",
    _sub_heading, content, flags=re.MULTILINE
)

# 2. Rename  ## N.  headings
def _sub_sec(m):
    hashes = m.group(1)
    num    = int(m.group(2))
    rest   = m.group(3)
    return f"{hashes} {SECTION_MAP.get(num, num)}. {rest}"

content = re.sub(
    r"^(#{2}) (\d+)\. (.*)",
    _sub_sec, content, flags=re.MULTILINE
)

# 3. Update  §N.M–N.M  ranges  (handle before individual replacements)
def _sub_range(m):
    maj1 = int(m.group(1)); min1 = m.group(2)
    dash = m.group(3)
    maj2 = int(m.group(4)); min2 = m.group(5)
    return (f"§{SECTION_MAP.get(maj1,maj1)}.{min1}"
            f"{dash}"
            f"{SECTION_MAP.get(maj2,maj2)}.{min2}")

content = re.sub(
    r"§(\d{1,2})\.(\d+)([–—])(\d{1,2})\.(\d+)",
    _sub_range, content
)

# 4. Update individual  §N.M  references  (1-2 digit section, not §1798)
def _sub_ref(m):
    maj = int(m.group(1)); min_ = m.group(2)
    return f"§{SECTION_MAP.get(maj, maj)}.{min_}"

content = re.sub(r"§(\d{1,2})\.(\d+)", _sub_ref, content)

# 5. Update standalone  §N  references  (not followed by digit or dot)
def _sub_plain(m):
    num = int(m.group(1))
    return f"§{SECTION_MAP.get(num, num)}"

content = re.sub(r"§(\d{1,2})(?![\.\d])", _sub_plain, content)


# ── build new ToC from renamed headings ─────────────────────────────────────

SKIP = {
    "SEMANTIC RAG ENGINE",
    "Architecture, Implementation and Research Foundations of a Vertical "
    "Retrieval-Augmented Generation System for PDF Documents",
    "Table of Contents",
    "Technology References",
}

# Special trailing notes for specific sections (keyed by heading text after rename)
NOTES = {
    "3. API Reference":
        " — 8 endpoints including SSE streaming, document CRUD, secure auth",
    "1.4 Automated Pipeline Test Suite":
        " — 233 tests, 5 scenarios + H5 compliance, no external deps",
}

toc_items = []   # (level, text)
in_code_block = False
in_references = False
for line in content.splitlines():
    # Track fenced code blocks (``` or ~~~)
    if re.match(r"^(`{3,}|~{3,})", line):
        in_code_block = not in_code_block
        continue
    if in_code_block:
        continue

    m = re.match(r"^(#{1,4}) (.+)", line)
    if not m:
        continue
    level = len(m.group(1))
    text  = m.group(2).strip()
    if text in SKIP:
        continue

    # Track references section — skip its sub-headings
    if text == "References":
        in_references = True
        toc_items.append((level, text))
        continue
    if in_references:
        continue

    # Only include up to level 3 (Parts, Sections, Subsections)
    if level > 3:
        continue

    toc_items.append((level, text))

def build_toc_line(level: int, text: str) -> str:
    note   = NOTES.get(text, "")
    anchor = heading_to_anchor(text)
    link   = f"[{text}](#{anchor}){note}"
    indent_map = {1: "", 2: "  ", 3: "    ", 4: "      "}
    indent = indent_map.get(level, "        ")
    return f"{indent}- {link}"

toc_lines = ["## Table of Contents", ""]
for level, text in toc_items:
    if text == "References":
        toc_lines.append("- [References](#references)")
        continue
    toc_lines.append(build_toc_line(level, text))

new_toc = "\n".join(toc_lines)

# Replace old ToC block (from ## Table of Contents up to the first ---)
content = re.sub(
    r"## Table of Contents\n.*?(?=\n---\n)",
    new_toc,
    content,
    flags=re.DOTALL,
)

with open(WHITEPAPER, "w", encoding="utf-8") as fh:
    fh.write(content)

print("✓ Renumbering complete.")
