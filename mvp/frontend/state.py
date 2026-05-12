"""
Shared state and CSS constants for the RAG frontend.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from frontend.api import ApiClient

# ── global shared state (per-user via nicegui storage) ────────────────────
@dataclass
class AppState:
    token: str = ""
    role: str = ""
    username: str = ""
    client: ApiClient = field(default_factory=ApiClient)
    active_chat_id: str = ""
    active_chat_title: str = ""


# ── Midnight dark colour palette ──────────────────────────────────────────
COLORS = {
    "bg":         "#111111",   # main background
    "sidebar":    "#0d0d0d",   # left nav
    "surface":    "#1a1a1a",   # card / input surface
    "surface2":   "#222222",   # hover
    "surface3":   "#2c2c2c",   # active / pressed
    "border":     "#242424",   # default border
    "border_l":   "#333333",   # lighter border for emphasis
    "text":       "#f0f0f0",   # primary text
    "text_sec":   "#a0a0a0",   # secondary text
    "text_muted": "#5a5a5a",   # muted
    "accent":     "#1aba91",   # teal-green (brighter)
    "accent_h":   "#18a882",   # hover
    "accent_dim": "rgba(26,186,145,0.10)",
    "user_bubble":"#1a1a1a",
    "bot_bubble": "#141414",
    "error":      "#f87171",
    "warn":       "#fbbf24",
    "ok":         "#34d399",
}

GLOBAL_CSS = f"""
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
html {{ scroll-behavior: smooth; }}
body, .nicegui-content {{
    background: {COLORS['bg']};
    color: {COLORS['text']};
    font-family: 'Inter', 'ui-sans-serif', system-ui, -apple-system, sans-serif;
    font-size: 15px;
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
}}
::-webkit-scrollbar {{ width: 4px; height: 4px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: {COLORS['border_l']}; border-radius: 4px; }}
::-webkit-scrollbar-thumb:hover {{ background: {COLORS['surface3']}; }}
a {{ color: {COLORS['accent']}; text-decoration: none; transition: opacity .15s; }}
a:hover {{ opacity: .8; }}
.q-btn {{ border-radius: 8px !important; transition: all .15s ease !important; }}
.q-field--outlined .q-field__control {{
    border-color: {COLORS['border_l']} !important;
    border-radius: 8px !important;
    transition: border-color .2s, box-shadow .2s;
}}
.q-field--outlined.q-field--focused .q-field__control {{
    border-color: {COLORS['accent']} !important;
    box-shadow: 0 0 0 2px {COLORS['accent_dim']} !important;
}}
.q-field__label {{ color: {COLORS['text_muted']} !important; }}
.q-field__native, .q-field__input {{ color: {COLORS['text']} !important; }}
/* page wrapper */
.page-wrap {{
    margin-left: 220px;
    width: calc(100% - 220px);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    overflow-x: hidden;
}}
.page-header {{
    border-bottom: 1px solid {COLORS['border']};
    padding: 14px 32px;
    background: {COLORS['bg']};
    display: flex;
    align-items: center;
    gap: 12px;
    flex-shrink: 0;
}}
.page-header h1 {{
    font-size: 17px;
    font-weight: 600;
    color: {COLORS['text']};
    margin: 0;
}}
.page-content {{
    flex: 1;
    padding: 28px 40px;
    overflow-y: auto;
}}
.section-title {{
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .1em;
    color: {COLORS['text_muted']};
    margin-bottom: 12px;
    margin-top: 24px;
}}
"""

# ── role badge colours ─────────────────────────────────────────────────────
ROLE_COLOR = {"reader": "#60a5fa", "writer": "#fbbf24", "admin": "#1aba91"}
