"""
Eval RAGAS page.
"""
from __future__ import annotations
from nicegui import ui
from frontend.state import COLORS, AppState


def _score_color(v: float) -> str:
    if v >= 0.8: return "#10a37f"
    if v >= 0.5: return "#f59e0b"
    return "#ef4444"


def build(state: AppState) -> None:
    ui.add_head_html("""
    <style>
      .eval-header {
        position:fixed; top:0; left:220px; right:0; height:56px;
        border-bottom:1px solid #222222; background:#111111;
        display:flex; align-items:center; padding:0 28px; z-index:50; gap:10px;
      }
      .eval-content {
        position:fixed; top:56px; bottom:0; left:220px; right:0;
        overflow-y:auto; padding:24px 36px;
      }
      .eval-card {
        background:#171717; border:1px solid #222222; border-radius:14px;
        padding:24px 28px; max-width:940px; margin:0 auto; width:100%;
      }
      .eval-result-card {
        background:#141414; border:1px solid #222222; border-radius:14px;
        padding:24px 28px; max-width:940px; margin:20px auto 0 auto; width:100%;
      }
      .score-block {
        background:#1a1a1a; border:1px solid #242424; border-radius:10px;
        padding:16px 18px; flex:1; text-align:center; min-width:130px;
        transition: border-color .2s;
      }
      .score-block:hover { border-color: #2e2e2e; }
      .score-val { font-size:30px; font-weight:700; letter-spacing:-.02em; }
      .score-lbl { font-size:10px; color:#5a5a5a; margin-top:3px; font-weight:600; text-transform:uppercase; letter-spacing:.06em; }
      .reason-text { font-size:12px; color:#6e6e6e; margin-top:6px; line-height:1.55; }
    </style>
    """)

    with ui.column().style("width:100%; height:100%;"):
        with ui.row().classes("eval-header"):
            ui.html('<div style="width:22px;height:22px;border-radius:6px;background:linear-gradient(135deg,#1aba91,#18a882);display:flex;align-items:center;justify-content:center;"><svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></div>')
            ui.label("Eval RAGAS").style("color:#f0f0f0; font-size:15px; font-weight:600; letter-spacing:-.01em;")

        with ui.column().classes("eval-content"):
            with ui.column().classes("eval-card").style("gap:14px;"):
                q_input = ui.input("Query").props("outlined dense").style(
                    f"background:{COLORS['surface']}; width:100%;"
                )
                with ui.row().classes("gap-3 w-full"):
                    a_input = ui.textarea("Answer").props("outlined autogrow").style(
                        f"background:{COLORS['surface']}; flex:1;"
                    )
                    c_input = ui.textarea("Context (testo recuperato)").props("outlined autogrow").style(
                        f"background:{COLORS['surface']}; flex:1;"
                    )
                with ui.row().classes("items-center justify-between w-full"):
                    run_btn = ui.button("Esegui valutazione", icon="science").props("no-caps").style(
                        f"background:{COLORS['accent']}; color:white; border-radius:8px;"
                        "font-weight:600; height:40px; padding:0 18px; font-size:13px;"
                        "box-shadow:0 2px 12px rgba(26,186,145,0.2);"
                    )
                    err_lbl = ui.label("").style(f"color:{COLORS['error']}; font-size:12px;")

            result_area = ui.column().style("max-width:960px; margin:0 auto; width:100%;")

        async def run_eval():
            q = q_input.value.strip()
            a = a_input.value.strip()
            c = c_input.value.strip()
            err_lbl.set_text("")
            if not (q and a and c):
                err_lbl.set_text("Compila tutti i campi.")
                return
            run_btn.disable()
            result_area.clear()
            with result_area:
                spinner = ui.spinner(size="lg").style(f"color:{COLORS['accent']}; margin:24px auto;")
            try:
                res = await state.client.evaluate(q, a, c)
                result_area.clear()
                with result_area:
                    with ui.column().classes("eval-result-card"):
                        ui.label("Risultati").style(
                            f"color:{COLORS['text']}; font-size:18px; font-weight:600; margin-bottom:16px;"
                        )

                        def score_val(field):
                            v = res.get(field, {})
                            if isinstance(v, dict): return v.get("score", 0.0)
                            return float(v) if v else 0.0

                        def score_reason(field):
                            v = res.get(field, {})
                            if isinstance(v, dict): return v.get("reason", "")
                            return ""

                        overall = res.get("overall", 0.0)

                        with ui.row().classes("gap-4 flex-wrap"):
                            for field, label in [
                                ("faithfulness", "Faithfulness"),
                                ("answer_relevancy", "Relevancy"),
                                ("context_recall", "Recall"),
                            ]:
                                sv = score_val(field)
                                with ui.column().classes("score-block"):
                                    ui.label(f"{sv:.2f}" if isinstance(sv, float) else "—").classes(
                                        "score-val"
                                    ).style(f"color:{_score_color(sv if isinstance(sv, float) else 0)};")
                                    ui.label(label).classes("score-lbl")
                                    reason = score_reason(field)
                                    if reason:
                                        ui.label(reason[:100]).classes("reason-text")

                        # overall bar
                        ov = float(overall) if overall else 0.0
                        with ui.row().classes("items-center gap-4 mt-4"):
                            ui.label("Overall").style(f"color:{COLORS['text_muted']}; font-size:13px; min-width:60px;")
                            ui.linear_progress(value=ov).props(
                                f"color={'positive' if ov>=0.8 else 'warning' if ov>=0.5 else 'negative'}"
                            ).style("flex:1; height:8px; border-radius:4px;")
                            ui.label(f"{ov:.2f}").style(
                                f"color:{_score_color(ov)}; font-weight:700; font-size:16px;"
                            )

            except Exception as e:
                result_area.clear()
                err_lbl.set_text(f"Errore: {e}")
            finally:
                run_btn.enable()

        run_btn.on("click", run_eval)
