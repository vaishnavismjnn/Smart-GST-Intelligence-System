# --- file: styles.py ---
# ═══════════════════════════════════════════════════════════════
# CENTRAL STYLESHEET — All CSS for the entire app lives here.
# Import and call load_css() once at the top of app.py.
# No other file should contain <style> blocks.
# ═══════════════════════════════════════════════════════════════

import streamlit as st

# ── Design Tokens ──────────────────────────────────────────────
# Light-blue background palette. All other elements are tuned
# to complement this warm, airy background.
TOKENS = {
    # Backgrounds
    "bg":           "#E8F4FD",   # main page bg — soft sky blue
    "bg2":          "#D6EBF8",   # slightly deeper blue
    "sidebar_bg":   "#C8E3F5",   # sidebar — medium blue
    # Cards — white-tinted glass on top of blue bg
    "card":         "rgba(255,255,255,0.75)",
    "card2":        "rgba(255,255,255,0.55)",
    "card_border":  "rgba(0,168,150,0.22)",
    "card_hover":   "rgba(0,212,170,0.08)",
    # Accent — teal (unchanged, works perfectly on light bg)
    "accent":       "#00A896",
    "accent2":      "#007A6E",
    "accent_glow":  "rgba(0,168,150,0.2)",
    "accent_light": "#00D4AA",
    # Gold highlight
    "gold":         "#D4A017",
    "warn":         "#C8860A",
    # Error
    "err":          "#D63E58",
    "err_glow":     "rgba(214,62,88,0.15)",
    # Typography — dark on light bg
    "text":         "#0F2137",   # near-black navy — primary text
    "text2":        "#2D5873",   # medium blue-grey — secondary text
    "muted":        "#5A8FA8",   # muted blue-grey
    "border":       "rgba(0,100,130,0.1)",
}

def load_css():
    """Inject the full app stylesheet. Call once from app.py."""
    t = TOKENS
    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&family=DM+Mono:wght@400;500&display=swap');

/* ── CSS Variables ─────────────────────────────────────────── */
:root {{
    --bg:           {t['bg']};
    --bg2:          {t['bg2']};
    --card:         {t['card']};
    --card2:        {t['card2']};
    --card-border:  {t['card_border']};
    --card-hover:   {t['card_hover']};
    --accent:       {t['accent']};
    --accent2:      {t['accent2']};
    --accent-glow:  {t['accent_glow']};
    --accent-light: {t['accent_light']};
    --gold:         {t['gold']};
    --warn:         {t['warn']};
    --err:          {t['err']};
    --err-glow:     {t['err_glow']};
    --text:         {t['text']};
    --text2:        {t['text2']};
    --muted:        {t['muted']};
    --border:       {t['border']};
    --sidebar-bg:   {t['sidebar_bg']};
}}

/* ── Reset & Base ──────────────────────────────────────────── */
*, *::before, *::after {{ box-sizing: border-box; }}
html, body, [class*="css"] {{ font-family: 'DM Sans', sans-serif !important; }}
#MainMenu, footer{{ visibility: hidden; }}
.block-container {{ padding: 1.75rem 2.5rem 3rem 2.5rem !important; max-width: 100% !important; }}

/* ── App Background — animated light-blue mesh ─────────────── */
.stApp {{
    background-color: var(--bg) !important;
    background-image:
        radial-gradient(ellipse 80% 50% at 20% 0%,  rgba(0,168,150,0.08) 0%, transparent 60%),
        radial-gradient(ellipse 60% 40% at 80% 100%, rgba(0,120,180,0.06) 0%, transparent 50%),
        radial-gradient(ellipse 40% 30% at 50% 50%,  rgba(212,160,23,0.03) 0%, transparent 50%);
    color: var(--text) !important;
}}
.stApp::before {{
    content: '';
    position: fixed; inset: 0;
    background-image:
        linear-gradient(rgba(0,168,150,0.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0,168,150,0.04) 1px, transparent 1px);
    background-size: 60px 60px;
    pointer-events: none; z-index: 0;
    animation: grid-drift 30s linear infinite;
}}
@keyframes grid-drift {{
    0%   {{ background-position: 0 0; }}
    100% {{ background-position: 60px 60px; }}
}}

