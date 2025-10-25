# auth.py — Supabase-only (no SQLAlchemy)
from __future__ import annotations
import secrets, hashlib, hmac, binascii, datetime as dt
from typing import Optional, List, Dict, Any

import streamlit as st
from db import get_supabase

# ---- Password hashing (std-lib PBKDF2-HMAC) ----
PBKDF2_ITER = 200_000

def _hash_password_pbkdf2(password: str, salt_hex: str, iterations: int = PBKDF2_ITER) -> str:
    salt = binascii.unhexlify(salt_hex.encode("ascii"))
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return binascii.hexlify(dk).decode("ascii")

def _new_salt_hex(nbytes: int = 16) -> str:
    return secrets.token_hex(nbytes)

# ---- Roles / constants ----
TOKEN_TTL_SECONDS = 7 * 24 * 3600  # 7 days
VALID_ROLES = ("user", "superadmin")

DEFAULT_SUPERADMIN = {
    "username": "superadmin",
    "password": "Super@123",
    "role": "superadmin",
    "first_name": "Super",
    "last_name": "Admin",
}

# Optional: allow overriding bootstrap superadmin via secrets
def _bootstrap_overrides() -> Dict[str, Any]:
    auth = st.secrets.get("auth", {})
    return {
        "username": auth.get("bootstrap_superadmin_username", DEFAULT_SUPERADMIN["username"]),
        "password": auth.get("bootstrap_superadmin_password", DEFAULT_SUPERADMIN["password"]),
        "first_name": auth.get("bootstrap_superadmin_first_name", DEFAULT_SUPERADMIN["first_name"]),
        "last_name": auth.get("bootstrap_superadmin_last_name", DEFAULT_SUPERADMIN["last_name"]),
        "role": "superadmin",
    }

# ---- Bootstrap: ensure a superadmin exists (Supabase) ----
def _ensure_superadmin():
    sb = get_supabase()
    seed = _bootstrap_overrides()
    username = seed["username"]

    # Does it exist?
    res = sb.table("users").select("id").eq("username", username).limit(1).execute()
    if res.data:
        return

    # Create default superadmin
    salt_hex = _new_salt_hex()
    pwd_hash = _hash_password_pbkdf2(seed["password"], salt_hex, PBKDF2_ITER)
    _ = sb.table("users").insert({
        "username": username,
        "pwd_hash": pwd_hash,
        "salt_hex": salt_hex,
        "iterations": PBKDF2_ITER,
        "role": "superadmin",
        "first_name": seed["first_name"],
        "last_name": seed["last_name"],
    }).execute()

# ---- User CRUD (superadmin only for write ops) ----
def get_user_by_username(username: str) -> Optional[dict]:
    sb = get_supabase()
    res = sb.table("users").select(
        "id, username, role, first_name, last_name, iterations, salt_hex, pwd_hash"
    ).eq("username", username).limit(1).execute()
    if not res.data:
        return None
    # return row as-is (keys match existing code expectations)
    return res.data[0]

def list_users() -> list[dict]:
    sb = get_supabase()
    res = sb.table("users").select(
        "id, username, role, first_name, last_name, created_at"
    ).order("created_at", desc=True).execute()
    return res.data or []

def create_user(username: str, password: str, role: str = "user",
                first_name: str = "", last_name: str = ""):
    if role not in VALID_ROLES:
        raise ValueError("Invalid role")
    if not username or not password:
        raise ValueError("Username and password are required")

    sb = get_supabase()
    # Duplicate check
    chk = sb.table("users").select("id").eq("username", username).limit(1).execute()
    if chk.data:
        raise ValueError("Username already exists")

    salt_hex = _new_salt_hex()
    pwd_hash = _hash_password_pbkdf2(password, salt_hex, PBKDF2_ITER)
    ins = sb.table("users").insert({
        "username": username,
        "pwd_hash": pwd_hash,
        "salt_hex": salt_hex,
        "iterations": PBKDF2_ITER,
        "role": role,
        "first_name": (first_name or "").strip(),
        "last_name": (last_name or "").strip(),
    }).execute()
    if getattr(ins, "error", None):
        raise RuntimeError(f"Create failed: {ins.error}")

