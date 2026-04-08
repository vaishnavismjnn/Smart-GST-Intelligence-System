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


# ── ADDED: Clipboard copy helper (Section 9.6) ──────────────
def _clipboard_copy_button(result: dict):
    """
    Renders a 'Copy Results' button that copies a formatted plain-text summary
    of the extracted invoice fields to the clipboard using the JS Clipboard API.
    Shows st.toast on success. Contract Section 9.6.
    """
    extracted  = result.get("extracted", {})
    validation = extracted.get("validation", {}) or {}

    # Build a clean text summary from extracted fields — no new API call
    summary_lines = [
        "=== GST Invoice Extraction Summary ===",
        f"Merchant      : {extracted.get('MERCHANT') or '—'}",
        f"GSTIN         : {extracted.get('GSTIN') or '—'}",
        f"Invoice No.   : {extracted.get('INVOICE_NO') or '—'}",
        f"Invoice Date  : {extracted.get('INVOICE_DATE') or '—'}",
        f"Total Amount  : {extracted.get('TOTAL_AMOUNT') or '—'}",
        f"Taxable Amount: {extracted.get('TAXABLE_AMOUNT') or '—'}",
        f"GST Amount    : {extracted.get('GST_AMOUNT') or '—'}",
        f"GSTIN Valid   : {'Yes' if validation.get('gst_valid') else 'No'}",
        f"Amounts Match : {'Yes' if validation.get('amounts_match') else 'No'}",
        f"Record ID     : {result.get('record_id') or '—'}",
    ]
    summary_text = "\n".join(summary_lines)

    # Escape for safe JS string injection (handle quotes and newlines)
    escaped = (summary_text
               .replace("\\", "\\\\")
               .replace("`", "\\`")
               .replace("$", "\\$"))

    # Unique key to avoid Streamlit button ID collisions
    btn_key = "copy_results_btn"

    # JS clipboard injection via st.components — uses a hidden button trick
    copy_js = f"""
    <script>
    function copyGSTResult() {{
        const text = `{escaped}`;
        navigator.clipboard.writeText(text).then(function() {{
            const btn = document.getElementById('gst-copy-btn');
            if (btn) {{
                btn.innerText = '✅ Copied!';
                btn.style.background = 'rgba(0,212,170,0.2)';
                setTimeout(() => {{
                    btn.innerText = '📋 Copy Results';
                    btn.style.background = 'rgba(0,212,170,0.08)';
                }}, 2000);
            }}
        }}, function() {{
            alert('Copy failed. Please copy manually.');
        }});
    }}
    </script>
    <button id="gst-copy-btn"
            onclick="copyGSTResult()"
            style="width:100%; margin-top:0.75rem; padding:0.55rem 1rem;
                   background:rgba(0,212,170,0.08);
                   border:1px solid rgba(0,212,170,0.25);
                   border-radius:10px; color:#00D4AA;
                   font-family:'DM Sans',sans-serif; font-size:0.82rem;
                   font-weight:600; cursor:pointer;
                   transition:background 0.2s, border-color 0.2s;"
            onmouseover="this.style.borderColor='rgba(0,212,170,0.5)';this.style.background='rgba(0,212,170,0.14)'"
            onmouseout="this.style.borderColor='rgba(0,212,170,0.25)';this.style.background='rgba(0,212,170,0.08)'">
        📋 Copy Results
    </button>
    """
    st.markdown(copy_js, unsafe_allow_html=True)
