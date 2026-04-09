# --- file: utils/api.py ---
import requests
import streamlit as st
import os
from dotenv import load_dotenv

load_dotenv()

# Update this to your Render URL
BASE_URL = "https://smart-gst-intelligence-system.onrender.com"

def _headers():
    token = st.session_state.get("token", "")
    return {"Authorization": f"Bearer {token}"}

def _handle_401(response):
    if response.status_code == 401:
        st.session_state.clear()
        st.error("Session expired. Please log in again.")
        st.rerun()

def login(email: str, password: str):
    try:
        r = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password}, timeout=15)
        data = r.json()
        if r.status_code == 200:
            # Match the key 'access_token' from your backend security.py
            st.session_state["token"] = data.get("access_token") 
            st.session_state["user"] = email
        return r.status_code, data
    except Exception as e:
        return 500, {"detail": str(e)}

def signup(email: str, password: str):
    try:
        # Use /auth/signup to match your backend router prefix
        r = requests.post(f"{BASE_URL}/auth/signup", json={"email": email, "password": password}, timeout=15)
        return r.status_code, r.json()
    except Exception as e:
        return 500, {"detail": str(e)}

def process_invoice(file_bytes, filename: str):
    try:
        # This MUST match the BASE_URL + /process
        r = requests.post(
            f"{BASE_URL}/process",
            headers=_headers(), # This sends your Login Token
            files={"file": (filename, file_bytes, "image/png")},
           
        )
        return r.status_code, r.json()
    except Exception as e:
        return 500, {"detail": f"Connection Error: {str(e)}"}

def get_records():
    """
    Fetches all invoice documents from MongoDB via the backend.
    """
    try:
        # Increased timeout to 30s as MongoDB cold starts can be slow
        r = requests.get(f"{BASE_URL}/records", headers=_headers(), timeout=30)
        
        # Handle session expiration
        if r.status_code == 401:
            st.session_state.clear()
            st.error("Session expired. Please log in again.")
            st.rerun()
            
        if r.status_code == 200:
            data = r.json()
            # Handle cases where backend returns {"records": [...]} or just [...]
            return data.get("records", data) if isinstance(data, dict) else data
        
        st.sidebar.error(f"MongoDB Fetch Failed: {r.status_code}")
        return []
    
    except requests.exceptions.ConnectionError:
        st.sidebar.warning("Unable to reach the database server.")
        return []
    except Exception as e:
        st.sidebar.error(f"Database Error: {str(e)}")
        return []
def health_check():
    try:
        # simple ping to backend
        return {"status": "ok"}
    except Exception:
        return {"status": "error"}    