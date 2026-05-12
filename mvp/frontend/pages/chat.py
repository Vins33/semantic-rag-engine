"""
Chat page — persistente, stile ChatGPT con markdown, sources, grounding.
"""
from __future__ import annotations
import asyncio
from nicegui import ui
from frontend.state import COLORS, AppState


def build(state: AppState, sidebar_col=None, rebuild_sidebar=None) -> None:
    ui.add_head_html("""
    <style>
      /* ── fixed chat shell ─────────────────────────────────────── */
      .chat-header {
        position: fixed; top: 0; left: 220px; right: 0; height: 56px;
        border-bottom: 1px solid #222222; background: #111111;
        display: flex; align-items: center; padding: 0 28px;
        z-index: 50; gap: 10px;
      }
      .chat-header-title {
        font-size: 15px; font-weight: 600; color: #f0f0f0; letter-spacing: -.01em;
      }
      .chat-messages-area {
        position: fixed; top: 56px; bottom: 88px;
        left: 220px; right: 0; overflow-y: auto;
        padding-bottom: 12px;
      }
      .chat-input-bar {
        position: fixed; bottom: 0; left: 220px; right: 0; height: 88px;
        background: linear-gradient(to top, #111111 80%, transparent);
        display: flex; align-items: center; justify-content: center;
        padding: 0 24px; z-index: 50;
      }
      .chat-input-inner {
        max-width: 700px; width: 100%;
        display: flex; align-items: flex-end; gap: 8px;
        background: #1a1a1a; border: 1px solid #2e2e2e;
        border-radius: 14px; padding: 8px 8px 8px 16px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        transition: border-color .2s, box-shadow .2s;
      }
      .chat-input-inner:focus-within {
        border-color: rgba(26,186,145,0.4);
        box-shadow: 0 4px 24px rgba(0,0,0,0.4), 0 0 0 1px rgba(26,186,145,0.15);
      }
      /* ── messages ─────────────────────────────────────────────── */
      .msg-row { display:flex; justify-content:center; padding:12px 20px; }
      .msg-row.user  { background:transparent; }
      .msg-row.assistant { background:rgba(255,255,255,0.015); }
      .msg-inner { max-width:720px; width:100%; display:flex; gap:14px; align-items:flex-start; }
      .msg-avatar {
        width:30px; height:30px; border-radius:8px;
        display:flex; align-items:center; justify-content:center;
        flex-shrink:0; font-size:12px; font-weight:700; margin-top:3px;
      }
      .msg-avatar.user { background:#2a2a2a; color:#a0a0a0; border:1px solid #333; }
      .msg-avatar.bot  {
        background:linear-gradient(135deg,#1aba91,#18a882); color:#fff;
        box-shadow: 0 2px 8px rgba(26,186,145,0.25);
      }
      .msg-body { flex:1; padding-top:2px; line-height:1.75; color:#e8e8e8; font-size:15px; }
      .msg-body p { margin-bottom:10px; }
      .msg-body h1,.msg-body h2,.msg-body h3 { color:#f5f5f5; margin:16px 0 6px; font-weight:600; }
      .msg-body h1 { font-size:1.25em; } .msg-body h2 { font-size:1.1em; } .msg-body h3 { font-size:1em; }
      .msg-body ul,.msg-body ol { padding-left:1.4em; margin-bottom:10px; }
      .msg-body li { margin-bottom:3px; }
      .msg-body code { background:#1e1e1e; border:1px solid #2e2e2e; border-radius:5px; padding:1px 6px; font-size:13px; color:#a8d8b8; }
      .msg-body pre  { background:#0f0f0f; border:1px solid #242424; border-radius:10px; padding:16px 18px; overflow-x:auto; margin:12px 0; }
      .msg-body pre code { background:transparent; border:none; padding:0; color:#c8e6c9; }
      .msg-body strong { color:#f5f5f5; }
      .msg-body blockquote { border-left:3px solid #1aba91; padding-left:14px; margin:10px 0; color:#a0a0a0; }
      /* ── sources + meta ────────────────────────────────────────── */
      .sources-bar { font-size:12px; margin-top:12px; display:flex; flex-wrap:wrap; gap:5px; align-items:center; }
      .source-chip { background:#181818; border:1px solid #272727; border-radius:20px; padding:3px 10px; font-size:11px; color:#888; transition:all .15s; cursor:default; }
      .source-chip:hover { border-color:rgba(26,186,145,0.4); color:#bbb; }
      .meta-row { font-size:11px; margin-top:7px; display:flex; gap:6px; flex-wrap:wrap; align-items:center; }
      .meta-badge { border-radius:12px; padding:2px 8px; font-size:10.5px; font-weight:600; letter-spacing:.02em; }
      .meta-badge.green  { background:rgba(26,186,145,0.12); color:#1aba91; }
      .meta-badge.yellow { background:rgba(251,191,36,0.12); color:#fbbf24; }
      .meta-badge.red    { background:rgba(248,113,113,0.12); color:#f87171; }
      .meta-badge.blue   { background:rgba(96,165,250,0.12); color:#60a5fa; }
      /* ── send button ────────────────────────────────────────────── */
      .send-btn {
        background: #1aba91 !important; border-radius: 9px !important;
        width: 38px; height: 38px; min-width: 38px !important;
        transition: background .15s, box-shadow .15s !important;
        box-shadow: 0 2px 8px rgba(26,186,145,0.2) !important;
        flex-shrink: 0;
      }
      .send-btn:hover { background:#18a882 !important; box-shadow:0 3px 12px rgba(26,186,145,0.35) !important; }
      /* textarea inside input-inner: no border, transparent */
      .chat-input-inner .q-field--outlined .q-field__control { border:none !important; box-shadow:none !important; background:transparent !important; }
      .chat-input-inner .q-field__native { font-size:14.5px; line-height:1.6; }
      /* ── thinking dots ──────────────────────────────────────────── */
      .thinking-dot { display:inline-block; width:6px; height:6px; border-radius:50%; background:#1aba91; animation:blink 1.4s infinite; margin:0 2px; }
      .thinking-dot:nth-child(2) { animation-delay:.25s; }
      .thinking-dot:nth-child(3) { animation-delay:.5s; }
      @keyframes blink { 0%,80%,100%{opacity:.1} 40%{opacity:1} }
    </style>
    """)

    messages: list[dict] = []
    thinking = {"active": False}

    # ── fixed header ─────────────────────────────────────────────────────
    with ui.row().classes("chat-header"):
        ui.html(f'<div style="width:22px;height:22px;border-radius:6px;background:linear-gradient(135deg,#1aba91,#18a882);display:flex;align-items:center;justify-content:center;flex-shrink:0;"><span style="color:#fff;font-size:11px;font-weight:700;">R</span></div>')
        chat_title_label = ui.label(state.active_chat_title or "Nuova chat").classes("chat-header-title")

    # ── scrollable messages area ──────────────────────────────────────────
    with ui.column().classes("chat-messages-area"):
        messages_col = ui.column().style("width:100%; gap:0;")

    # ── fixed input bar ───────────────────────────────────────────────────
    with ui.row().classes("chat-input-bar"):
        with ui.row().classes("chat-input-inner"):
            textarea = ui.textarea(placeholder="Scrivi un messaggio…").props(
                "outlined autogrow no-error-icon"
            ).style(
                "background:transparent; flex:1; font-size:14.5px;"
                f"color:{COLORS['text']};"
            )
            send_btn = ui.button(icon="send").classes("send-btn").props("flat")

        def _render_meta(meta: dict):
            sources   = meta.get("sources") or []
            grounding = meta.get("grounding") or {}
            confab    = meta.get("confabulation") or {}
            ctrl      = meta.get("controller") or {}
            cache_hit = meta.get("cache_hit", False)
            if sources:
                with ui.row().classes("sources-bar"):
                    ui.label("Fonti:").style("color:#555; font-size:11px;")
                    for s in sources[:6]:
                        fname = s.get("filename", "")
                        page  = s.get("page", "")
                        chip  = fname + (f" p.{page}" if page else "")
                        ui.html(f'<span class="source-chip">{chip}</span>')
            badges = []
            g_score = grounding.get("score")
            if g_score is not None:
                lvl = "green" if g_score >= 0.6 else ("yellow" if g_score >= 0.3 else "red")
                badges.append(f'<span class="meta-badge {lvl}">⚓ grounding {g_score:.2f}</span>')
            if confab.get("has_confabulation"):
                badges.append('<span class="meta-badge red">⚠ confab</span>')
            if ctrl.get("iterations", 0) > 0:
                badges.append(f'<span class="meta-badge blue">🔄 {ctrl["iterations"]} iters</span>')
            if cache_hit:
                badges.append('<span class="meta-badge green">⚡ cache</span>')
            model = meta.get("model", "")
            if model and model not in ("intent_gate",):
                badges.append(f'<span class="meta-badge blue" style="opacity:.55">{model}</span>')
            if badges:
                ui.html('<div class="meta-row">' + "".join(badges) + '</div>')

        def render_msg(role: str, content: str, meta: dict | None = None):
            cls         = "user" if role == "user" else "assistant"
            avatar_char = state.username[0].upper() if role == "user" else "R"
            avatar_cls  = "user" if role == "user" else "bot"
            with messages_col:
                with ui.row().classes(f"msg-row {cls}"):
                    with ui.row().classes("msg-inner"):
                        ui.html(f'<div class="msg-avatar {avatar_cls}">{avatar_char}</div>')
                        with ui.column().style("flex:1; gap:0;"):
                            ui.markdown(content).classes("msg-body")
                            if meta and role == "assistant":
                                _render_meta(meta)

        def render_thinking():
            with messages_col:
                with ui.row().classes("msg-row assistant"):
                    with ui.row().classes("msg-inner"):
                        ui.html('<div class="msg-avatar bot">R</div>')
                        ui.html(
                            '<div class="msg-body" style="padding-top:10px;">'
                            '<span class="thinking-dot"></span>'
                            '<span class="thinking-dot"></span>'
                            '<span class="thinking-dot"></span>'
                            '</div>'
                        )
            ui.run_javascript('document.querySelector(".chat-messages-area").scrollTop = 999999')

        async def load_history():
            if not state.active_chat_id:
                return
            try:
                history = await state.client.chat_messages(state.active_chat_id)
                messages_col.clear()
                messages.clear()
                for m in history:
                    messages.append(m)
                    render_msg(m["role"], m["content"], m.get("meta") or {})
                ui.run_javascript('document.querySelector(".chat-messages-area").scrollTop = 999999')
            except Exception:
                pass

        async def send_message():
            question = textarea.value.strip()
            if not question or thinking["active"]:
                return
            textarea.set_value("")
            thinking["active"] = True
            send_btn.disable()

            # auto-create chat if needed
            if not state.active_chat_id:
                try:
                    title = question[:40] + ("…" if len(question) > 40 else "")
                    chat_info = await state.client.chat_create(title)
                    state.active_chat_id    = chat_info["chat_id"]
                    state.active_chat_title = chat_info["title"]
                    chat_title_label.set_text(state.active_chat_title)
                    if rebuild_sidebar:
                        rebuild_sidebar()
                except Exception:
                    pass

            messages.append({"role": "user", "content": question})
            render_msg("user", question)
            if state.active_chat_id:
                asyncio.create_task(state.client.chat_append(state.active_chat_id, "user", question))
            render_thinking()
            ui.run_javascript('document.querySelector(".chat-messages-area").scrollTop = 999999')

            try:
                result = await state.client.query(question)
                if messages_col.default_slot.children:
                    messages_col.default_slot.children[-1].delete()
                answer = result.get("answer", "*(nessuna risposta)*")
                meta   = {k: result.get(k) for k in ("sources","grounding","confabulation","controller","cache_hit","model")}
                messages.append({"role": "assistant", "content": answer, "meta": meta})
                render_msg("assistant", answer, meta=meta)
                if state.active_chat_id:
                    asyncio.create_task(state.client.chat_append(state.active_chat_id, "assistant", answer, meta))
            except Exception as e:
                if messages_col.default_slot.children:
                    messages_col.default_slot.children[-1].delete()
                render_msg("assistant", f"❌ Errore: {e}")
            finally:
                thinking["active"] = False
                send_btn.enable()
                ui.run_javascript('document.querySelector(".chat-messages-area").scrollTop = 999999')

    send_btn.on("click", send_message)
    textarea.on("keydown.ctrl.enter", send_message)

    ui.timer(0.05, load_history, once=True)