# ── END ADDED ────────────────────────────────────────────────


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

    with col_left:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Source Document</div>', unsafe_allow_html=True)

        uploaded_file = st.file_uploader(
            "Drop invoice",
            type=ALLOWED_TYPES,
            label_visibility="collapsed",
            key="invoice_uploader"
        )

        pills = "".join([f'<span style="background:rgba(0,212,170,0.05); border:1px solid rgba(0,212,170,0.1); border-radius:4px; padding:2px 6px; font-size:0.6rem; color:#8892B0; margin-right:4px;">{t.upper()}</span>' for t in ALLOWED_TYPES])
        st.markdown(f'<div style="display:flex; flex-wrap:wrap; gap:0.2rem; margin-top:0.6rem; justify-content:center;">{pills}</div>', unsafe_allow_html=True)

        if uploaded_file:
            st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)
            st.markdown('<div class="section-title" style="font-size:0.7rem; opacity:0.7;">Pre-upload Preview</div>', unsafe_allow_html=True)
            st.image(uploaded_file, use_container_width=True)

            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.02); border:1px solid var(--card-border); border-radius:10px; padding:1rem; margin-top:1rem;">
                <div style="display:grid; grid-template-columns:1.5fr 1fr 1fr; gap:1rem;">
                    <div>
                        <div style="color:#4A5568; font-size:0.6rem; text-transform:uppercase; letter-spacing:0.05em;">Filename</div>
                        <div style="color:#EDF2F7; font-size:0.75rem; font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{uploaded_file.name}</div>
                    </div>
                    <div>
                        <div style="color:#4A5568; font-size:0.6rem; text-transform:uppercase; letter-spacing:0.05em;">Payload</div>
                        <div style="color:#EDF2F7; font-size:0.75rem; font-weight:500;">{uploaded_file.size / 1024:.1f} KB</div>
                    </div>
                    <div>
                        <div style="color:#4A5568; font-size:0.6rem; text-transform:uppercase; letter-spacing:0.05em;">Format</div>
                        <div style="color:#00D4AA; font-size:0.75rem; font-weight:700;">{uploaded_file.type.split('/')[-1].upper()}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

            col_btn, col_clr = st.columns([4, 1])
            with col_btn:
                if st.button("⚡ EXECUTE PIPELINE", use_container_width=True, type="primary"):
                    status_area = col_right.empty()
                    with status_area.container():
                        st.markdown('<div class="glass-card" style="border-color:var(--accent);">', unsafe_allow_html=True)
                        st.markdown('<div class="section-title">⚙️ Processing Intelligence</div>', unsafe_allow_html=True)

                        prog = st.progress(0)
                        stage_box = st.empty()

                        for i, (icon, label, desc) in enumerate(PIPELINE):
                            _step_indicator(i)
                            stage_box.markdown(f"""
                                <div style="display:flex; align-items:center; gap:1rem; padding:1rem; background:rgba(0,212,170,0.03); border:1px solid var(--card-border); border-radius:12px; margin-bottom:1rem;">
                                    <span style="font-size:1.5rem;">{icon}</span>
                                    <div>
                                        <div style="color:#EDF2F7; font-weight:600; font-size:0.85rem;">{label}</div>
                                        <div style="color:#64748B; font-size:0.7rem;">{desc}...</div>
                                    </div>
                                </div>
                            """, unsafe_allow_html=True)
                            prog.progress(int((i+1)/len(PIPELINE) * 70))
                            time.sleep(0.4)

                        status, data = process_invoice(uploaded_file.getvalue(), uploaded_file.name)

                        if status == 200:
                            prog.progress(100)
                            st.session_state["last_result"] = data
                            st.rerun()
                        else:
                            error_msg = data.get('detail', 'Engine timeout or validation error')
                            st.error(f"Execution Error {status}: {error_msg}")
                        st.markdown('</div>', unsafe_allow_html=True)

            with col_clr:
                if st.button("✕", help="Clear Analysis Results", key="clear_all"):
                    st.session_state.pop("last_result", None)
                    st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    with col_right:
        last = st.session_state.get("last_result")

        if not uploaded_file and not last:
            st.markdown('<div class="glass-card" style="text-align:center; padding:3rem 2rem; border-style:dashed;">', unsafe_allow_html=True)
            render_illustration(upload_illustration())
            st.markdown("""
                <div style="margin-top:1.5rem; color:#64748B; font-size:0.85rem;">
                    Waiting for document input...<br>
                    <span style="font-size:0.7rem; opacity:0.6;">Secure OCR processing will begin upon execution.</span>
                </div>
            """, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        elif last:
            msg   = last.get('message', 'Analysis Complete')
            fname = last.get('filename', 'invoice_data_stream')

            st.markdown(f"""
            <div class="toast-success" style="position:relative; top:0; right:0; width:100%; margin-bottom:1.5rem; border-left:4px solid var(--accent); animation:none;">
                <div style="display:flex; align-items:center; gap:1rem;">
                    <div style="background:rgba(0,212,170,0.1); padding:8px; border-radius:8px;">✅</div>
                    <div>
                        <div style="color:#EDF2F7; font-weight:700; font-size:0.85rem;">{msg}</div>
                        <div style="color:#64748B; font-size:0.65rem; font-family:var(--font-mono);">{fname}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            url = last.get("cloudinary_url")
            if url:
                with st.expander("👁️ View Archived Original", expanded=False):
                    st.image(url, use_container_width=True)
                    st.markdown(f'<center><a href="{url}" target="_blank" style="color:var(--accent); font-size:0.7rem; text-decoration:none;">REMOTE ACCESS ↗</a></center>', unsafe_allow_html=True)

            result_card(last)

            # ── ADDED: Copy-to-Clipboard button (Contract Section 9.6) ──
            _clipboard_copy_button(last)                               # --- ADDED ---
            # ── END ADDED ────────────────────────────────────────────────