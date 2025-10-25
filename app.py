# app.py
from theming import apply_theme, THEMES
from db import get_supabase  # ⬅️ use Supabase client, not SQLAlchemy
import streamlit as st
import importlib
from urllib.parse import urlencode, quote
from auth import login_form, register_form, validate_token, logout_now

# --- make sure project root, modules/, and pages/ are importable ---
import sys
from pathlib import Path

# (Optional) Old SQL sanity probe removed since we now use Supabase client
# If you want a quick ping, you can later call get_supabase().table("users").select("id").limit(1).execute()

ROOT = Path(__file__).resolve().parent
for p in (ROOT, ROOT / "modules", ROOT / "pages"):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

st.set_page_config(
    page_title="Valve Design Suite",
    layout="wide",
    menu_items={"Get Help": None, "Report a bug": None, "About": "Valve Design Suite"}
)

# ========= one-time bootstrap (avoid sidebar flicker/overhead) =========
if "boot_done" not in st.session_state:
    # Supabase client check (soft, no network call required)
    try:
        _sb = get_supabase()
        # Optional: tiny no-op to verify object exists
        print("Supabase client ready.")
    except Exception as e:
        # Do not crash the app during bootstrap
        print("DB check (soft) failed:", e)

    # Theme default once
    st.session_state.theme = st.session_state.get("theme", "Classic Light")
    st.session_state.boot_done = True

# ========= utilities =========
def qp_get_all() -> dict:
    """Query params as {key: single string} across Streamlit versions."""
    try:
        qp = st.query_params  # mapping-like on newer Streamlit
        items = qp.items() if hasattr(qp, "items") else []
    except Exception:
        qp = st.experimental_get_query_params()  # legacy
        items = (qp or {}).items()
    out = {}
    for k, v in items:
        out[k] = v[0] if isinstance(v, list) else v
    return out

def set_query_params_silent(**params):
    """Set query params with minimal layout change (still causes rerun)."""
    try:
        st.query_params.clear()
        for k, v in params.items():
            st.query_params[k] = v
    except Exception:
        try:
            st.experimental_set_query_params(**params)
        except Exception:
            pass

# ========= CSS (glassy links) =========
st.markdown("""
<style>
#MainMenu, footer { visibility: hidden; }

/* Hide Streamlit built-in multipage nav (various builds) */
section[data-testid="stSidebarNav"],
div[data-testid="stSidebarNav"],
nav[aria-label="Page navigation"] { display:none !important; }

/* ---- Glassy link-style nav ---- */
:root {
  --brand-blue: #2563eb;
  --text: #0f172a;
  --muted: #475569;
  --border: rgba(15, 23, 42, 0.08);
  --glass: rgba(255,255,255,.35);
  --glass-hover: rgba(255,255,255,.55);
  --glass-active: rgba(37, 99, 235, .18);
}

.sidebar-profile {
  padding: .5rem;
  margin-bottom: .35rem;
  border-bottom: 1px solid #e5e7eb;
  background: #ffffff;
  border-radius: .5rem;
}
.sidebar-profile .name { font-weight:700; }
.sidebar-profile .role { font-size:.9rem; color: var(--muted); }

.nav-title {
  margin: .15rem 0 .35rem 0;
  font-weight: 700;
  font-size: 1rem;
  color: var(--text);
}

.nav-links { margin: 0; padding: 0; }
.nav-links a.nav {
  display: block;
  margin: 0;
  padding: .4rem .6rem;
  font-size: 14px;
  line-height: 1.2;
  border-radius: .6rem;
  color: var(--text);
  text-decoration: none;
  border: 1px solid var(--border);
  background: var(--glass);
  backdrop-filter: blur(6px);
  transition: background .15s ease, border-color .15s ease, transform .04s ease;
  cursor: pointer;
}
.nav-links a.nav + a.nav { margin-top: .35rem; }
.nav-links a.nav:hover { background: var(--glass-hover); }
.nav-links a.nav:active { transform: translateY(0.5px); }
.nav-links a.nav.active {
  background: var(--glass-active);
  border-color: rgba(37, 99, 235, .25);
  color: var(--text);
}

/* Keep sidebar from visually shifting (same height always) */
section[data-testid="stSidebar"] > div:first-child {
  min-height: 100vh;
}

.sidebar-auth-footer {
  position: sticky; bottom: 0; left: 0; right: 0;
  padding: .5rem .25rem .75rem .25rem;
  background: linear-gradient(180deg, rgba(248,250,252,0) 0%, rgba(248,250,252,1) 30%);
  border-top: 1px solid #e5e7eb;
}
.sidebar-auth-footer .btn-signin button    { background:#3b82f6 !important; color:#fff !important; border-color:#3b82f6 !important; }
.sidebar-auth-footer .btn-register button  { background:#22c55e !important; color:#fff !important; border-color:#22c55e !important; }
.sidebar-auth-footer .btn-logout button    { background:#ef4444 !important; color:#fff !important; border-color:#ef4444 !important; }
.sidebar-auth-footer button:hover { filter:brightness(0.95); }
</style>
""", unsafe_allow_html=True)

