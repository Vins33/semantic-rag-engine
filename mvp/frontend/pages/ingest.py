"""
Ingest page — drag & drop upload PDF/Markdown.
"""
from __future__ import annotations
from nicegui import ui, events
from frontend.state import COLORS, AppState


def build(state: AppState) -> None:
    ui.add_head_html("""
    <style>
      .ingest-wrap { margin-left:220px; width:calc(100% - 220px); display:flex; flex-direction:column; min-height:100vh; overflow-x:hidden; }
      .ingest-header {
        position:fixed; top:0; left:220px; right:0; height:56px;
        border-bottom:1px solid #222222; background:#111111;
        display:flex; align-items:center; padding:0 28px; z-index:50; gap:10px;
      }
      .ingest-content {
        position:fixed; top:56px; bottom:0; left:220px; right:0;
        overflow-y:auto; padding:24px 36px;
      }
      .ingest-card {
        background: #171717; border:1px solid #222222; border-radius:12px;
        padding: 14px 18px; max-width:800px; margin:0 auto 8px auto;
        display:flex; align-items:center; gap:12px;
        transition: border-color .2s;
      }
      .ingest-card:hover { border-color: #2e2e2e; }
      .ingest-meta { font-size:12px; color:#5a5a5a; margin-top:3px; }
      /* Quasar q-uploader overrides */
      .q-uploader {
        background:#141414 !important; border:2px dashed #252525 !important;
        border-radius:14px !important; box-shadow:none !important;
        max-width:800px; width:100%;
        transition: border-color .2s, background .2s;
      }
      .q-uploader:hover, .q-uploader--dnd {
        border-color:#1aba91 !important; background:rgba(26,186,145,.04) !important;
      }
      .q-uploader__header {
        background:transparent !important;
        border-bottom:1px solid #222222;
        padding:18px 22px;
      }
      .q-uploader__header-content { color:#f0f0f0 !important; font-size:14px; gap:12px; }
      .q-uploader__title { font-size:14px; color:#f0f0f0 !important; }
      .q-uploader__subtitle { font-size:12px; color:#5a5a5a !important; }
      .q-uploader__list { background:transparent !important; padding:8px 12px; }
      .q-uploader__file { background:#1a1a1a !important; border:1px solid #242424 !important; border-radius:8px !important; margin:4px 0 !important; }
      .q-uploader__file-header { color:#f0f0f0 !important; }
      .q-uploader__file-status { color:#1aba91 !important; }
      .q-uploader__file--errored .q-uploader__file-status { color:#f87171 !important; }
    </style>
    """)

    with ui.column().classes("ingest-wrap"):

        # ── fixed header
        with ui.row().classes("ingest-header"):
            ui.html('<div style="width:22px;height:22px;border-radius:6px;background:linear-gradient(135deg,#1aba91,#18a882);display:flex;align-items:center;justify-content:center;"><svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg></div>')
            ui.label("Documenti").style("color:#f0f0f0; font-size:15px; font-weight:600; letter-spacing:-.01em;")

        with ui.column().classes("ingest-content"):

            results_col = ui.column().style("max-width:820px; margin:0 auto; width:100%;")

            async def handle_upload(e: events.UploadEventArguments):
                filename = e.name
                content  = e.content.read()
                with results_col:
                    with ui.row().classes("ingest-card"):
                        spinner = ui.spinner(size="sm").style("color:#10a37f;")
                        with ui.column().style("gap:0; flex:1;"):
                            name_lbl = ui.label(filename).style(
                                f"color:{COLORS['text']}; font-size:14px; font-weight:500;"
                            )
                            meta_lbl = ui.label("Caricamento…").classes("ingest-meta")
                        status_slot = ui.element("div")
                try:
                    result = await state.client.ingest(filename, content)
                    spinner.delete()
                    with status_slot:
                        ui.icon("check_circle").style("color:#1aba91; font-size:20px;")
                    pages  = result.get("pages", 0)
                    chunks = result.get("chunks_created", 0)
                    doc_id = result.get("doc_id", "")
                    meta_lbl.set_text(
                        f"{pages} pag · {chunks} chunk · {doc_id[:8]}…"
                    )
                except Exception as ex:
                    spinner.delete()
                    with status_slot:
                        ui.icon("error").style("color:#f87171; font-size:20px;")
                    meta_lbl.set_text(str(ex)[:80])
                    meta_lbl.style("color:#f87171;")

            # ── upload widget
            ui.upload(
                label="Trascina PDF o Markdown qui  —  o clicca per selezionare",
                multiple=True,
                on_upload=handle_upload,
                auto_upload=True,
            ).props('accept=".pdf,.md,.txt" color="teal" text-color="grey-5"').style("width:100%;")

            ui.label("Formati supportati: PDF · Markdown (.md) · Testo (.txt)").style(
                f"color:{COLORS['text_muted']}; font-size:12px; margin-top:10px;"
            )
