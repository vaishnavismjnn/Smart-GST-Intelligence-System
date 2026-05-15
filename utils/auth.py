# --- file: utils/auth.py ---
import streamlit as st

def is_authenticated() -> bool:
    """Checks if the user has a valid token and email in session state."""
    return bool(st.session_state.get("token") and st.session_state.get("user"))

def logout():
    """Clears all session data and redirects to login."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

def get_user_initials() -> str:
    """Generates a 2-letter avatar string from the user's email."""
    user = st.session_state.get("user", "")
    if not user:
        return "U"
    # Handles both 'john.doe@email.com' and 'john@email.com'
    name_part = user.split("@")[0].replace(".", " ")
    parts = name_part.split()
    initials = "".join(p[0].upper() for p in parts if p)
    return initials[:2] or "U"