/* ── Sidebar ───────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
    background: var(--sidebar-bg) !important;
    border-right: 1px solid var(--card-border) !important;
    backdrop-filter: blur(20px);
}}
[data-testid="stSidebar"]::before {{
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 300px;
    background: radial-gradient(ellipse at 50% 0%, rgba(0,168,150,0.1) 0%, transparent 70%);
    pointer-events: none;
}}
[data-testid="stSidebar"] * {{ color: var(--text) !important; }}
[data-testid="stSidebarContent"] {{ padding: 0 !important; }}

/* ── Buttons ───────────────────────────────────────────────── */
.stButton > button {{
    background: linear-gradient(135deg, var(--accent) 0%, var(--accent2) 100%) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 10px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    letter-spacing: 0.02em !important;
    padding: 0.6rem 1.5rem !important;
    transition: all 0.25s cubic-bezier(0.4,0,0.2,1) !important;
    box-shadow: 0 4px 15px rgba(0,168,150,0.25) !important;
    position: relative !important;
    overflow: hidden !important;
}}
.stButton > button::after {{
    content: '';
    position: absolute;
    top: -50%; left: -60%;
    width: 40%; height: 200%;
    background: rgba(255,255,255,0.2);
    transform: skewX(-20deg);
    transition: left 0.4s ease !important;
}}
.stButton > button:hover::after {{ left: 120%; }}
.stButton > button:hover {{
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 25px rgba(0,168,150,0.4) !important;
}}
.stButton > button:active {{ transform: translateY(0) scale(0.98) !important; }}

/* ── Inputs ────────────────────────────────────────────────── */
.stTextInput > div > div > input,
.stSelectbox > div > div,
.stNumberInput > div > div > input {{
    background: rgba(255,255,255,0.85) !important;
    border: 1px solid var(--card-border) !important;
    border-radius: 10px !important;
    color: var(--text) !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.88rem !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
}}
.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus {{
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--accent-glow) !important;
}}
.stTextInput label, .stSelectbox label, .stNumberInput label {{
    color: var(--text2) !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.04em !important;
    text-transform: uppercase !important;
}}

/* ── File Uploader ─────────────────────────────────────────── */
[data-testid="stFileUploader"] {{
    background: rgba(255,255,255,0.7) !important;
    border: 2px dashed var(--card-border) !important;
    border-radius: 16px !important;
    transition: border-color 0.3s, background 0.3s, box-shadow 0.3s !important;
}}
[data-testid="stFileUploader"]:hover {{
    border-color: var(--accent) !important;
    background: rgba(255,255,255,0.9) !important;
    box-shadow: 0 0 30px rgba(0,168,150,0.1) !important;
}}

/* ── Tabs ──────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {{
    background: rgba(255,255,255,0.5) !important;
    border-radius: 12px !important;
    padding: 4px !important;
    border: 1px solid var(--card-border) !important;
    gap: 4px !important;
}}
.stTabs [data-baseweb="tab"] {{
    color: var(--text2) !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    font-size: 0.85rem !important;
    transition: all 0.2s !important;
}}
.stTabs [aria-selected="true"] {{
    background: linear-gradient(135deg, var(--accent), var(--accent2)) !important;
    color: #FFFFFF !important;
    font-weight: 600 !important;
}}

/* ── Expander ──────────────────────────────────────────────── */
.streamlit-expanderHeader {{
    background: rgba(255,255,255,0.75) !important;
    border: 1px solid var(--card-border) !important;
    border-radius: 10px !important;
    color: var(--text) !important;
    font-weight: 500 !important;
    transition: border-color 0.2s, background 0.2s !important;
}}
.streamlit-expanderHeader:hover {{
    border-color: rgba(0,168,150,0.35) !important;
    background: rgba(255,255,255,0.9) !important;
}}
.streamlit-expanderContent {{
    background: rgba(255,255,255,0.5) !important;
    border: 1px solid var(--card-border) !important;
    border-top: none !important;
    border-radius: 0 0 10px 10px !important;
}}

/* ── Progress Bar ──────────────────────────────────────────── */
.stProgress > div > div > div {{
    background: linear-gradient(90deg, var(--accent), var(--gold)) !important;
    border-radius: 10px !important;
}}
.stProgress > div > div {{
    background: rgba(0,168,150,0.12) !important;
    border-radius: 10px !important;
}}

/* ── Scrollbar ─────────────────────────────────────────────── */
::-webkit-scrollbar {{ width: 5px; height: 5px; }}
::-webkit-scrollbar-track {{ background: var(--bg); }}
::-webkit-scrollbar-thumb {{ background: rgba(0,168,150,0.35); border-radius: 10px; }}
::-webkit-scrollbar-thumb:hover {{ background: var(--accent); }}

