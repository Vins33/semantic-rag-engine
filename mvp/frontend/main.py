"""
RAG Engine Frontend — NiceGUI single-page app.
Run: python frontend/main.py
"""
from __future__ import annotations

from nicegui import app as ng_app, ui

from frontend.state import AppState, COLORS, GLOBAL_CSS
from frontend.pages import login, sidebar
from frontend.pages import chat, dashboard, ingest, eval, entities, tuner


def build_app():

    @ui.page("/")
    def index():
        state = AppState()
        current_page: dict = {"id": "chat"}
        page_container: dict = {}

        ui.add_head_html(f"<style>{GLOBAL_CSS}</style>")
        ui.add_head_html("""
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link href="https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,300;0,14..32,400;0,14..32,500;0,14..32,600;0,14..32,700;1,14..32,400&display=swap" rel="stylesheet">
        <style>
          body, .nicegui-content,
          p, span:not(.material-icons):not(.material-symbols-outlined),
          div:not(.material-icons), label, input, textarea, button {
            font-family: 'Inter', sans-serif;
          }
        </style>
        """)

        # ── root container ────────────────────────────────────────────────
        root = ui.column().style("width:100vw; height:100vh; overflow:hidden; position:relative;")

        # ── initial: show login page ──────────────────────────────────────
        with root:
            login_container = ui.column().style("width:100%; height:100%;")
            app_container = ui.column().style(
                "width:100%; height:100%; display:none; flex-direction:row;"
            )

        # ── login build ───────────────────────────────────────────────────
        with login_container:
            def on_login_success():
                login_container.style("display:none")
                app_container.style("display:flex")
                render_app()

            login.build(state, on_login_success)

        # ── app shell ─────────────────────────────────────────────────────
        def render_app():
            with app_container:
                # sidebar column
                sidebar_col = ui.column().style("width:220px; flex-shrink:0;")

                # content column
                content_col = ui.column().style(
                    "flex:1; height:100vh; overflow:hidden; position:relative;"
                )
                page_container["col"] = content_col

                # chat list cache
                chat_state = {"chats": []}

                async def refresh_chats():
                    try:
                        chat_state["chats"] = await state.client.chat_list()
                    except Exception:
                        chat_state["chats"] = []
                    rebuild_sidebar()

                def rebuild_sidebar():
                    sidebar_col.clear()
                    with sidebar_col:
                        sidebar.build(
                            state, current_page["id"], navigate,
                            chats=chat_state["chats"] if current_page["id"] == "chat" else None,
                            on_new_chat=lambda: ui.timer(0, _new_chat, once=True),
                            on_select_chat=lambda cid, title: ui.timer(0, lambda: _select_chat(cid, title), once=True),
                            on_delete_chat=lambda cid: ui.timer(0, lambda: _delete_chat(cid), once=True),
                            on_rename_chat=lambda cid, title: ui.timer(0, lambda: _rename_chat(cid, title), once=True),
                        )

                async def _new_chat():
                    state.active_chat_id    = ""
                    state.active_chat_title = ""
                    current_page["id"] = "chat"
                    content_col.clear()
                    render_page("chat")
                    rebuild_sidebar()

                async def _select_chat(cid: str, title: str):
                    state.active_chat_id    = cid
                    state.active_chat_title = title
                    current_page["id"] = "chat"
                    content_col.clear()
                    render_page("chat")
                    rebuild_sidebar()

                async def _delete_chat(cid: str):
                    try:
                        await state.client.chat_delete(cid)
                        if state.active_chat_id == cid:
                            state.active_chat_id    = ""
                            state.active_chat_title = ""
                            content_col.clear()
                            render_page("chat")
                        await refresh_chats()
                    except Exception:
                        pass

                async def _rename_chat(cid: str, old_title: str):
                    result = {"title": None}

                    async def do_rename():
                        new_title = inp.value.strip()
                        if new_title and new_title != old_title:
                            try:
                                await state.client.chat_rename(cid, new_title)
                                if state.active_chat_id == cid:
                                    state.active_chat_title = new_title
                                await refresh_chats()
                            except Exception:
                                pass
                        dialog.close()

                    with ui.dialog() as dialog, ui.card().style(
                        f"background:{COLORS['surface']}; border:1px solid {COLORS['border_l']}; border-radius:12px; min-width:320px; padding:24px;"
                    ):
                        ui.label("Rinomina chat").style(f"color:{COLORS['text']}; font-weight:600; font-size:15px; margin-bottom:12px;")
                        inp = ui.input(value=old_title).props("outlined dense").style(
                            f"width:100%; background:{COLORS['bg']}; color:{COLORS['text']};"
                        )
                        with ui.row().classes("justify-end gap-2 mt-3"):
                            ui.button("Annulla", on_click=dialog.close).props("flat no-caps").style(f"color:{COLORS['text_muted']};")
                            ui.button("Salva", on_click=do_rename).props("no-caps").style(
                                f"background:{COLORS['accent']}; color:white; border-radius:8px; padding:0 16px;"
                            )
                    dialog.open()

                def navigate(page_id: str):
                    if page_id == current_page["id"]:
                        return
                    current_page["id"] = page_id
                    rebuild_sidebar()
                    content_col.clear()
                    render_page(page_id)
                    if page_id == "chat":
                        ui.timer(0, refresh_chats, once=True)

                rebuild_sidebar()

                with content_col:
                    render_page(current_page["id"])

                # initial chat list load
                ui.timer(0.1, refresh_chats, once=True)

        def render_page(page_id: str):
            col = page_container.get("col")
            target = col if col else ui.column()
            with target:
                if page_id == "chat":
                    chat.build(state)
                elif page_id == "dashboard":
                    dashboard.build(state)
                elif page_id == "ingest":
                    ingest.build(state)
                elif page_id == "eval":
                    eval.build(state)
                elif page_id == "entities":
                    entities.build(state)
                elif page_id == "tuner":
                    tuner.build(state)


build_app()

ui.run(
    host="0.0.0.0",
    port=8080,
    title="RAG Engine",
    favicon="🤖",
    dark=True,
    reload=False,
    show=False,
    uvicorn_logging_level="info",
    reconnect_timeout=30,
)
