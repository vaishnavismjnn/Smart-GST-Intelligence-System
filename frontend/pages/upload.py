# --- file: pages/upload.py ---
import streamlit as st
import time
from utils.api import process_invoice
from utils.auth import is_authenticated
from components.cards import result_card
from components.illustrations import upload_illustration, render_illustration

# ✅ NEW IMPORTS (modular utils)
from utils.invoice_utils import (
    compress_image,
    get_file_hash,
    get_cached_result,
    set_cached_result,
    get_file_size_kb,
    init_cache   # ✅ moved here (instead of inline import)
)

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
            # ❌ OLD (memory leak risk)
            # st.session_state["uploaded_file"] = uploaded_file

            # ✅ FIX: store only lightweight metadata
            st.session_state["uploaded_file_name"] = uploaded_file.name

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

                if not uploaded_file:
                    st.error("Please upload a file first.")
                    st.stop()

                # ✅ SAFE CACHE INIT
                init_cache(st.session_state)

                # FILE HASH
                try:
                    file_hash = get_file_hash(uploaded_file)
                except Exception as e:
                    st.error(f"File error: {str(e)}")
                    st.stop()

                # CACHE CHECK
                cached = get_cached_result(file_hash, st.session_state.cache)
                if cached:
                    st.success("⚡ Loaded instantly from cache")
                    st.session_state["last_result"] = cached
                    st.rerun()

                # FILE SIZE GUARD
                size_kb = get_file_size_kb(uploaded_file)
                if size_kb > 5000:
                    st.warning("File too large. Compressing may take longer...")

                progress_placeholder = st.empty()

                for i, step in enumerate(PIPELINE):
                    with progress_placeholder.container():
                        _step_indicator(i)
                        st.info(step[2])

                # COMPRESSION
                try:
                    with st.spinner("📦 Optimizing image..."):
                        compressed_image = compress_image(
                            uploaded_file,
                            max_size=(1024, 1024),
                            quality=70,
                            grayscale=False
                        )
                except Exception as e:
                    st.error(f"Compression failed: {str(e)}")
                    st.stop()

                # ✅ API CALL (SAFE RESPONSE HANDLING)
                with st.spinner("Processing invoice..."):
                    retries = 2
                    response = None

                    for attempt in range(retries):
                        try:
                            response = process_invoice(
                                compressed_image.getvalue(),
                                uploaded_file.name
                            )
                            break
                        except Exception as e:
                            if attempt == retries - 1:
                                st.error(f"API Error: {str(e)}")
                                st.stop()
                            time.sleep(1)

                    # ✅ CRITICAL FIX (prevents crash)
                    if not isinstance(response, tuple) or len(response) != 2:
                        st.error("Invalid API response")
                        st.stop()

                    status, data = response

                # RESPONSE HANDLING
                if status == 200 and data:

                    set_cached_result(file_hash, data, st.session_state.cache)

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

        if last is None:
            # Right panel empty state — illustration imported at top of file,
            # previously imported but never called (dead import fixed here).
            st.markdown('<div class="glass-card" style="text-align:center; padding:3rem 1.5rem;">',
                        unsafe_allow_html=True)
            render_illustration(
                upload_illustration(),
                "Upload an invoice on the left to see extracted data here"
            )
            st.markdown("""
            <div style="margin-top:1rem;">
                <div style="color:#A0AEC0; font-size:0.82rem; font-weight:600;">
                    Waiting for document…
                </div>
                <div style="color:#4A5568; font-size:0.75rem; margin-top:0.3rem;">
                    Results will appear here after pipeline completes
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

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