/* ── Alerts & Spinner ──────────────────────────────────────── */
.stSpinner > div {{ border-top-color: var(--accent) !important; }}
.stAlert {{ border-radius: 12px !important; border: none !important; }}

/* ── Download Button ───────────────────────────────────────── */
.stDownloadButton > button {{
    background: transparent !important;
    color: var(--accent) !important;
    border: 1px solid var(--card-border) !important;
    border-radius: 10px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
    transition: all 0.2s !important;
}}
.stDownloadButton > button:hover {{
    background: rgba(0,168,150,0.08) !important;
    border-color: var(--accent) !important;
    box-shadow: 0 0 15px var(--accent-glow) !important;
    transform: translateY(-1px) !important;
}}

/* ══════════════════════════════════════════════════════════════
   REUSABLE COMPONENT CLASSES
══════════════════════════════════════════════════════════════ */

/* Page header */
.page-header {{
    margin-bottom: 2rem;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid var(--card-border);
    animation: fade-up 0.5s ease both;
}}
.page-title {{
    font-family: 'DM Sans', sans-serif;
    font-size: 1.75rem;
    font-weight: 700;
    color: var(--text);
    letter-spacing: -0.03em;
    margin: 0;
}}
.page-sub {{ color: var(--text2); font-size: 0.85rem; margin-top: 4px; }}

/* KPI Card */
.kpi-card {{
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 16px;
    padding: 1.5rem 1.75rem;
    position: relative;
    overflow: hidden;
    transition: transform 0.25s cubic-bezier(0.4,0,0.2,1), box-shadow 0.25s, border-color 0.25s;
    backdrop-filter: blur(12px);
    box-shadow: 0 2px 12px rgba(0,100,130,0.08);
    cursor: default;
}}
.kpi-card::before {{
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, var(--accent), var(--gold), transparent);
    opacity: 0.8;
}}
.kpi-card::after {{
    content: '';
    position: absolute; top: -50%; right: -20%;
    width: 120px; height: 120px;
    background: radial-gradient(circle, rgba(0,168,150,0.07) 0%, transparent 70%);
    border-radius: 50%;
}}
.kpi-card:hover {{
    transform: translateY(-4px) scale(1.01);
    box-shadow: 0 16px 48px rgba(0,168,150,0.15);
    border-color: rgba(0,168,150,0.35);
}}
.kpi-icon {{ font-size: 1.4rem; margin-bottom: 0.75rem; display: block; }}
.kpi-label {{
    color: var(--text2); font-size: 0.72rem; text-transform: uppercase;
    letter-spacing: 0.1em; font-weight: 600; margin-bottom: 0.5rem;
}}
.kpi-value {{
    color: var(--accent); font-size: 2rem; font-weight: 700;
    line-height: 1; letter-spacing: -0.03em;
}}
.kpi-sub {{ color: var(--muted); font-size: 0.72rem; margin-top: 0.4rem; }}

/* Glass Card */
.glass-card {{
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 16px;
    padding: 1.5rem;
    backdrop-filter: blur(12px);
    box-shadow: 0 2px 16px rgba(0,100,130,0.07);
    transition: border-color 0.2s, box-shadow 0.2s;
    animation: fade-up 0.45s ease both;
}}
.glass-card:hover {{
    border-color: rgba(0,168,150,0.3);
    box-shadow: 0 4px 24px rgba(0,168,150,0.1);
}}

/* Section Title */
.section-title {{
    font-size: 0.72rem; font-weight: 700; color: var(--accent);
    text-transform: uppercase; letter-spacing: 0.12em; margin-bottom: 1rem;
    display: flex; align-items: center; gap: 0.5rem;
}}
.section-title::after {{
    content: ''; flex: 1; height: 1px;
    background: linear-gradient(90deg, var(--card-border), transparent);
}}

/* Detail Rows */
.detail-row {{
    display: flex; justify-content: space-between; align-items: center;
    padding: 0.65rem 0; border-bottom: 1px solid var(--border);
    transition: background 0.15s;
}}
.detail-row:last-child {{ border-bottom: none; }}
.detail-row:hover {{
    background: rgba(0,168,150,0.04);
    border-radius: 6px; padding-left: 4px;
}}
.detail-label {{ color: var(--text2); font-size: 0.8rem; }}
.detail-value {{ color: var(--text); font-weight: 500; font-size: 0.88rem; }}