def update_user(
    user_id: str,
    *,
    password: Optional[str] = None,
    role: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None
):
    updates: Dict[str, Any] = {}

    if password:
        salt_hex = _new_salt_hex()
        pwd_hash = _hash_password_pbkdf2(password, salt_hex, PBKDF2_ITER)
        updates.update({"pwd_hash": pwd_hash, "salt_hex": salt_hex, "iterations": PBKDF2_ITER})

    if role is not None:
        if role not in VALID_ROLES:
            raise ValueError("Invalid role")
        updates["role"] = role

    if first_name is not None:
        updates["first_name"] = (first_name or "").strip()
    if last_name is not None:
        updates["last_name"] = (last_name or "").strip()

    if not updates:
        return

    sb = get_supabase()
    res = sb.table("users").update(updates).eq("id", user_id).execute()
    if getattr(res, "error", None):
        raise RuntimeError(f"Update failed: {res.error}")

def delete_user(user_id: str):
    sb = get_supabase()
    res = sb.table("users").delete().eq("id", user_id).execute()
    if getattr(res, "error", None):
        raise RuntimeError(f"Delete failed: {res.error}")

# ---- Auth core ----
def authenticate(username: str, password: str) -> Optional[dict]:
    sb = get_supabase()
    res = sb.table("users").select(
        "id, username, role, first_name, last_name, salt_hex, iterations, pwd_hash"
    ).eq("username", username).limit(1).execute()

    if not res.data:
        return None

    row = res.data[0]
    uid = row.get("id")
    uname = row.get("username")
    role = row.get("role")
    first_name = row.get("first_name")
    last_name = row.get("last_name")
    salt_hex = row.get("salt_hex")
    iterations = int(row.get("iterations") or PBKDF2_ITER)
    stored_hash = row.get("pwd_hash")

    calc_hash = _hash_password_pbkdf2(password, salt_hex, iterations)
    if hmac.compare_digest(calc_hash, stored_hash):
        return {
            "id": str(uid),
            "username": uname,
            "role": role,
            "first_name": first_name,
            "last_name": last_name,
        }
    return None

def register_user(*args, **kwargs):
    """Compatibility wrapper; superadmin uses UI below."""
    return create_user(*args, **kwargs)

# ---- Token helpers (URL query param, stored in DB) ----
def issue_token(user: dict) -> str:
    sb = get_supabase()
    token = secrets.token_urlsafe(24)
    now = dt.datetime.now(dt.timezone.utc)
    exp = now + dt.timedelta(seconds=TOKEN_TTL_SECONDS)

    ins = sb.table("auth_tokens").insert({
        "token": token,
        "user_id": user["id"],
        "created_at": now.isoformat(),
        "exp_at": exp.isoformat(),
    }).execute()
    if getattr(ins, "error", None):
        # Fallback: still return token, but note the error in logs
        print("auth_tokens insert error:", ins.error)
    return token

def validate_token(token: Optional[str]):
    if not token:
        return None
    sb = get_supabase()
    res = sb.table("auth_tokens").select(
        "user_id, exp_at, users!inner(id,username,role,first_name,last_name)"
    ).eq("token", token).limit(1).execute()

    if not res.data:
        return None

    row = res.data[0]
    exp_at = row.get("exp_at")
    try:
        # Supabase returns ISO strings
        exp_dt = dt.datetime.fromisoformat(exp_at.replace("Z", "+00:00")) if isinstance(exp_at, str) else None
    except Exception:
        exp_dt = None

    now = dt.datetime.now(dt.timezone.utc)
    if exp_dt and now > exp_dt:
        # best-effort delete (ignore errors)
        try:
            sb.table("auth_tokens").delete().eq("token", token).execute()
        except Exception:
            pass
        return None

    # User info via join alias users
    u = row.get("users") or {}
    return {
        "id": str(u.get("id") or row.get("user_id")),
        "username": u.get("username"),
        "role": u.get("role"),
        "first_name": u.get("first_name"),
        "last_name": u.get("last_name"),
        "token": token,
    }

