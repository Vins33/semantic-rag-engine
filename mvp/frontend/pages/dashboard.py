"""
Dashboard page — health status + parsed Prometheus metrics.
"""
from __future__ import annotations
import re
from nicegui import ui
from frontend.state import COLORS, AppState


def _parse_metric(text: str, name: str) -> str:
    """Extract the latest value of a Prometheus metric from raw text."""
    for line in text.splitlines():
        if line.startswith(name) and not line.startswith("#"):
            parts = line.split()
            if parts:
                return parts[-1]
    return "—"


def _parse_histogram_count(text: str, name: str) -> str:
    pattern = rf"^{re.escape(name)}_count\b"
    for line in text.splitlines():
        if re.match(pattern, line):
            return line.split()[-1]
    return "—"


def build(state: AppState) -> None:
    ui.add_head_html("""
    <style>
      .dash-header {
        position:fixed; top:0; left:220px; right:0; height:56px;
        border-bottom:1px solid #222222; background:#111111;
        display:flex; align-items:center; justify-content:space-between;
        padding:0 28px; z-index:50;
      }
      .dash-content {
        position:fixed; top:56px; bottom:0; left:220px; right:0;
        overflow-y:auto; padding:24px 36px;
      }
      .dash-section-title {
        font-size: 10px; font-weight: 700; text-transform: uppercase;
        letter-spacing: .1em; color: #5a5a5a; margin-bottom: 12px; margin-top: 20px;
      }
      .metric-card {
        background: #171717; border: 1px solid #222222; border-radius: 12px;
        padding: 18px 22px; min-width: 150px; flex:1;
        transition: border-color .2s;
        position: relative; overflow: hidden;
      }
      .metric-card::before {
        content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
        background: linear-gradient(90deg, #1aba91, transparent);
        opacity: 0;
        transition: opacity .2s;
      }
      .metric-card:hover { border-color: #2e2e2e; }
      .metric-card:hover::before { opacity: 1; }
      .metric-value { font-size: 26px; font-weight: 700; color: #f0f0f0; margin-top: 6px; letter-spacing: -.02em; }
      .metric-label { font-size: 11px; color: #5a5a5a; font-weight: 500; text-transform: uppercase; letter-spacing: .05em; }
      .status-dot { width:8px; height:8px; border-radius:50%; margin-right:7px; display:inline-block; flex-shrink:0; }
      .status-dot.ok  { background:#1aba91; box-shadow:0 0 6px rgba(26,186,145,.5); }
      .status-dot.err { background:#f87171; box-shadow:0 0 6px rgba(248,113,113,.5); }
      .status-name { font-size:13px; color:#a0a0a0; font-weight:500; }
      .status-val  { font-size:12px; margin-top:4px; }
      .refresh-ghost {
        background: #1a1a1a !important; border: 1px solid #272727 !important;
        border-radius: 8px !important; color: #5a5a5a !important;
        font-size: 12px !important; transition: all .15s !important;
      }
      .refresh-ghost:hover { background: #222222 !important; color: #a0a0a0 !important; border-color: #333 !important; }
    </style>
    """)

    # ── fixed header (create btn here so refresh() can reference it)
    refresh_btn_ref: list = []
    with ui.row().classes("dash-header"):
        with ui.row().classes("items-center gap-2"):
            ui.html('<div style="width:22px;height:22px;border-radius:6px;background:linear-gradient(135deg,#1aba91,#18a882);display:flex;align-items:center;justify-content:center;flex-shrink:0;"><span style="color:#fff;font-size:11px;font-weight:700;">R</span></div>')
            ui.label("Dashboard").style("color:#f0f0f0; font-size:15px; font-weight:600; letter-spacing:-.01em;")
        btn = ui.button("Aggiorna", icon="refresh").props("flat no-caps").classes("refresh-ghost")
        refresh_btn_ref.append(btn)

    # ── scrollable content
    with ui.column().classes("dash-content"):

        # ── health section
        ui.html('<div class="dash-section-title">Servizi</div>')

        with ui.row().classes("gap-3 flex-wrap w-full"):
            health_cards: dict[str, ui.html] = {}
            for svc in ["API", "Ollama", "Embed"]:
                with ui.column().classes("metric-card").style("min-width:150px; flex:1;"):
                    health_cards[svc] = ui.html(
                        f'<div style="display:flex;align-items:center;"><span class="status-dot err"></span><span class="status-name">{svc}</span></div>'
                    )
                    health_cards[svc + "_val"] = ui.label("—").classes("status-val").style(
                        "color:#5a5a5a; font-size:12px;"
                    )

        # ── prometheus metrics
        ui.html('<div class="dash-section-title">Metriche RAG</div>')

        metric_defs = [
            ("rag_query_latency",    "Query Latency (count)", "counter"),
            ("rag_ingest_total",     "Documenti Ingestati",   "gauge"),
            ("rag_cache_hits_total", "Cache Hits",            "gauge"),
            ("rag_confabulation_total", "Confabulazioni",     "gauge"),
            ("rag_token_budget_cuts_total", "Budget Cuts",    "gauge"),
            ("rag_retrieval_count",  "Retrievals (total)",    "counter"),
        ]

        metric_labels: dict[str, ui.label] = {}
        with ui.row().classes("gap-3 flex-wrap w-full"):
            for key, label, kind in metric_defs:
                with ui.column().classes("metric-card"):
                    ui.label(label).classes("metric-label")
                    metric_labels[key] = ui.label("—").classes("metric-value")

        ts_label = ui.label("").style(
            f"color:#3a3a3a; font-size:11px; margin-top:12px;"
        )

        async def refresh():
            from datetime import datetime
            refresh_btn = refresh_btn_ref[0]
            refresh_btn.disable()

            try:
                h = await state.client.health()
                api_ok = h.get("status") == "ok"
                ollama_ok = h.get("ollama") == "ok"
                embed = h.get("embed_model", "—")
                dot_ok = '<span class="status-dot ok"></span>'
                dot_err = '<span class="status-dot err"></span>'
                health_cards["API"].set_content(f'<div style="display:flex;align-items:center;">{dot_ok if api_ok else dot_err}<span class="status-name">API Backend</span></div>')
                health_cards["Ollama"].set_content(f'<div style="display:flex;align-items:center;">{dot_ok if ollama_ok else dot_err}<span class="status-name">Ollama LLM</span></div>')
                health_cards["Embed"].set_content(f'<div style="display:flex;align-items:center;">{dot_ok}<span class="status-name">Embed</span></div>')
                health_cards["API_val"].set_text("online" if api_ok else "offline")
                health_cards["Ollama_val"].set_text("online" if ollama_ok else "offline")
                health_cards["Embed_val"].set_text(embed)
            except Exception as e:
                health_cards["API"].set_content('<div style="display:flex;align-items:center;"><span class="status-dot err"></span><span class="status-name">API Backend</span></div>')
                health_cards["API_val"].set_text(str(e)[:40])

            try:
                raw = await state.client.metrics_raw()
                for key, label, kind in metric_defs:
                    if kind == "counter":
                        val = _parse_histogram_count(raw, key)
                        if val == "—": val = _parse_metric(raw, key + "_total")
                        if val == "—": val = _parse_metric(raw, key)
                    else:
                        val = _parse_metric(raw, key + "_total")
                        if val == "—": val = _parse_metric(raw, key)
                    try:
                        metric_labels[key].set_text(f"{float(val):.0f}")
                    except Exception:
                        metric_labels[key].set_text(val)
            except Exception:
                for key, *_ in metric_defs:
                    metric_labels[key].set_text("err")

            ts_label.set_text(f"Aggiornato: {datetime.now().strftime('%H:%M:%S')}")
            refresh_btn.enable()

        refresh_btn_ref[0].on("click", refresh)
        ui.timer(0.1, refresh, once=True)
        ui.timer(30.0, refresh)
