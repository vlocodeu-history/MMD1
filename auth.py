# auth.py
from __future__ import annotations
import secrets, hashlib, hmac, binascii, datetime as dt
from typing import Optional, List

import streamlit as st
from sqlalchemy import text
from db import connect, scalar

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

# ---- Bootstrap: ensure a superadmin exists ----
def _ensure_superadmin():
    with connect() as conn:
        exists = scalar(conn, "SELECT 1 FROM users WHERE username=:u", u=DEFAULT_SUPERADMIN["username"])
        if exists:
            return
        salt_hex = _new_salt_hex()
        pwd_hash = _hash_password_pbkdf2(DEFAULT_SUPERADMIN["password"], salt_hex, PBKDF2_ITER)
        conn.execute(
            text("""
                INSERT INTO users (username, pwd_hash, salt_hex, iterations, role, first_name, last_name)
                VALUES (:u, :h, :s, :it, :r, :f, :l)
            """),
            dict(
                u=DEFAULT_SUPERADMIN["username"], h=pwd_hash, s=salt_hex, it=PBKDF2_ITER,
                r="superadmin", f=DEFAULT_SUPERADMIN["first_name"], l=DEFAULT_SUPERADMIN["last_name"]
            )
        )

# ---- User CRUD (superadmin only for write ops) ----
def get_user_by_username(username: str) -> Optional[dict]:
    with connect() as conn:
        row = conn.execute(text("""
            SELECT id, username, role, first_name, last_name, iterations, salt_hex, pwd_hash
            FROM users WHERE username=:u
        """), {"u": username}).one_or_none()
        if not row: return None
        keys = ["id","username","role","first_name","last_name","iterations","salt_hex","pwd_hash"]
        return dict(zip(keys, row))

def list_users() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(text("""
            SELECT id, username, role, first_name, last_name, created_at
            FROM users ORDER BY created_at DESC
        """)).all()
        out = []
        for r in rows:
            out.append({
                "id": r[0], "username": r[1], "role": r[2],
                "first_name": r[3], "last_name": r[4], "created_at": r[5]
            })
        return out

def create_user(username: str, password: str, role: str = "user", first_name: str = "", last_name: str = ""):
    if role not in VALID_ROLES:
        raise ValueError("Invalid role")
    if not username or not password:
        raise ValueError("Username and password are required")
    with connect() as conn:
        exists = scalar(conn, "SELECT 1 FROM users WHERE username=:u", u=username)
        if exists:
            raise ValueError("Username already exists")
        salt_hex = _new_salt_hex()
        pwd_hash = _hash_password_pbkdf2(password, salt_hex, PBKDF2_ITER)
        conn.execute(text("""
            INSERT INTO users (username, pwd_hash, salt_hex, iterations, role, first_name, last_name)
            VALUES (:u, :h, :s, :it, :r, :f, :l)
        """), dict(u=username, h=pwd_hash, s=salt_hex, it=PBKDF2_ITER, r=role,
                   f=first_name.strip(), l=last_name.strip()))

def update_user(
    user_id: str,
    *,
    password: Optional[str] = None,
    role: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None
):
    sets = []; params = {"id": user_id}
    if password:
        salt_hex = _new_salt_hex()
        pwd_hash = _hash_password_pbkdf2(password, salt_hex, PBKDF2_ITER)
        sets += ["pwd_hash=:h", "salt_hex=:s", "iterations=:it"]
        params.update(h=pwd_hash, s=salt_hex, it=PBKDF2_ITER)
    if role:
        if role not in VALID_ROLES:
            raise ValueError("Invalid role")
        sets.append("role=:r"); params["r"] = role
    if first_name is not None:
        sets.append("first_name=:f"); params["f"] = first_name.strip()
    if last_name is not None:
        sets.append("last_name=:l"); params["l"] = last_name.strip()
    if not sets:
        return
    with connect() as conn:
        conn.execute(text(f"UPDATE users SET {', '.join(sets)} WHERE id=:id"), params)

def delete_user(user_id: str):
    with connect() as conn:
        conn.execute(text("DELETE FROM users WHERE id=:id"), {"id": user_id})

# ---- Auth core ----
def authenticate(username: str, password: str) -> Optional[dict]:
    with connect() as conn:
        row = conn.execute(text("""
            SELECT id, username, role, first_name, last_name, salt_hex, iterations, pwd_hash
            FROM users WHERE username=:u
        """), {"u": username}).one_or_none()
        if not row:
            return None
        uid, uname, role, first_name, last_name, salt_hex, iterations, stored_hash = row
        calc_hash = _hash_password_pbkdf2(password, salt_hex, int(iterations))
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

# ---- Token helpers (URL query param) ----
def issue_token(user: dict) -> str:
    token = secrets.token_urlsafe(24)
    now = dt.datetime.now(dt.timezone.utc)
    exp = now + dt.timedelta(seconds=TOKEN_TTL_SECONDS)
    with connect() as conn:
        conn.execute(text("""
            INSERT INTO auth_tokens (token, user_id, created_at, exp_at)
            VALUES (:t, :uid, :c, :e)
        """), {"t": token, "uid": user["id"], "c": now, "e": exp})
    return token

def validate_token(token: Optional[str]):
    if not token:
        return None
    with connect() as conn:
        row = conn.execute(text("""
            SELECT t.user_id, u.username, u.role, u.first_name, u.last_name, t.exp_at
            FROM auth_tokens t
            JOIN users u ON u.id = t.user_id
            WHERE t.token=:t
        """), {"t": token}).one_or_none()
        if not row:
            return None

        user_id, username, role, first_name, last_name, exp_at = row
        now = dt.datetime.now(dt.timezone.utc)
        exp_at = _as_aware_utc(exp_at)

        if exp_at is not None and now > exp_at:
            conn.execute(text("DELETE FROM auth_tokens WHERE token=:t"), {"t": token})
            return None

        return {
            "id": str(user_id),
            "username": username,
            "role": role,
            "first_name": first_name,
            "last_name": last_name,
            "token": token,
        }


def revoke_token(token: Optional[str]):
    if not token:
        return
    with connect() as conn:
        conn.execute(text("DELETE FROM auth_tokens WHERE token=:t"), {"t": token})

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
                qp = st.query_params; qp["auth"] = token
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
            new_first = st.text_input("First name", value=u["first_name"], key=f"fn_{u['id']}")
            new_last  = st.text_input("Last name",  value=u["last_name"],  key=f"ln_{u['id']}")
            new_role  = st.selectbox("Role", ["user","superadmin"], index=0 if u["role"]=="user" else 1, key=f"role_{u['id']}")
            new_pwd   = st.text_input("Reset password (leave blank to keep)", type="password", key=f"pw_{u['id']}")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("💾 Save", key=f"save_{u['id']}"):
                    try:
                        update_user(u["id"], password=new_pwd or None, role=new_role,
                                    first_name=new_first, last_name=new_last)
                        st.success("Updated.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
            with c2:
                if u["username"] == "superadmin":
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

def _as_aware_utc(ts: dt.datetime | None) -> dt.datetime | None:
    if ts is None:
        return None
    if ts.tzinfo is None:
        # treat naive as UTC
        return ts.replace(tzinfo=dt.timezone.utc)
    return ts.astimezone(dt.timezone.utc)