/* Badges */
.badge-valid {{
    background: rgba(0,168,150,0.12); color: var(--accent);
    border: 1px solid rgba(0,168,150,0.3); border-radius: 20px;
    padding: 3px 12px; font-size: 0.72rem; font-weight: 700;
    letter-spacing: 0.04em; text-transform: uppercase;
}}
.badge-invalid {{
    background: rgba(214,62,88,0.1); color: var(--err);
    border: 1px solid rgba(214,62,88,0.3); border-radius: 20px;
    padding: 3px 12px; font-size: 0.72rem; font-weight: 700;
    letter-spacing: 0.04em; text-transform: uppercase;
}}
.badge-warn {{
    background: rgba(200,134,10,0.1); color: var(--warn);
    border: 1px solid rgba(200,134,10,0.3); border-radius: 20px;
    padding: 3px 12px; font-size: 0.72rem; font-weight: 700;
    letter-spacing: 0.04em; text-transform: uppercase;
}}

/* Activity Items */
.activity-item {{
    background: var(--card); border: 1px solid var(--card-border);
    border-radius: 12px; padding: 1rem 1.25rem; margin-bottom: 0.6rem;
    transition: border-color 0.2s, transform 0.2s, box-shadow 0.2s;
    cursor: default;
    box-shadow: 0 1px 6px rgba(0,100,130,0.06);
}}
.activity-item:hover {{
    border-color: rgba(0,168,150,0.35);
    transform: translateX(5px);
    box-shadow: -4px 0 20px rgba(0,168,150,0.08);
}}

/* Mono font */
.mono {{ font-family: 'DM Mono', monospace; }}

/* Table */
.tbl-header {{
    display: grid; padding: 0.6rem 1rem;
    background: rgba(0,168,150,0.08);
    border-radius: 10px 10px 0 0;
    border: 1px solid var(--card-border);
    font-size: 0.68rem; color: var(--accent);
    text-transform: uppercase; letter-spacing: 0.1em; font-weight: 700;
}}
.tbl-row {{
    display: grid; padding: 0.75rem 1rem;
    background: var(--card);
    border: 1px solid var(--card-border); border-top: none;
    font-size: 0.82rem; align-items: center;
    transition: background 0.15s, transform 0.15s;
}}
.tbl-row:hover {{ background: rgba(0,168,150,0.05); transform: translateX(2px); }}
.tbl-row:last-child {{ border-radius: 0 0 10px 10px; }}

