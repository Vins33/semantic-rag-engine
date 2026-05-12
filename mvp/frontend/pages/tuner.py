"""
AutoTuner page — view active params and history.
"""
from __future__ import annotations
from nicegui import ui
from frontend.state import COLORS, AppState


def build(state: AppState) -> None:
    ui.add_head_html("""
    <style>
      .tuner-header {
        position:fixed; top:0; left:220px; right:0; height:56px;
        border-bottom:1px solid #222222; background:#111111;
        display:flex; align-items:center; justify-content:space-between;
        padding:0 28px; z-index:50;
      }
      .tuner-content {
        position:fixed; top:56px; bottom:0; left:220px; right:0;
        overflow-y:auto; padding:24px 36px;
      }
      .param-card {
        background:#171717; border:1px solid #222222; border-radius:12px;
        padding:18px 22px; flex:1; min-width:150px;
        transition: border-color .2s; position:relative; overflow:hidden;
      }
      .param-card::before {
        content:''; position:absolute; top:0; left:0; right:0; height:2px;
        background:linear-gradient(90deg,#1aba91,transparent); opacity:.6;
      }
      .param-card:hover { border-color: #2e2e2e; }
      .param-value { font-size:24px; font-weight:700; color:#f0f0f0; letter-spacing:-.02em; }
      .param-label { font-size:10px; color:#5a5a5a; margin-top:2px; font-weight:600; text-transform:uppercase; letter-spacing:.06em; }
      .history-row {
        background:#141414; border:1px solid #1e1e1e; border-radius:8px;
        padding:11px 16px; font-size:12.5px; color:#d0d0d0;
        transition: border-color .15s;
      }
      .history-row:hover { border-color: #2a2a2a; }
      .dash-section-title {
        font-size:10px; font-weight:700; text-transform:uppercase;
        letter-spacing:.1em; color:#5a5a5a; margin-bottom:12px; margin-top:20px;
      }
      .refresh-ghost {
        background: #1a1a1a !important; border: 1px solid #272727 !important;
        border-radius: 8px !important; color: #5a5a5a !important;
        font-size: 12px !important; transition: all .15s !important;
      }
      .refresh-ghost:hover { background: #222 !important; color: #a0a0a0 !important; }
    </style>
    """)

    # ── fixed header
    with ui.row().classes("tuner-header"):
        with ui.row().classes("items-center gap-2"):
            ui.html('<div style="width:22px;height:22px;border-radius:6px;background:linear-gradient(135deg,#1aba91,#18a882);display:flex;align-items:center;justify-content:center;"><svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M12 20V10M18 20V4M6 20v-4" stroke="white" stroke-width="2.5" stroke-linecap="round"/></svg></div>')
            ui.label("Auto Tuner").style("color:#f0f0f0; font-size:15px; font-weight:600; letter-spacing:-.01em;")
        refresh_btn = ui.button("Aggiorna", icon="refresh").props("flat no-caps").classes("refresh-ghost")

    # ── scrollable content
    with ui.column().classes("tuner-content"):

        ui.html('<div class="dash-section-title">Parametri attivi (UCB1)</div>')
        params_row = ui.row().classes("gap-4 flex-wrap w-full")
        history_col = ui.column().style("width:100%; gap:8px; margin-top:24px;")
        err_lbl = ui.label("").style(f"color:{COLORS['error']}; font-size:12px;")

        async def refresh():
            params_row.clear()
            history_col.clear()
            err_lbl.set_text("")
            try:
                data = await state.client.tuner_params()
                active = data.get("active_params", {})
                history = data.get("history", {})

                with params_row:
                    param_labels = {
                        "top_k": "Top K",
                        "rerank_threshold": "Rerank Threshold",
                        "token_budget": "Token Budget",
                        "controller_iters": "Controller Iters",
                    }
                    for key, label in param_labels.items():
                        val = active.get(key, "—")
                        with ui.column().classes("param-card"):
                            ui.label(label).classes("param-label")
                            ui.label(str(val)).classes("param-value")

                with history_col:
                    ui.html(
                        '<div style="font-size:13px;color:#8e8e8e;font-weight:600;'
                        'text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px;">'
                        'Storico osservazioni</div>'
                    )
                    total = history.get("total_observations", 0)
                    best = history.get("best_params", {})
                    ui.label(f"Osservazioni totali: {total}").style(
                        f"color:{COLORS['text_muted']}; font-size:13px; margin-bottom:8px;"
                    )
                    if best:
                        ui.label(f"Best params: {best}").style(
                            f"color:{COLORS['accent']}; font-size:13px;"
                        )

            except Exception as e:
                err_lbl.set_text(str(e)[:100])

        refresh_btn.on("click", refresh)
        ui.timer(0.1, refresh, once=True)
