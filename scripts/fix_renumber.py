"""
Corrective renumber pass: assigns section numbers SEQUENTIALLY per Part
(position-based, not value-based — immune to double-application).
Then rebuilds the ToC.

Safe to run multiple times (idempotent after the first correct run).
"""
import re

WHITEPAPER = "/home/vins/semantic-rag-engine/SEMANTIC_RAG_ENGINE_WHITEPAPER.md"

# ── anchor helper ──────────────────────────────────────────────────────────

def heading_to_anchor(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s\-]", "", text, flags=re.UNICODE)
    text = text.replace(" ", "-")
    return text.strip("-")


# ── pass 1: fix heading numbers positionally ───────────────────────────────

with open(WHITEPAPER, "r", encoding="utf-8") as fh:
    lines = fh.readlines()

in_code = False
current_section = 0   # current section counter within a Part

for idx, raw in enumerate(lines):
    line = raw.rstrip("\n")

    # Track fenced code blocks
    if re.match(r"^(`{3,}|~{3,})", line):
        in_code = not in_code
        continue
    if in_code:
        continue

    # Part heading resets counter
    if re.match(r"^# Part ", line):
        current_section = 0
        continue

    # Section heading ## N. Title  →  ## <seq>. Title
    m = re.match(r"^(## )(\d+)\. (.+)", line)
    if m:
        current_section += 1
        correct = f"{m.group(1)}{current_section}. {m.group(3)}\n"
        if lines[idx] != correct:
            lines[idx] = correct
        continue

    # Subsection heading ### N.M Title  →  ### <seq>.M Title
    m = re.match(r"^(#{3,4} )(\d+)(\.[\d]+ .+)", line)
    if m and current_section > 0:
        correct = f"{m.group(1)}{current_section}{m.group(3)}\n"
        if lines[idx] != correct:
            lines[idx] = correct

with open(WHITEPAPER, "w", encoding="utf-8") as fh:
    fh.writelines(lines)

print("✓ Heading numbers corrected positionally.")


# ── pass 2: rebuild ToC ────────────────────────────────────────────────────

with open(WHITEPAPER, "r", encoding="utf-8") as fh:
    content = fh.read()

SKIP = {
    "SEMANTIC RAG ENGINE",
    "Architecture, Implementation and Research Foundations of a Vertical "
    "Retrieval-Augmented Generation System for PDF Documents",
    "Table of Contents",
    "Technology References",
}

NOTES = {
    "3. API Reference":
        " — 8 endpoints including SSE streaming, document CRUD, secure auth",
    "1.4 Automated Pipeline Test Suite":
        " — 233 tests, 5 scenarios + H5 compliance, no external deps",
}

toc_items = []
in_code = False
in_references = False
for line in content.splitlines():
    if re.match(r"^(`{3,}|~{3,})", line):
        in_code = not in_code
        continue
    if in_code:
        continue

    m = re.match(r"^(#{1,3}) (.+)", line)
    if not m:
        continue
    level = len(m.group(1))
    text  = m.group(2).strip()
    if text in SKIP:
        continue
    if text == "References":
        in_references = True
        toc_items.append((level, text))
        continue
    if in_references:
        continue
    if level > 3:
        continue
    toc_items.append((level, text))

def build_toc_line(level: int, text: str) -> str:
    note   = NOTES.get(text, "")
    anchor = heading_to_anchor(text)
    link   = f"[{text}](#{anchor}){note}"
    indent = {1: "", 2: "  ", 3: "    "}.get(level, "      ")
    return f"{indent}- {link}"

toc_lines = ["## Table of Contents", ""]
for level, text in toc_items:
    if text == "References":
        toc_lines.append("- [References](#references)")
        continue
    toc_lines.append(build_toc_line(level, text))

new_toc = "\n".join(toc_lines)
content = re.sub(
    r"## Table of Contents\n.*?(?=\n---\n)",
    new_toc,
    content,
    flags=re.DOTALL,
)

with open(WHITEPAPER, "w", encoding="utf-8") as fh:
    fh.write(content)

print("✓ ToC rebuilt.")