def revoke_token(token: Optional[str]):
    if not token:
        return
    sb = get_supabase()
    try:
        sb.table("auth_tokens").delete().eq("token", token).execute()
    except Exception:
        pass

# ---- URL query token setter (not strictly needed here) ----
def _set_query_token(token: Optional[str]):
    qp = st.query_params
    if token:
        qp["auth"] = token
    else:
        if "auth" in qp:
            del qp["auth"]

# ---- Page guards ----
def current_user() -> Optional[dict]:
    if "user" in st.session_state and st.session_state["user"]:
        return st.session_state["user"]
    tok = st.query_params.get("auth")
    if isinstance(tok, list):
        tok = tok[0] if tok else None
    user = validate_token(tok)
    if user:
        st.session_state["user"] = user
        return user
    return None

def require_role(roles: List[str]):
    user = current_user()
    if not user:
        st.stop()
    if user["role"] not in roles:
        st.error("You don't have permission to view this page.")
        st.stop()

# ---- Streamlit UI helpers ----
def login_form():
    _ensure_superadmin()  # seed default admin if needed
    st.subheader("Login")
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            user = authenticate(username, password)
            if user:
                st.session_state["user"] = user
                token = issue_token(user)
                qp = st.query_params
                qp["auth"] = token
                st.session_state["auth_view"] = None
                st.session_state["redirect_to_page"] = "Valve Data"
                st.success(f"Welcome, {user.get('first_name') or user['username']}!")
                st.rerun()
            else:
                st.error("Invalid username or password.")

def register_form():
    st.subheader("User Management (superadmin only)")
    cu = current_user()
    if not cu or cu.get("role") != "superadmin":
        st.info("Only superadmin can manage users.")
        return

    st.markdown("#### Create user")
    with st.form("register_form", clear_on_submit=True):
        first_name = st.text_input("First name")
        last_name  = st.text_input("Last name")
        username   = st.text_input("Username")
        password   = st.text_input("Password", type="password")
        role       = st.selectbox("Role", ["user", "superadmin"], index=0)
        submitted  = st.form_submit_button("Create user")
        if submitted:
            try:
                create_user(username, password, role, first_name, last_name)
                st.success(f"User '{username}' created with role '{role}'.")
            except Exception as e:
                st.error(str(e))

    st.markdown("---")
    st.markdown("#### Existing users")
    users = list_users()
    if not users:
        st.info("No users yet.")
        return

    for u in users:
        with st.expander(f"{u['username']} • {u['role']}"):
            new_first = st.text_input("First name", value=u.get("first_name") or "", key=f"fn_{u['id']}")
            new_last  = st.text_input("Last name",  value=u.get("last_name") or "",  key=f"ln_{u['id']}")
            new_role  = st.selectbox("Role", ["user","superadmin"], index=0 if u.get("role")=="user" else 1, key=f"role_{u['id']}")
            new_pwd   = st.text_input("Reset password (leave blank to keep)", type="password", key=f"pw_{u['id']}")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("💾 Save", key=f"save_{u['id']}"):
                    try:
                        update_user(
                            u["id"],
                            password=new_pwd or None,
                            role=new_role,
                            first_name=new_first,
                            last_name=new_last
                        )
                        st.success("Updated.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
            with c2:
                if u["username"] == DEFAULT_SUPERADMIN["username"]:
                    st.caption("Default superadmin cannot be deleted.")
                else:
                    if st.button("🗑️ Delete", key=f"del_{u['id']}"):
                        try:
                            delete_user(u["id"])
                            st.success("Deleted.")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

def logout_now():
    token = st.query_params.get("auth")
    if isinstance(token, list):
        token = token[0] if token else None
    if token:
        revoke_token(token)
    try:
        _set_query_token(None)
    except Exception:
        pass
    st.session_state.pop("user", None)
    st.session_state["auth_view"] = "login"
    st.rerun()
