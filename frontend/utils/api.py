# --- file: utils/api.py ---

import requests
import streamlit as st
import os

# Backend URL
BASE_URL = os.getenv(
    "BASE_URL",
    "https://smart-gst-intelligence-system.onrender.com"
)


# ------------------ HELPERS ------------------

def _headers():
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _safe_json(response):
    try:
        return response.json()
    except Exception:
        return {}


def _handle_401(response):
    if response.status_code == 401:
        st.session_state.clear()
        st.error("Session expired. Please log in again.")
        st.rerun()


# ------------------ AUTH ------------------

def login(email: str, password: str):
    try:
        r = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": email, "password": password},
            timeout=15
        )

        data = _safe_json(r)

        if r.status_code == 200:
            st.session_state["token"] = data.get("access_token")
            st.session_state["user"] = email

        return r.status_code, data

    except Exception as e:
        return 500, {"detail": str(e)}


def signup(email: str, password: str):
    try:
        r = requests.post(
            f"{BASE_URL}/auth/signup",
            json={"email": email, "password": password},
            timeout=15
        )

        data = _safe_json(r)
        return r.status_code, data

    except Exception as e:
        return 500, {"detail": str(e)}


# ------------------ INVOICE PROCESS ------------------

def process_invoice(file_bytes, filename: str):
    try:
        r = requests.post(
            f"{BASE_URL}/process",
            headers=_headers(),
            files={"file": (filename, file_bytes, "image/png")},
            timeout=30
        )

        _handle_401(r)
        return r.status_code, _safe_json(r)

    except Exception as e:
        return 500, {"detail": f"Connection Error: {str(e)}"}


# ------------------ RECORDS ------------------

def get_records():
    """
    Fetches all invoice documents from MongoDB via backend.
    """
    try:
        r = requests.get(
            f"{BASE_URL}/records",
            headers=_headers(),
            timeout=30
        )

        _handle_401(r)

        if r.status_code == 200:
            data = _safe_json(r)

            # Handles both {"records": [...]} and [...]
            return data.get("records", data) if isinstance(data, dict) else data

        st.sidebar.error(f"MongoDB Fetch Failed: {r.status_code}")
        return []

    except requests.exceptions.ConnectionError:
        st.sidebar.warning("Backend is waking up... please wait ⏳")
        return []

    except Exception as e:
        st.sidebar.error(f"Database Error: {str(e)}")
        return []


# ------------------ HEALTH ------------------

def health_check():
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        return {"status": "ok"} if r.status_code == 200 else {"status": "error"}
    except Exception:
        return {"status": "error"}