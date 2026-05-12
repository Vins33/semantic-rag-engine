"""
Shared sidebar navigation used by all pages.
"""
from __future__ import annotations
from nicegui import ui
from frontend.state import COLORS, ROLE_COLOR, AppState


NAV_ITEMS = [
    ("chat",      "Chat",        "chat"),
    ("dashboard", "Dashboard",   "dashboard"),
    ("ingest",    "Documenti",   "upload_file"),
    ("eval",      "Eval RAGAS",  "science"),
    ("entities",  "Entità / KG", "hub"),
    ("tuner",     "Auto Tuner",  "tune"),
]


def build(state: AppState, current_page: str, navigate, chats: list[dict] | None = None,
          on_new_chat=None, on_select_chat=None, on_delete_chat=None, on_rename_chat=None) -> None:
    with ui.column().style(
        f"width:220px; min-width:220px; height:100vh; background:{COLORS['sidebar']};"
        f"border-right:1px solid {COLORS['border']}; padding:12px 0 8px 0; gap:0;"
        "position:fixed; left:0; top:0; z-index:100; overflow-y:auto; overflow-x:hidden;"
    ):
        # ── logo ─────────────────────────────────────────────────────────
        with ui.row().classes("items-center gap-2").style("padding:4px 16px 16px 16px;"):
            ui.html(f'''
              <div style="width:28px;height:28px;border-radius:8px;
                background:linear-gradient(135deg,{COLORS["accent"]},{COLORS["accent_h"]});
                display:flex;align-items:center;justify-content:center;flex-shrink:0;">
                <span style="color:#fff;font-size:14px;font-weight:700;line-height:1;">R</span>
              </div>
            ''')
            ui.label("RAG Engine").style(
                f"color:{COLORS['text']}; font-size:15px; font-weight:700; letter-spacing:-.02em;"
            )

        # ── new chat button ───────────────────────────────────────────────
        if current_page == "chat" and on_new_chat:
            with ui.row().classes("items-center gap-2 cursor-pointer").style(
                f"background:{COLORS['surface']}; border-radius:8px; padding:8px 12px;"
                f"margin:0 10px 8px 10px; transition:background .15s; border:1px solid {COLORS['border_l']};"
            ).on("click", on_new_chat):
                ui.icon("add", size="0.95rem").style(f"color:{COLORS['accent']}")
                ui.label("Nuova chat").style(
                    f"color:{COLORS['text_sec']}; font-size:13px; font-weight:500;"
                )

        # ── chat list ─────────────────────────────────────────────────────
        if current_page == "chat" and chats is not None:
            with ui.column().style("gap:1px; max-height:260px; overflow-y:auto; margin-bottom:4px; width:100%; padding:0 8px;"):
                for chat in chats:
                    cid = chat["chat_id"]
                    title = chat["title"]
                    is_active = (cid == state.active_chat_id)
                    row_bg = COLORS['surface'] if is_active else "transparent"
                    text_color = COLORS['text'] if is_active else COLORS['text_sec']

                    with ui.row().classes("items-center w-full").style(
                        f"background:{row_bg}; border-radius:6px; padding:5px 8px; cursor:pointer;"
                        "transition:background .12s; position:relative; gap:6px;"
                    ).on("click", lambda c=cid, t=title: on_select_chat(c, t) if on_select_chat else None):
                        ui.icon("chat_bubble_outline", size="0.8rem").style(
                            f"color:{'#1aba91' if is_active else COLORS['text_muted']}; flex-shrink:0;"
                        )
                        ui.label(title[:26] + ("…" if len(title) > 26 else "")).style(
                            f"color:{text_color}; font-size:12.5px; flex:1; overflow:hidden; white-space:nowrap;"
                        )
                        if is_active:
                            with ui.row().style("gap:3px; flex-shrink:0;"):
                                ui.icon("drive_file_rename_outline", size="0.75rem").style(
                                    f"color:{COLORS['text_muted']}; cursor:pointer; transition:color .15s;"
                                ).on("click.stop", lambda c=cid, t=title: on_rename_chat(c, t) if on_rename_chat else None)
                                ui.icon("delete_outline", size="0.75rem").style(
                                    f"color:{COLORS['error']}; opacity:.6; cursor:pointer; transition:opacity .15s;"
                                ).on("click.stop", lambda c=cid: on_delete_chat(c) if on_delete_chat else None)

            ui.element("div").style(
                f"height:1px; background:{COLORS['border']}; margin:6px 12px 6px 12px;"
            )

        # ── nav items ────────────────────────────────────────────────────
        for page_id, label, icon in NAV_ITEMS:
            is_active = (current_page == page_id)
            text_color = COLORS["accent"] if is_active else COLORS["text_sec"]
            bg = f"background:{COLORS['surface2']};" if is_active else ""
            left_accent = f"border-left:2px solid {COLORS['accent']}; padding-left:14px;" if is_active else "border-left:2px solid transparent; padding-left:14px;"

            with ui.row().classes("items-center gap-3 cursor-pointer w-full").style(
                f"{bg}{left_accent} padding-top:8px; padding-bottom:8px; padding-right:12px;"
                "transition:background .12s;"
            ).on("click", lambda p=page_id: navigate(p)):
                ui.icon(icon, size="1rem").style(f"color:{text_color}; flex-shrink:0;")
                ui.label(label).style(
                    f"color:{text_color}; font-size:13.5px; font-weight:{'600' if is_active else '400'};"
                )

        ui.space()

        # ── user badge ───────────────────────────────────────────────────
        with ui.column().style(
            f"border-top:1px solid {COLORS['border']}; padding:10px 14px; margin-top:auto; width:100%;"
        ):
            role_color = ROLE_COLOR.get(state.role, COLORS['text_muted'])
            with ui.row().classes("items-center gap-2"):
                ui.html(f'''
                  <div style="width:30px;height:30px;border-radius:50%;
                    background:{COLORS["surface2"]};border:1px solid {COLORS["border_l"]};
                    display:flex;align-items:center;justify-content:center;flex-shrink:0;">
                    <span style="color:{COLORS["text_sec"]};font-size:12px;font-weight:600;">
                      {(state.username or "?")[0].upper()}
                    </span>
                  </div>
                ''')
                with ui.column().style("gap:1px; overflow:hidden;"):
                    ui.label(state.username or "guest").style(
                        f"color:{COLORS['text']}; font-size:12.5px; font-weight:500; "
                        "white-space:nowrap; overflow:hidden; text-overflow:ellipsis;"
                    )
                    ui.label(state.role or "—").style(
                        f"color:{role_color}; font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.06em;"
                    )

