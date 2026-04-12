# --- file: utils/api.py ---
# ═══════════════════════════════════════════════════════════════════════════
# API LAYER — tailored exactly to the backend routes.
#
# BACKEND FACTS (confirmed from all backend files):
#
#   POST /process  (JWT required)
#     → Saves to MongoDB with **extracted spread FLAT:
#       { filename, cloudinary_url, status:"processed", user_email,
#         GSTIN, MERCHANT, TOTAL_AMOUNT, TAXABLE_AMOUNT, GST_AMOUNT,
#         INVOICE_DATE, INVOICE_NO, validation:{gst_valid, amounts_match} }
#     → Returns:
#       { message, record_id, cloudinary_url, extracted:{...} }
#
#   GET /records  (JWT required, paginated)
#     → Returns: { total, page, limit, records:[...flat docs...] }
#     → Default limit=10. We pass limit=1000 to fetch all records at once.
#     → Each record has FLAT fields (no "extracted" nesting) because
#       process.py saves with **extracted spread directly into the doc.
#
#   GET /  → { "message": "API is running 🚀" } (used as health check)
#   No /health route exists in backend.
# ═══════════════════════════════════════════════════════════════════════════

import requests
import streamlit as st
import os
import time

BASE_URL = os.getenv(
    "BASE_URL",
    "https://smart-gst-intelligence-system.onrender.com"
)


# ── _headers ─────────────────────────────────────────────────────────────────
def _headers():
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}


# ── _safe_json ───────────────────────────────────────────────────────────────
def _safe_json(response):
    try:
        return response.json()
    except Exception:
        return {}


# ── _handle_401 ──────────────────────────────────────────────────────────────
def _handle_401(response) -> None:
    if response.status_code == 401:
        st.session_state.clear()
        st.error("Session expired. Please log in again.")
        st.rerun()


# ── login ────────────────────────────────────────────────────────────────────
def login(email: str, password: str):
    try:
        r = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": email, "password": password},
            timeout=15,
        )
        data = _safe_json(r)
        if r.status_code == 200:
            st.session_state["token"] = data.get("access_token")
            st.session_state["user"]  = email
        return r.status_code, data
    except Exception as e:
        return 500, {"detail": str(e)}


# ── signup ───────────────────────────────────────────────────────────────────
def signup(email: str, password: str):
    try:
        r = requests.post(
            f"{BASE_URL}/auth/signup",
            json={"email": email, "password": password},
            timeout=15,
        )
        data = _safe_json(r)
        return r.status_code, data
    except Exception as e:
        return 500, {"detail": str(e)}


# ── process_invoice ───────────────────────────────────────────────────────────
# Backend /process requires JWT Bearer token (Depends(get_current_user)).
# _headers() attaches the token automatically from session_state.
# Response shape: { message, record_id, cloudinary_url, extracted:{...} }
# upload.py result_card() reads result.get("extracted") — correct as-is.
def process_invoice(file_bytes: bytes, filename: str):
    try:
        r = requests.post(
            f"{BASE_URL}/process",
            headers=_headers(),
            files={"file": (filename, file_bytes, "image/png")},
        )
        _handle_401(r)
        return r.status_code, _safe_json(r)
    except Exception as e:
        return 500, {"detail": f"Connection Error: {str(e)}"}


# ── get_records ───────────────────────────────────────────────────────────────
# Backend /records returns: { "total": N, "page": 1, "limit": 10, "records": [...] }
#
# KEY FIXES:
#   FIX 1 — limit=1000: Default backend limit is 10. Without passing a high
#            limit, the dashboard only sees 10 records max and misses all others.
#            We fetch up to 1000 in one call — sufficient for this app's scale.
#
#   FIX 2 — Extract records from wrapper: Backend always wraps in
#            {"total":..., "records":[...]}. We extract the "records" list.
#
#   FIX 3 — Records are already FLAT: process.py saves with **extracted
#            spread, so MERCHANT, GSTIN, TOTAL_AMOUNT etc are at top level.
#            No flattening needed. We return records as-is.
#
#   FIX 4 — 401 handled first: Token expiry returns 401. We clear session
#            immediately instead of showing confusing fetch-failed errors.
#
#   FIX 5 — Retry on 502/503: Render free tier cold-starts return these.
#            We wait 3s and retry once before giving up.
def get_records() -> list:
    """
    Fetch ALL invoice records for the current user.
    Returns a flat list of dicts. Never returns None or a dict.
    """
    max_attempts = 2

    for attempt in range(max_attempts):
        try:
            r = requests.get(
                f"{BASE_URL}/records",
                headers=_headers(),
                params={"limit": 1000, "page": 1},   # FIX 1: fetch all, not just 10
                timeout=30,
            )

            # FIX 4: handle 401 before anything else
            if r.status_code == 401:
                _handle_401(r)
                return []

            if r.status_code == 200:
                data = _safe_json(r)

                # FIX 2: backend always wraps in {"records": [...]}
                if isinstance(data, dict):
                    records_val = data.get("records")
                    if isinstance(records_val, list):
                        # FIX 3: records are flat — return directly
                        return [rec for rec in records_val if isinstance(rec, dict)]

                # Safety: if backend ever returns a plain list
                if isinstance(data, list):
                    return [rec for rec in data if isinstance(rec, dict)]

                # Got 200 but unexpected shape — retry once
                if attempt < max_attempts - 1:
                    time.sleep(2)
                    continue

                st.sidebar.warning("Unexpected response from server. Try refreshing.")
                return []

            # FIX 5: Render cold-start — retry once
            if r.status_code in (502, 503) and attempt < max_attempts - 1:
                st.sidebar.warning("Backend is waking up... retrying ⏳")
                time.sleep(3)
                continue

            st.sidebar.error(f"MongoDB Fetch Failed: {r.status_code}")
            return []

        except requests.exceptions.ConnectionError:
            if attempt < max_attempts - 1:
                time.sleep(2)
                continue
            st.sidebar.warning("Backend is waking up... please wait ⏳")
            return []
        except Exception as e:
            st.sidebar.error(f"Database Error: {str(e)}")
            return []

    return []


# ── health_check ─────────────────────────────────────────────────────────────
# Backend has no /health route. We use GET / which always returns
# {"message": "API is running 🚀"} — presence of "message" key = online.
def health_check() -> dict:
    try:
        r = requests.get(f"{BASE_URL}/", timeout=5)
        if r.status_code == 200:
            return {"status": "ok"}
        return {"status": "error"}
    except Exception:
        return {"status": "error"}