/* ══════════════════════════════════════════════════════════════
   ANIMATIONS
══════════════════════════════════════════════════════════════ */
@keyframes fade-up {{
    from {{ opacity: 0; transform: translateY(14px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
}}
@keyframes fade-in {{
    from {{ opacity: 0; }}
    to   {{ opacity: 1; }}
}}
@keyframes glow-pulse {{
    0%, 100% {{ box-shadow: 0 0 20px rgba(0,168,150,0.15); }}
    50%       {{ box-shadow: 0 0 40px rgba(0,168,150,0.35); }}
}}
@keyframes shimmer {{
    0%   {{ background-position: -200% center; }}
    100% {{ background-position: 200% center; }}
}}
@keyframes float {{
    0%, 100% {{ transform: translateY(0px); }}
    50%       {{ transform: translateY(-8px); }}
}}
@keyframes spin-slow {{
    from {{ transform: rotate(0deg); }}
    to   {{ transform: rotate(360deg); }}
}}
@keyframes border-glow {{
    0%, 100% {{ border-color: var(--card-border); }}
    50%       {{ border-color: rgba(0,168,150,0.4); }}
}}
@keyframes pulse-ring {{
    0%   {{ box-shadow: 0 0 0 0 rgba(0,168,150,0.5); }}
    70%  {{ box-shadow: 0 0 0 8px rgba(0,168,150,0); }}
    100% {{ box-shadow: 0 0 0 0 rgba(0,168,150,0); }}
}}
@keyframes slide-in-right {{
    from {{ transform: translateX(120%); opacity: 0; }}
    to   {{ transform: translateX(0);    opacity: 1; }}
}}
@keyframes ticker {{
    0%   {{ transform: translateX(100%); }}
    100% {{ transform: translateX(-100%); }}
}}

.fade-up    {{ animation: fade-up  0.45s ease both; }}
.fade-up-d1 {{ animation: fade-up  0.45s ease 0.1s both; }}
.fade-up-d2 {{ animation: fade-up  0.45s ease 0.2s both; }}
.fade-up-d3 {{ animation: fade-up  0.45s ease 0.3s both; }}
.float-anim {{ animation: float    4s ease-in-out infinite; }}
.glow-anim  {{ animation: glow-pulse 3s ease-in-out infinite; }}
.border-anim {{ animation: border-glow 3s ease-in-out infinite; }}

.shimmer-text {{
    background: linear-gradient(90deg, var(--accent) 0%, var(--gold) 50%, var(--accent) 100%);
    background-size: 200% auto;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: shimmer 3s linear infinite;
}}

.pulse-dot {{
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--accent);
    display: inline-block;
    animation: pulse-ring 2s ease-out infinite;
}}

.toast-success {{
    position: fixed; top: 1.5rem; right: 1.5rem; z-index: 9999;
    background: rgba(255,255,255,0.96);
    border: 1px solid rgba(0,168,150,0.4);
    border-left: 4px solid var(--accent);
    border-radius: 12px; padding: 1rem 1.5rem;
    box-shadow: 0 8px 32px rgba(0,100,130,0.15), 0 0 20px rgba(0,168,150,0.08);
    animation: slide-in-right 0.4s cubic-bezier(0.4,0,0.2,1) both;
    backdrop-filter: blur(20px);
    min-width: 280px;
}}

.step-indicator {{
    display: flex; gap: 0.5rem; align-items: center; margin-bottom: 1rem;
}}
.step-dot {{
    width: 28px; height: 28px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.72rem; font-weight: 700;
    border: 2px solid var(--card-border);
    color: var(--muted);
    transition: all 0.3s;
}}
.step-dot.active {{
    background: var(--accent); color: #fff;
    border-color: var(--accent);
    box-shadow: 0 0 12px rgba(0,168,150,0.4);
}}
.step-dot.done {{
    background: rgba(0,168,150,0.15);
    border-color: rgba(0,168,150,0.4);
    color: var(--accent);
}}
.step-line {{
    flex: 1; height: 1px; background: var(--border);
}}
.step-line.done {{ background: rgba(0,168,150,0.4); }}

/* ══════════════════════════════════════════════════════════════
   SIDEBAR COMPONENT CLASSES
══════════════════════════════════════════════════════════════ */
.sb-brand {{
    display: flex; align-items: center; gap: 0.75rem;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid rgba(0,168,150,0.15);
    margin-bottom: 1.5rem;
}}
.sb-brand-icon {{
    width: 40px; height: 40px;
    background: linear-gradient(135deg, #00A896, #007A6E);
    border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.1rem;
    box-shadow: 0 4px 15px rgba(0,168,150,0.3);
    flex-shrink: 0;
}}
.sb-brand-name {{
    font-size: 1rem; font-weight: 700;
    color: var(--text); letter-spacing: -0.02em;
}}
.sb-brand-tag {{ font-size: 0.65rem; color: var(--text2); letter-spacing: 0.05em; }}
.sb-user {{
    display: flex; align-items: center; gap: 0.75rem;
    background: rgba(0,168,150,0.08);
    border: 1px solid rgba(0,168,150,0.15);
    border-radius: 12px; padding: 0.75rem; margin-bottom: 1.5rem;
}}
.sb-avatar {{
    width: 36px; height: 36px; border-radius: 50%;
    background: linear-gradient(135deg, #00A896, #007A6E);
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; color: #fff; font-size: 0.82rem; flex-shrink: 0;
}}
.sb-username {{ font-weight: 600; font-size: 0.82rem; color: var(--text); }}
.sb-usertag  {{ font-size: 0.65rem; color: var(--text2); }}
.sb-online {{
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--accent);
    box-shadow: 0 0 6px rgba(0,168,150,0.7);
    display: inline-block; margin-right: 4px;
}}
.sb-nav-label {{
    font-size: 0.63rem; font-weight: 700;
    color: var(--muted); text-transform: uppercase;
    letter-spacing: 0.12em; margin-bottom: 0.5rem; padding-left: 0.25rem;
}}
.sb-nav-item {{
    display: flex; align-items: center; gap: 0.75rem;
    padding: 0.6rem 0.75rem; border-radius: 10px;
    margin-bottom: 2px; cursor: pointer;
    transition: all 0.15s ease;
    border: 1px solid transparent;
}}
.sb-nav-item:hover {{
    background: rgba(0,168,150,0.08);
    border-color: rgba(0,168,150,0.15);
}}
.sb-nav-item.active {{
    background: rgba(0,168,150,0.12);
    border-color: rgba(0,168,150,0.25);
}}
.sb-nav-icon {{ font-size: 1rem; width: 20px; text-align: center; }}
.sb-nav-text {{ font-size: 0.85rem; font-weight: 500; color: var(--text); }}
.sb-nav-text.active {{ color: var(--accent); font-weight: 600; }}
.sb-nav-sub  {{ font-size: 0.65rem; color: var(--muted); }}
.sb-version  {{
    text-align: center; font-size: 0.65rem; color: var(--muted);
    margin-top: 0.75rem; letter-spacing: 0.05em;
}}

/* ══════════════════════════════════════════════════════════════
   LOGIN PAGE CLASSES
══════════════════════════════════════════════════════════════ */
.auth-card {{
    background: rgba(255,255,255,0.88);
    border: 1px solid rgba(0,168,150,0.2);
    border-radius: 20px; padding: 2.5rem;
    backdrop-filter: blur(24px);
    box-shadow: 0 24px 80px rgba(0,100,130,0.12), 0 0 60px rgba(0,168,150,0.04);
    animation: fade-up 0.5s ease both;
}}
.demo-chip {{
    display: inline-flex; align-items: center; gap: 0.4rem;
    background: rgba(0,168,150,0.08); border: 1px solid rgba(0,168,150,0.2);
    border-radius: 20px; padding: 4px 14px;
    font-size: 0.73rem; color: var(--accent);
    font-family: 'DM Mono', monospace;
}}
.feature-pill {{
    display: inline-flex; align-items: center; gap: 0.35rem;
    background: rgba(0,100,130,0.06); border: 1px solid rgba(0,100,130,0.12);
    border-radius: 20px; padding: 4px 12px;
    font-size: 0.73rem; color: var(--text2); margin: 0.2rem;
}}
.security-strip {{
    display: flex; justify-content: center; gap: 1.5rem;
    margin-top: 1.25rem; padding-top: 1rem;
    border-top: 1px solid rgba(0,100,130,0.1);
}}
.security-item {{
    display: flex; align-items: center; gap: 0.35rem;
    font-size: 0.68rem; color: var(--muted);
}}

/* ══════════════════════════════════════════════════════════════
   ITC FORECASTER PAGE CLASSES
══════════════════════════════════════════════════════════════ */
.itc-gauge-wrap {{
    text-align: center; padding: 1.5rem;
}}
.itc-amount {{
    font-size: 2.2rem; font-weight: 700; color: var(--accent);
    font-family: 'DM Mono', monospace; letter-spacing: -0.03em;
    margin: 0.5rem 0 0.25rem 0;
}}
.itc-label {{
    font-size: 0.72rem; color: var(--text2); text-transform: uppercase;
    letter-spacing: 0.1em; font-weight: 600;
}}
.win-toast {{
    background: rgba(255,255,255,0.95);
    border: 1px solid rgba(0,168,150,0.35);
    border-left: 4px solid var(--accent);
    border-radius: 12px; padding: 0.85rem 1.25rem;
    margin-bottom: 0.5rem;
    animation: slide-in-right 0.4s ease both;
    box-shadow: 0 4px 16px rgba(0,168,150,0.12);
    display: flex; align-items: center; gap: 0.75rem;
}}

/* ══════════════════════════════════════════════════════════════
   FORENSIC TABLE PAGE CLASSES
══════════════════════════════════════════════════════════════ */
.forensic-row-invalid {{
    animation: pulse-red 2s ease-in-out infinite;
}}
@keyframes pulse-red {{
    0%, 100% {{ background: rgba(214,62,88,0.04); }}
    50%       {{ background: rgba(214,62,88,0.09); }}
}}
.duplicate-modal {{
    background: rgba(255,255,255,0.96);
    border: 1px solid rgba(214,62,88,0.3);
    border-left: 4px solid var(--err);
    border-radius: 14px; padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
    box-shadow: 0 8px 32px rgba(214,62,88,0.12);
    animation: fade-up 0.35s ease both;
}}
.fp-chip {{
    display: inline-block;
    background: rgba(0,168,150,0.08);
    border: 1px solid rgba(0,168,150,0.2);
    border-radius: 6px; padding: 2px 8px;
    font-size: 0.68rem; font-family: 'DM Mono', monospace;
    color: var(--accent); margin-top: 4px;
}}
</style>
""", unsafe_allow_html=True)