# ========= Theme =========
apply_theme(st.session_state.theme)

# ========= cache imports + page map once =========
if "PAGE_MAP" not in st.session_state:
    missing_modules = []

    def _safe_import(mod_name: str, func_name: str):
        try:
            mod = importlib.import_module(mod_name)
            if not hasattr(mod, func_name):
                return None, (mod_name, f"does not define `{func_name}()`")
            return mod, None
        except Exception as e:
            return None, (mod_name, str(e))

    def import_page(basename: str, func_name: str):
        last_err = None
        for candidate in (f"models.{basename}", f"modules.{basename}", f"pages.{basename}", basename):
            mod, err = _safe_import(candidate, func_name)
            if mod:
                return mod, None
            last_err = err
        return None, last_err

    pv, err1   = import_page("page_valve",             "render_valve")
    pd, err2   = import_page("page_dc001",             "render_dc001")
    pa, err3   = import_page("page_dc001a",            "render_dc001a")
    ps, err4   = import_page("page_dc002",             "render_dc002")
    pc, err5   = import_page("page_dc002a",            "render_dc002a")
    pe, err6   = import_page("page_dc003",             "render_dc003")
    pf, err7   = import_page("page_dc004",             "render_dc004")
    pg, err8   = import_page("page_dc005",             "render_dc005")
    ph, err9   = import_page("page_dc005a",            "render_dc005a")
    pi, err10  = import_page("page_dc006",             "render_dc006")
    pj, err11  = import_page("page_dc006a",            "render_dc006a")
    pk, err12  = import_page("page_dc007_body",        "render_dc007_body")
    pl, err13  = import_page("page_dc007_body_holes",  "render_dc007_body_holes")
    pm, err14  = import_page("page_dc008",             "render_dc008")
    pn, err15  = import_page("page_dc010",             "render_dc010")
    po, err16  = import_page("page_dc011",             "render_dc011")
    pp, err17  = import_page("page_dc012",             "render_dc012")
    pa_lib, err18  = import_page("page_admin_library", "render_admin_library")
    pmylib, err19  = import_page("page_my_library",    "render_my_library")

    for err in (err1, err2, err3, err4, err5, err6, err7, err8, err9, err10, err11, err12, err13, err14, err15, err16, err17, err18, err19):
        if err:
            missing_modules.append(err)

    if missing_modules:
        st.error("One or more page modules failed to import. See details below.")
        for name, msg in missing_modules:
            st.markdown(f"**{name}**: `{msg}`")
        st.stop()

    st.session_state.PAGE_MAP = {
        "Valve Data": pv.render_valve,
        "DC001 (Seat insert & spring)": pd.render_dc001,
        "DC001A (Self relieving)": pa.render_dc001a,
        "DC002 (Body-closure bolts)": ps.render_dc002,
        "DC002A (Bolts test condition)": pc.render_dc002a,
        "DC003 (Bearing stress)": pe.render_dc003,
        "DC004 (Seat thickness)": pf.render_dc004,
        "DC005 (Bolt calc – gland)": pg.render_dc005,
        "DC005A (Bolt calc – test)": ph.render_dc005a,
        "DC006 (Flange stress)": pi.render_dc006,
        "DC006A (Flange stress – test)": pj.render_dc006a,
        "DC007_1_body (Body wall thickness)": pk.render_dc007_body,
        "DC007-2_body (Body holes)": pl.render_dc007_body_holes,
        "DC008 (Ball sizing)": pm.render_dc008,
        "DC010 (Valve Torque Calculation)": pn.render_dc010,
        "DC011 (Flow Coefficient (Cv) Calculation)": po.render_dc011,
        "DC012 (Lifting Lugs (Eye Bolts) Calculation)": pp.render_dc012,
        "My Library (Summary)": pmylib.render_my_library,
        "Admin • All Designs": pa_lib.render_admin_library,  # hidden unless superadmin
    }

PAGE_MAP = st.session_state.PAGE_MAP
ADMIN_LABEL = "Admin • All Designs"

# ========= auth & nav state =========
if "auth_view" not in st.session_state:
    st.session_state.auth_view = None

# Seed active page once from URL
if "active_page" not in st.session_state:
    qp = qp_get_all()
    seed = qp.get("nav")
    st.session_state.active_page = seed if (seed in PAGE_MAP) else "Valve Data"

