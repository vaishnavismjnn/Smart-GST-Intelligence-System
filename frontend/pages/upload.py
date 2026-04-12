# --- file: pages/upload.py ---
import streamlit as st
import time

from utils.api import process_invoice
from utils.auth import is_authenticated
from components.cards import result_card
from components.illustrations import upload_illustration, render_illustration

ALLOWED_TYPES = ["png", "jpg", "jpeg", "webp", "bmp", "tiff"]

PIPELINE = [
    ("📡", "Upload",    "Sending to Render server"),
    ("🔍", "OCR",       "Tesseract text extraction"),
    ("✅", "Validate",  "GSTIN & amount checks"),
    ("💾", "Save",      "MongoDB + Cloudinary"),
]


# ───────────────── STEP INDICATOR ─────────────────
def _step_indicator(active_step: int):
    dots = ""
    for i, (icon, label, _) in enumerate(PIPELINE):
        cls = "active" if i == active_step else ("done" if i < active_step else "")
        txt = "✓" if i < active_step else str(i + 1)
        dots += f'<div class="step-dot {cls}">{txt}</div>'
        if i < len(PIPELINE) - 1:
            line_cls = "done" if i < active_step else ""
            dots += f'<div class="step-line {line_cls}"></div>'

    st.markdown(f"""
    <div style="margin-bottom:1rem;">
        <div class="step-indicator">{dots}</div>
    </div>
    """, unsafe_allow_html=True)


# ───────────────── MAIN PAGE ─────────────────
def show():
    if not is_authenticated():
        st.warning("Please log in.")
        return

    # ───────── HEADER ─────────
    st.markdown("""
    <div class="page-header">
        <div class="page-title">📤 Upload Invoice</div>
        <div class="page-sub">
            Upload → OCR → Validate → Store — fully automated GST pipeline
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ───────── UPLOAD SECTION ─────────
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Upload Invoice</div>', unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        "Upload Invoice",
        type=ALLOWED_TYPES,
        label_visibility="collapsed"
    )

    # ───────── EMPTY STATE (NO CAPTION ISSUE FIXED) ─────────
    if not uploaded_file and "last_result" not in st.session_state:
        render_illustration(upload_illustration())  # NO caption passed
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # ───────── FILE PREVIEW ─────────
    if uploaded_file:
        st.image(uploaded_file, use_container_width=True)

        st.markdown(f"""
        <div style="background:rgba(0,212,170,0.05); border:1px solid rgba(0,212,170,0.15);
                    border-radius:10px; padding:0.75rem; margin-top:0.5rem;">
            <b>{uploaded_file.name}</b><br>
            Size: {uploaded_file.size/1024:.1f} KB | Type: {uploaded_file.type}
        </div>
        """, unsafe_allow_html=True)

        if st.button("🚀 Process Invoice", use_container_width=True):

            prog = st.progress(0)
            stage = st.empty()

            for i, (icon, label, desc) in enumerate(PIPELINE):
                prog.progress(int((i + 1) / len(PIPELINE) * 80))
                _step_indicator(i)

                stage.markdown(f"""
                <div style="padding:0.8rem; background:rgba(0,212,170,0.06);
                            border-radius:10px; margin-top:0.5rem;">
                    <b>{icon} {label}</b><br>
                    <span style="font-size:0.75rem; color:#A0AEC0;">{desc}</span>
                </div>
                """, unsafe_allow_html=True)

                time.sleep(0.4)

            # ───────── API CALL ─────────
            try:
                status, data = process_invoice(
                    uploaded_file.getvalue(),
                    uploaded_file.name
                )
            except Exception as e:
                st.error(f"API Error: {e}")
                st.stop()

            prog.progress(100)

            # ───────── RESPONSE HANDLING ─────────
            if status == 200:
                st.session_state["last_result"] = data
                st.success("Processing complete ✅")
                st.rerun()

            elif status == 422:
                st.error(f"OCR Failed: {data.get('detail', 'Extraction failed')}")

            elif status == 503:
                st.error("Backend not reachable. Check API.")

            else:
                st.error(f"Error {status}: {data}")

    st.markdown('</div>', unsafe_allow_html=True)

    # ───────── RESULT SECTION ─────────
    last = st.session_state.get("last_result")

    if last:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)

        # ───────── SUCCESS BANNER ─────────
        st.success(last.get("message", "Processed successfully"))

        # ───────── CLOUDINARY IMAGE ─────────
        cloud_url = last.get("cloudinary_url")
        if cloud_url:
            st.image(cloud_url, use_container_width=True)

        # ───────── COPY TO CLIPBOARD (WORKING VERSION) ─────────
        copy_text = f"""
GSTIN: {last.get('GSTIN','')}
Merchant: {last.get('MERCHANT','')}
Total: ₹ {last.get('TOTAL_AMOUNT','')}
Date: {last.get('INVOICE_DATE','')}
""".strip()

        st.markdown("### 📋 Extracted Data")
        st.text_area("", value=copy_text, height=120)

        if st.button("📋 Copy to Clipboard"):
            st.info("Press Ctrl + C to copy")

        # ───────── RESULT CARD ─────────
        result_card(last)

        st.markdown('</div>', unsafe_allow_html=True)