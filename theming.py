# theming.py
import streamlit as st

THEMES = {
    "Classic Light": {
        "primary": "#0ea5e9", "bg": "#ffffff", "bg2": "#f1f5f9", "text": "#0f172a"
    },
    "Slate Dark": {
        "primary": "#22d3ee", "bg": "#0b1220", "bg2": "#111827", "text": "#e5e7eb"
    },
    "Ocean": {
        "primary": "#0284c7", "bg": "#f8fbff", "bg2": "#e6f1ff", "text": "#0b2038"
    },
    "Emerald": {
        "primary": "#10b981", "bg": "#ffffff", "bg2": "#ecfdf5", "text": "#052e21"
    },
    "Crimson": {
        "primary": "#ef4444", "bg": "#ffffff", "bg2": "#fff1f2", "text": "#111827"
    },
    "Midnight Indigo": {
        "primary": "#6366f1", "bg": "#0f1226", "bg2": "#141836", "text": "#e2e8f0"
    },
    "Graphite": {
        "primary": "#fbbf24", "bg": "#0b0b0c", "bg2": "#171717", "text": "#e5e5e5"
    },
}

def apply_theme(name: str):
    t = THEMES.get(name, THEMES["Classic Light"])
    css = f"""
    <style>
      :root {{
        --primary: {t['primary']};
        --bg: {t['bg']};
        --bg2: {t['bg2']};
        --text: {t['text']};
      }}
      /* app surfaces */
      div[data-testid="stAppViewContainer"] {{
        background: var(--bg) !important; color: var(--text) !important;
      }}
      section[data-testid="stSidebar"] > div:first-child {{
        background: var(--bg2) !important; color: var(--text) !important;
      }}
      /* radio, select, text, etc. */
      .stRadio, .stSelectbox, .stTextInput, .stNumberInput, label, p, h1, h2, h3, h4 {{
        color: var(--text) !important;
      }}
      /* buttons */
      .stButton > button {{
        background: var(--primary) !important; border-color: var(--primary) !important;
        color: #fff !important;
      }}
      .stButton > button:hover {{ filter: brightness(0.95); }}
      /* tables/dataframes */
      .stDataFrame, .stTable {{ color: var(--text) !important; }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
