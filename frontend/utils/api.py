# --- file: utils/api.py ---
# ═══════════════════════════════════════════════════════════════════════════
# API LAYER — all HTTP communication with the Render backend.
#
# Every function returns a predictable Python type. Pages never call requests
# directly — they go through this module so error handling is centralised.
# ═══════════════════════════════════════════════════════════════════════════

import requests
import streamlit as st
import os

# ── BASE_URL ─────────────────────────────────────────────────────────────────
# Read from environment variable so the same codebase works in dev and prod.
# On Streamlit Cloud, set BASE_URL in app secrets / environment variables.
BASE_URL = os.getenv(
    "BASE_URL",
    "https://smart-gst-intelligence-system.onrender.com"
)


# ── _headers ─────────────────────────────────────────────────────────────────
# Attaches the JWT Bearer token to every authenticated request.
# Token is stored in st.session_state["token"] after login.
# If no token exists we return an empty dict — the backend will return 401
# which _handle_401 catches and redirects to login.
def _headers():
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}


# ── _safe_json ───────────────────────────────────────────────────────────────
# WHY: response.json() raises json.JSONDecodeError if the backend returns a
# non-JSON response (e.g. HTML error page from Render's cold-start proxy).
# We return {} instead of crashing so callers always get a dict.
def _safe_json(response) -> dict:
    try:
        return response.json()
    except Exception:
        return {}


# ── _handle_401 ──────────────────────────────────────────────────────────────
# JWT tokens expire (default 30 min on the backend). When the token expires,
# every API call returns 401. We clear session and force re-login so the user
# doesn't see confusing "MongoDB Fetch Failed: 401" errors.
def _handle_401(response) -> None:
    if response.status_code == 401:
        st.session_state.clear()
        st.error("Session expired. Please log in again.")
        st.rerun()


# ── login ────────────────────────────────────────────────────────────────────
# WHY IT RETURNS (status_code, data):
#   Pages need the status code to decide what to show (success vs error message).
#   Returning a tuple keeps the API contract explicit — callers always unpack both.
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
# Sends the compressed image bytes to the /process endpoint.
# The backend runs Tesseract OCR, validates the GSTIN, stores to MongoDB and
# Cloudinary, then returns the extracted fields + validation flags.
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
# WHY THE SHAPE-CHECK MATTERS:
#   The backend can return either:
#     (a) A JSON array  → [{"_id":...}, ...]
#     (b) A JSON object → {"records": [...], "total": 42}
#     (c) A status/error dict with no "records" key → {"status": "ok"}
#
#   The original code used `data.get("records", data)` which for case (c)
#   returned the entire dict as the fallback — that dict then got wrapped as
#   a single fake "invoice" record, crashing every downstream .get("GSTIN").
#
#   The fix: explicit shape checking. Only return records when we can confirm
#   the data is a list or a dict containing a list under "records". Otherwise
#   return [] and let the UI show its empty state gracefully.
def get_records() -> list:
    """
    Fetch all invoice documents from MongoDB via the backend.
    Always returns a list (never None, never a dict).
    """
    try:
        r = requests.get(
            f"{BASE_URL}/records",
            headers=_headers(),
            timeout=30,
        )
        _handle_401(r)

        if r.status_code == 200:
            data = _safe_json(r)

            # Case (a): backend returned a plain list
            if isinstance(data, list):
                return data

            # Case (b): backend wrapped records in an object
            if isinstance(data, dict):
                records_val = data.get("records")
                if isinstance(records_val, list):
                    return records_val

            # Case (c) or unknown shape — fail safe
            return []

        st.sidebar.error(f"MongoDB Fetch Failed: {r.status_code}")
        return []

    except requests.exceptions.ConnectionError:
        st.sidebar.warning("Backend is waking up... please wait ⏳")
        return []
    except Exception as e:
        st.sidebar.error(f"Database Error: {str(e)}")
        return []


# ── health_check ─────────────────────────────────────────────────────────────
# Used by profile.py to show the API connection status indicator.
# Returns a dict (not bool) for forward compatibility with richer status info.
def health_check() -> dict:
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        return {"status": "ok"} if r.status_code == 200 else {"status": "error"}
    except Exception:
        return {"status": "error"}