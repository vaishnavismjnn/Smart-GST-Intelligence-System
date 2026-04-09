# --- file: pages/upload.py ---
import streamlit as st
import time
from utils.api import process_invoice
from utils.auth import is_authenticated
from components.cards import result_card
from components.illustrations import upload_illustration, render_illustration

ALLOWED_TYPES = ["png", "jpg", "jpeg", "webp", "bmp", "tiff"]

PIPELINE = [
    ("📡", "Network",   "Establishing secure link to Render"),
    ("🔍", "OCR Engine", "Extracting Tesseract neural data"),
    ("⚖️", "Validator",  "Cross-referencing GSTIN & Totals"),
    ("🛡️", "Archiver",   "Syncing to Cloudinary & MongoDB"),
]


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
    <div style="margin-bottom:1.5rem; padding: 0 10px;">
        <div class="step-indicator">{dots}</div>
        <div style="display:flex; justify-content:space-between; margin-top:0.6rem;">
            {''.join(f'''<span style="font-size:0.6rem; font-weight:600;
                                   color:{"#00D4AA" if i <= active_step else "#4A5568"};
                                   text-transform:uppercase; letter-spacing:0.05em;
                                   flex:1; text-align:center;">{l}</span>'''
                      for i, (_, l, _) in enumerate(PIPELINE))}
        </div>
    </div>
    """, unsafe_allow_html=True)


def show():
    if not is_authenticated():
        st.warning("Authentication required. Please sign in to access the upload portal.")
        return

    st.markdown("""
    <div class="page-header">
        <div class="page-title">📤 Document Ingestion</div>
        <div class="page-sub">
            AI-powered OCR gateway for real-time GST validation and cloud archival.
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_left, col_right = st.columns([1, 1.1], gap="large")

    # ---------------- LEFT PANEL ----------------
    with col_left:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Source Document</div>', unsafe_allow_html=True)

        uploaded_file = st.file_uploader(
            "Drop invoice",
            type=ALLOWED_TYPES,
            label_visibility="collapsed",
            key="invoice_uploader"
        )

        pills = "".join([
            f'<span style="background:rgba(0,212,170,0.05); border:1px solid rgba(0,212,170,0.1); border-radius:4px; padding:2px 6px; font-size:0.6rem; color:#8892B0; margin-right:4px;">{t.upper()}</span>'
            for t in ALLOWED_TYPES
        ])

        st.markdown(
            f'<div style="display:flex; flex-wrap:wrap; gap:0.2rem; margin-top:0.6rem; justify-content:center;">{pills}</div>',
            unsafe_allow_html=True
        )

        if uploaded_file:
            st.session_state["uploaded_file"] = uploaded_file

            st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)
            st.markdown('<div class="section-title" style="font-size:0.7rem; opacity:0.7;">Pre-upload Preview</div>', unsafe_allow_html=True)

            st.image(uploaded_file, use_container_width=True)
            st.success("File ready for processing 🚀")

            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.02); border:1px solid var(--card-border); border-radius:10px; padding:1rem; margin-top:1rem;">
                <div style="display:grid; grid-template-columns:1.5fr 1fr 1fr; gap:1rem;">
                    <div>
                        <div style="color:#4A5568; font-size:0.6rem;">Filename</div>
                        <div style="color:#EDF2F7;">{uploaded_file.name}</div>
                    </div>
                    <div>
                        <div style="color:#4A5568; font-size:0.6rem;">Payload</div>
                        <div style="color:#EDF2F7;">{uploaded_file.size / 1024:.1f} KB</div>
                    </div>
                    <div>
                        <div style="color:#4A5568; font-size:0.6rem;">Format</div>
                        <div style="color:#00D4AA;">
                            {(uploaded_file.type.split('/')[-1].upper() if uploaded_file.type else "UNKNOWN")}
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            if st.button("⚡ EXECUTE PIPELINE", use_container_width=True):

                progress_placeholder = st.empty()

                for i in range(len(PIPELINE)):
                    with progress_placeholder.container():
                        _step_indicator(i)
                        st.info(PIPELINE[i][2])
                    time.sleep(0.6)

                with st.spinner("Processing invoice..."):
                    try:
                        status, data = process_invoice(
                            uploaded_file.getvalue(),
                            uploaded_file.name
                        )
                    except Exception as e:
                        st.error(f"API Error: {str(e)}")
                        return

                if status == 200:
                    st.session_state["last_result"] = data
                    st.success("Processing complete ✅")
                    st.rerun()
                else:
                    st.error(f"Processing failed (Status {status})")
                    st.write("Response:", data)

        st.markdown('</div>', unsafe_allow_html=True)

    # ---------------- RIGHT PANEL ----------------
    with col_right:
        last = st.session_state.get("last_result")
        uploaded_file = st.session_state.get("uploaded_file")

        if last is None:
            st.markdown("Waiting for upload...")

        elif last:
            result_card(last)

            extracted = last.get("extracted", {})
            validation = extracted.get("validation", {}) or {}

            result_text = f"""
=== GST Invoice Extraction Summary ===

Merchant      : {extracted.get('MERCHANT') or '—'}
GSTIN         : {extracted.get('GSTIN') or '—'}
Invoice No.   : {extracted.get('INVOICE_NO') or '—'}
Invoice Date  : {extracted.get('INVOICE_DATE') or '—'}

Total Amount  : {extracted.get('TOTAL_AMOUNT') or '—'}
Taxable Amount: {extracted.get('TAXABLE_AMOUNT') or '—'}
GST Amount    : {extracted.get('GST_AMOUNT') or '—'}

GSTIN Valid   : {'Yes' if validation.get('gst_valid') else 'No'}
Amounts Match : {'Yes' if validation.get('amounts_match') else 'No'}

Record ID     : {last.get('record_id') or '—'}
"""

            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Export Results</div>', unsafe_allow_html=True)

            st.code(result_text, language="text")

            st.download_button(
                label="📥 Download Results",
                data=result_text,
                file_name="gst_results.txt",
                mime="text/plain",
                use_container_width=True
            )

            st.markdown('</div>', unsafe_allow_html=True)