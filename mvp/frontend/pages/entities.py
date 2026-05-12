"""
Entities / KG explorer page.
"""
from __future__ import annotations
from nicegui import ui
from frontend.state import COLORS, AppState


def build(state: AppState) -> None:
    ui.add_head_html("""
    <style>
      .ent-wrap { margin-left:220px; width:calc(100% - 220px); display:flex; flex-direction:column; min-height:100vh; overflow-x:hidden; }
      .ent-header {
        position:fixed; top:0; left:220px; right:0; height:56px;
        border-bottom:1px solid #222222; background:#111111;
        display:flex; align-items:center; padding:0 28px; z-index:50; gap:10px;
      }
      .ent-content {
        position:fixed; top:56px; bottom:0; left:220px; right:0;
        overflow-y:auto; padding:24px 36px;
      }
      .ent-card {
        background:#171717; border:1px solid #222222; border-radius:14px;
        padding:22px 26px; max-width:800px; margin:0 auto; width:100%;
      }
      .ent-chip {
        background:rgba(26,186,145,0.06); border:1px solid rgba(26,186,145,0.2); border-radius:20px;
        padding:5px 14px; font-size:12.5px; color:#e0e0e0; cursor:pointer;
        transition:all .15s;
      }
      .ent-chip:hover { background:rgba(26,186,145,0.12); border-color:rgba(26,186,145,0.4); }
      .triple-row {
        background:#0f0f0f; border:1px solid #1e1e1e; border-radius:8px;
        padding:9px 14px; font-size:12.5px; color:#d0d0d0;
        font-family: 'JetBrains Mono', 'Fira Code', monospace; margin-bottom:5px;
        transition: border-color .15s;
      }
      .triple-row:hover { border-color: #2a2a2a; }
      .triple-row b { color:#1aba91; }
    </style>
    """)

    with ui.column().classes("ent-wrap"):

        # ── fixed header
        with ui.row().classes("ent-header"):
            ui.html('<div style="width:22px;height:22px;border-radius:6px;background:linear-gradient(135deg,#1aba91,#18a882);display:flex;align-items:center;justify-content:center;"><svg width="13" height="13" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="3" stroke="white" stroke-width="2"/><circle cx="4" cy="6" r="2" stroke="white" stroke-width="2"/><circle cx="20" cy="6" r="2" stroke="white" stroke-width="2"/><circle cx="4" cy="18" r="2" stroke="white" stroke-width="2"/><circle cx="20" cy="18" r="2" stroke="white" stroke-width="2"/><path d="M6 6.5L10 10M14 10l4-3.5M14 14l4 3.5M6 17.5L10 14" stroke="white" stroke-width="1.5" stroke-linecap="round"/></svg></div>')
            ui.label("Entità / Knowledge Graph").style("color:#f0f0f0; font-size:15px; font-weight:600; letter-spacing:-.01em;")

        with ui.column().classes("ent-content"):

            with ui.column().classes("ent-card"):
                with ui.row().classes("items-center gap-3 w-full"):
                    search_input = ui.input("Cerca entità…").props("outlined dense").style(
                        f"background:{COLORS['surface']}; flex:1;"
                    )
                    search_btn = ui.button(icon="search").props("flat").style(
                        f"background:{COLORS['accent']}; color:white; border-radius:8px;"
                        "width:38px; height:38px; min-width:38px;"
                        "box-shadow:0 2px 8px rgba(26,186,145,0.2);"
                    )
                err_lbl = ui.label("").style(
                    f"color:{COLORS['error']}; font-size:12px; margin-top:6px;"
                )

            results_col = ui.column().style("max-width:820px; margin:16px auto 0 auto; width:100%;")
            kg_col      = ui.column().style("max-width:820px; margin:12px auto 0 auto; width:100%;")

            async def load_kg(entity: str):
                kg_col.clear()
                with kg_col:
                    ui.spinner(size="md").style(f"color:{COLORS['accent']};")
                try:
                    data = await state.client.kg_context(entity)
                    kg_col.clear()
                    triples = data.get("triples", [])
                    context = data.get("context", "")
                    with kg_col:
                        with ui.column().classes("ent-card").style("margin-top:0;"):
                            with ui.row().classes("items-center gap-2 mb-3"):
                                ui.icon("account_tree", size="1rem").style(f"color:{COLORS['accent']}")
                                ui.label(f"KG: {entity}").style(
                                    f"color:{COLORS['accent']}; font-size:16px; font-weight:600;"
                                )
                            if triples:
                                for t in triples[:20]:
                                    s = t.get("subject",""); p = t.get("predicate",""); o = t.get("object","")
                                    ui.html(
                                        f'<div class="triple-row">({s}) &mdash; <b>{p}</b> &rarr; ({o})</div>'
                                    )
                            else:
                                ui.label("Nessun triple trovato nel KG.").style(
                                    f"color:{COLORS['text_muted']}; font-size:13px;"
                                )
                            if context:
                                ui.separator().style(f"background:{COLORS['border']}; margin:14px 0 10px;")
                                ui.label("Contesto testuale").style(
                                    "color:#8e8e8e; font-size:11px; text-transform:uppercase; letter-spacing:.06em; font-weight:600;"
                                )
                                ui.label(context[:600]).style(
                                    f"color:{COLORS['text']}; font-size:13px; line-height:1.65; margin-top:6px;"
                                )
                except Exception as e:
                    kg_col.clear()
                    with kg_col:
                        ui.label(f"Errore KG: {e}").style(f"color:{COLORS['error']};")

            async def search_entities():
                q = search_input.value.strip()
                err_lbl.set_text("")
                if not q:
                    return
                results_col.clear()
                kg_col.clear()
                with results_col:
                    ui.spinner(size="md").style(f"color:{COLORS['accent']};")
                try:
                    entities = await state.client.search_entities(q)
                    results_col.clear()
                    if not entities:
                        with results_col:
                            ui.label("Nessuna entità trovata.").style(
                                f"color:{COLORS['text_muted']}; font-size:14px;"
                            )
                        return
                    with results_col:
                        with ui.column().classes("ent-card"):
                            ui.label(f"{len(entities)} entità trovate — clicca per vedere il grafo").style(
                                f"color:{COLORS['text_muted']}; font-size:12px; margin-bottom:14px;"
                            )
                            with ui.row().classes("flex-wrap gap-2"):
                                for ent in entities[:40]:
                                    text  = ent.get("text", str(ent))
                                    etype = ent.get("type", "")
                                    chip_txt = f"{text} [{etype}]" if etype else text
                                    ui.html(
                                        f'<span class="ent-chip">{chip_txt}</span>'
                                    ).on("click", lambda e=text: load_kg(e))
                except Exception as e:
                    results_col.clear()
                    err_lbl.set_text(str(e)[:120])

            search_input.on("keydown.enter", search_entities)
            search_btn.on("click", search_entities)