# Auto-login from URL token
if "user" not in st.session_state:
    qp = qp_get_all()
    token = qp.get("auth")
    v = validate_token(token)
    if v:
        st.session_state["user"] = {
            **({"id": v.get("id")} if isinstance(v, dict) and v.get("id") else {}),
            "username": v["username"],
            "role": v["role"],
            "first_name": v.get("first_name", ""),
            "last_name": v.get("last_name", ""),
        }
        if st.session_state.get("auth_view") in ("login", None):
            st.session_state["auth_view"] = None
            st.session_state["redirect_to_page"] = st.session_state.get("redirect_to_page", st.session_state.active_page)

# Keep active_page synced if URL ?nav= changed
qp_nav = qp_get_all().get("nav")
if qp_nav and qp_nav in PAGE_MAP and qp_nav != st.session_state.active_page:
    st.session_state.active_page = qp_nav

# If a non-admin tries to land on Admin page, push them away + fix URL
user = st.session_state.get("user")
is_superadmin = bool(user and user.get("role") == "superadmin")
if st.session_state.active_page == ADMIN_LABEL and not is_superadmin:
    st.session_state.active_page = "Valve Data"
    q = qp_get_all()
    q["nav"] = "Valve Data"
    set_query_params_silent(**q)

# Handle redirects
if st.session_state.get("redirect_to_page"):
    st.session_state.active_page = st.session_state.pop("redirect_to_page")

# ========= SIDEBAR (static HTML -> minimal flicker) =========
with st.sidebar:
    # Profile (static HTML)
    if user:
        full_name = f"{user.get('first_name','').strip()} {user.get('last_name','').strip()}".strip()
        display_name = full_name if full_name else user.get("username", "")
        st.markdown(
            f"""
            <div class="sidebar-profile">
                <div class="name">{display_name}</div>
                <div class="role">{user.get('role','user').title()}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="sidebar-profile">
                <div class="name">Welcome</div>
                <div class="role">Please sign in</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Theme select (optional)
    sel = st.selectbox("Theme", list(THEMES.keys()),
                       index=list(THEMES.keys()).index(st.session_state.theme))
    if sel != st.session_state.theme:
        st.session_state.theme = sel
        apply_theme(sel)

    # Link nav (pure HTML; minimal repaint)
    st.markdown('<div class="nav-title">Valve Design Suite</div>', unsafe_allow_html=True)

    def _allowed(page_name: str, user_dict) -> bool:
        if page_name == ADMIN_LABEL:
            return bool(user_dict and user_dict.get("role") == "superadmin")
        return True

    base_qp = qp_get_all()
    links = ['<div class="nav-links">']
    for name in PAGE_MAP.keys():
        if not _allowed(name, user):
            continue
        active = (st.session_state.active_page == name)
        cls = "nav active" if active else "nav"
        q = dict(base_qp)
        q["nav"] = name
        href = "?" + urlencode(q, quote_via=quote)
        links.append(f'<a class="{cls}" href="{href}" target="_self">{name}</a>')
    links.append("</div>")
    st.markdown("\n".join(links), unsafe_allow_html=True)

    # Auth footer
    st.markdown('<div class="sidebar-auth-footer">', unsafe_allow_html=True)
    c1, c2 = st.columns(2, gap="small")
    if user:
        with c1:
            st.markdown('<div class="btn-logout">', unsafe_allow_html=True)
            if st.button("Logout", use_container_width=True):
                logout_now()
            st.markdown("</div>", unsafe_allow_html=True)
        with c2:
            if is_superadmin:
                st.markdown('<div class="btn-register">', unsafe_allow_html=True)
                if st.button("Register", use_container_width=True):
                    st.session_state.auth_view = "register"
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.empty()
    else:
        with c1:
            st.markdown('<div class="btn-signin">', unsafe_allow_html=True)
            if st.button("Sign in", use_container_width=True):
                st.session_state.auth_view = "login"
            st.markdown("</div>", unsafe_allow_html=True)
        with c2:
            st.empty()
    st.markdown("</div>", unsafe_allow_html=True)

# ========= MAIN =========
if st.session_state.get("user") and st.session_state.get("auth_view") == "login":
    st.session_state["auth_view"] = None
    st.session_state["redirect_to_page"] = st.session_state.get("redirect_to_page", st.session_state.active_page)

if st.session_state.auth_view == "login":
    st.title("Login")
    st.markdown("---")
    login_form()
elif st.session_state.auth_view == "register":
    st.title("Register (superadmin only)")
    st.markdown("---")
    register_form()
else:
    if not st.session_state.get("user"):
        st.title("Please sign in")
        st.markdown("---")
        st.warning("You must **sign in** to access the calculation pages.")
        if st.button("Open Sign in form"):
            st.session_state.auth_view = "login"
    else:
        st.title(st.session_state.active_page)
        st.markdown("---")
        try:
            PAGE_MAP[st.session_state.active_page]()
        except Exception as e:
            st.error(f"Error while rendering {st.session_state.active_page}: {e}")
