"""
Login page — JWT role selector, stile Midnight.
"""
from __future__ import annotations
from nicegui import ui
from frontend.state import COLORS, ROLE_COLOR, AppState


def build(state: AppState, on_success) -> None:
    ui.add_head_html("""
    <style>
      .login-wrap {
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #111111;
        background-image: radial-gradient(ellipse at 50% 0%, rgba(26,186,145,0.07) 0%, transparent 60%);
      }
      .login-card {
        background: #1a1a1a;
        border: 1px solid #272727;
        border-radius: 16px;
        padding: 40px 44px;
        width: 380px;
        box-shadow: 0 20px 60px rgba(0,0,0,0.6), 0 0 0 1px rgba(26,186,145,0.05);
      }
      .login-logo {
        width: 44px; height: 44px; border-radius: 12px;
        background: linear-gradient(135deg, #1aba91, #18a882);
        display: flex; align-items: center; justify-content: center;
        margin: 0 auto 16px auto;
        box-shadow: 0 4px 16px rgba(26,186,145,0.3);
      }
      .login-title {
        font-size: 22px; font-weight: 700; color: #f0f0f0;
        text-align: center; margin-bottom: 4px; letter-spacing: -.02em;
      }
      .login-sub {
        font-size: 13px; color: #5a5a5a;
        text-align: center; margin-bottom: 28px;
      }
      .login-input-wrap { margin-bottom: 16px; }
      .login-btn {
        background: #1aba91 !important;
        color: white !important;
        font-weight: 600 !important;
        border-radius: 9px !important;
        width: 100%; height: 42px;
        font-size: 14px !important;
        letter-spacing: .01em;
        transition: background .15s, box-shadow .15s !important;
        box-shadow: 0 2px 12px rgba(26,186,145,0.25) !important;
      }
      .login-btn:hover {
        background: #18a882 !important;
        box-shadow: 0 4px 20px rgba(26,186,145,0.4) !important;
      }
      .role-label {
        font-size: 11px; font-weight: 700; text-transform: uppercase;
        letter-spacing: .08em; color: #5a5a5a; margin-bottom: 8px;
      }
    </style>
    """)

    with ui.column().classes("login-wrap"):
        with ui.element("div").classes("login-card"):
            # logo
            ui.html('<div class="login-logo"><svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></div>')
            ui.html('<div class="login-title">RAG Engine</div>')
            ui.html('<div class="login-sub">Assistente semantico su documenti</div>')

            with ui.column().classes("login-input-wrap"):
                username_input = ui.input(
                    placeholder="Username",
                ).props('outlined dense').style(
                    f"background:{COLORS['surface']}; color:{COLORS['text']};"
                    "border-radius:8px; width:100%;"
                )

            # role selector
            selected_role = {"value": "reader"}

            ui.html('<div class="role-label">Ruolo</div>')

            def make_role_btn(label: str, role: str, color: str):
                btn = ui.button(label).style(
                    f"background:{color}18; color:{color}; border:1px solid {color}40;"
                    "border-radius:20px; padding:3px 14px; font-size:12px; font-weight:600;"
                    "transition:all .15s;"
                ).on("click", lambda r=role: select_role(r))
                return btn

            role_buttons: dict = {}
            with ui.row().classes("gap-2 mb-4"):
                for role, color in ROLE_COLOR.items():
                    role_buttons[role] = make_role_btn(role.capitalize(), role, color)

            def select_role(r: str):
                selected_role["value"] = r
                role_label.set_text(f"Ruolo selezionato: {r}")

            role_label = ui.label("Ruolo selezionato: reader").style(
                f"color:{COLORS['text_muted']}; font-size:11.5px; margin-bottom:18px; display:block;"
            )

            error_label = ui.label("").style(
                f"color:{COLORS['error']}; font-size:12px; text-align:center; width:100%;"
                "margin-bottom:8px; min-height:16px; display:block;"
            )

            async def do_login():
                error_label.set_text("")
                name = username_input.value.strip()
                if not name:
                    error_label.set_text("Inserisci un username")
                    return
                try:
                    await state.client.login(sub=name, role=selected_role["value"])
                    state.token = state.client.token
                    state.role = selected_role["value"]
                    state.username = name
                    on_success()
                except Exception as e:
                    error_label.set_text(f"Errore login: {e}")

            ui.button("Accedi", on_click=do_login).classes("login-btn").props("no-caps")

