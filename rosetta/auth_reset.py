# rosetta/auth_reset.py
from __future__ import annotations
import time
import hashlib
import streamlit as st
from rosetta.db import supa
from rosetta.users import set_password  # already in your project


def _hash_code(code: str, pepper: str) -> str:
    h = hashlib.sha256()
    h.update((pepper + str(code)).encode("utf-8"))
    return h.hexdigest()


def _find_user_by_identifier(identifier: str):
    sb = supa()
    ident = (identifier or "").strip()
    if not ident:
        return None
    res = (
        sb.table("users")
        .select("username,email")
        .or_(f"username.eq.{ident},email.eq.{ident}")
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        return None
    row = rows[0]
    return row["username"], row["email"]


def _store_reset_code(
    username: str, email_addr: str, code_hash: str, ttl_minutes: int = 15
):
    sb = supa()
    now = int(time.time())
    exp = now + ttl_minutes * 60
    sb.table("password_resets").insert(
        {
            "username": username,
            "code_hash": code_hash,
            "sent_to": email_addr,
            "expires_at": exp,
            "used": False,
            "created_at": now,
        }
    ).execute()


def request_password_reset(identifier: str):
    """
    Returns (ok: bool, username: str, msg: str)
      - (True, <username>, "sent")        -> code emailed successfully
      - (True, <username>, "<6digit>")    -> DEV mode (no SMTP): show code in UI
      - (False, "", "<error message>")    -> invalid / error
    """
    ident = (identifier or "").strip()
    if not ident:
        return False, "", "Enter a username or email."

    found = _find_user_by_identifier(ident)
    if not found:
        return False, "", "No user found with that username or email."
    username, email_addr = found

    # 6-digit code
    import secrets as pysecrets

    code = f"{pysecrets.randbelow(1_000_000):06d}"

    # Hash + store with TTL
    pepper = st.secrets.get("security", {}).get("reset_pepper", "static-dev-pepper")
    code_hash = _hash_code(code, pepper)

    try:
        _store_reset_code(username, email_addr, code_hash, ttl_minutes=15)
    except Exception as e:
        return False, "", f"Could not create reset code: {e}"

    # Try to email; if no SMTP, fall back to DEV reveal
    smtp = st.secrets.get("smtp", {}) or {}
    host = smtp.get("host")
    if host:
        try:
            import smtplib
            import ssl
            from email.message import EmailMessage

            port = int(smtp.get("port", 587))
            user = smtp.get("user") or smtp.get("username")
            password = smtp.get("password")
            sender = smtp.get("sender") or user or f"no-reply@{host}"
            use_ssl = bool(smtp.get("ssl", False))
            starttls = bool(smtp.get("starttls", True))

            msg = EmailMessage()
            msg["Subject"] = "Your Rosetta password reset code"
            msg["From"] = sender
            msg["To"] = email_addr
            msg.set_content(
                f"Hi {username},\n\n"
                f"Your password reset code is: {code}\n"
                f"It expires in 15 minutes.\n\n"
                f"If you didn’t request this, you can ignore this email."
            )

            if use_ssl:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(host, port, context=context) as s:
                    if user and password:
                        s.login(user, password)
                    s.send_message(msg)
            else:
                with smtplib.SMTP(host, port) as s:
                    if starttls:
                        s.starttls(context=ssl.create_default_context())
                    if user and password:
                        s.login(user, password)
                    s.send_message(msg)

            return True, username, "sent"
        except Exception:
            # Email failed → return the code for DEV path
            return True, username, code

    # No SMTP configured → DEV path
    return True, username, code


def verify_reset_code_and_set_password(
    username: str, code: str, new_password: str
) -> bool:
    sb = supa()
    now = int(time.time())
    pepper = st.secrets.get("security", {}).get("reset_pepper", "static-dev-pepper")
    code_hash = _hash_code(code, pepper)

    res = (
        sb.table("password_resets")
        .select("id,expires_at,used")
        .eq("username", username)
        .eq("code_hash", code_hash)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        return False

    row = rows[0]
    if row["used"] or now > row["expires_at"]:
        return False

    sb.table("password_resets").update({"used": True}).eq("id", row["id"]).execute()
    set_password(username, new_password)
    try:
        st.rerun()
    except Exception:
        pass
    return True
