# --- file: components/illustrations.py ---
# All illustrations are inline SVGs — no external images needed.
# Domain-relevant: invoices, tax, analytics, security, India map grid.

import streamlit as st

def gst_hero_illustration():
    """Hero SVG for login page — floating invoice with data streams."""
    return """
    <svg viewBox="0 0 420 320" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:420px;">
      <defs>
        <linearGradient id="cardGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" style="stop-color:#0F1C34;stop-opacity:1"/>
          <stop offset="100%" style="stop-color:#0B1628;stop-opacity:1"/>
        </linearGradient>
        <linearGradient id="accentLine" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" style="stop-color:#00D4AA;stop-opacity:1"/>
          <stop offset="100%" style="stop-color:#00D4AA;stop-opacity:0"/>
        </linearGradient>
        <linearGradient id="glowGrad" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" style="stop-color:#00D4AA;stop-opacity:0.2"/>
          <stop offset="100%" style="stop-color:#00D4AA;stop-opacity:0"/>
        </linearGradient>
        <filter id="glow">
          <feGaussianBlur stdDeviation="3" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        <style>
          .float1 { animation: svgFloat1 4s ease-in-out infinite; transform-origin: 210px 160px; }
          .float2 { animation: svgFloat2 5s ease-in-out infinite 0.5s; transform-origin: 320px 80px; }
          .float3 { animation: svgFloat3 6s ease-in-out infinite 1s; transform-origin: 90px 240px; }
          .dash-anim { stroke-dasharray: 6 4; animation: dashMove 2s linear infinite; }
          @keyframes svgFloat1 { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-10px)} }
          @keyframes svgFloat2 { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-7px)} }
          @keyframes svgFloat3 { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-12px)} }
          @keyframes dashMove  { to { stroke-dashoffset: -20; } }
          .blink { animation: blinkAnim 2s step-end infinite; }
          @keyframes blinkAnim { 0%,100%{opacity:1} 50%{opacity:0.3} }
          .scan  { animation: scanLine 3s ease-in-out infinite; }
          @keyframes scanLine { 0%,100%{transform:translateY(0)} 50%{transform:translateY(80px)} }
        </style>
      </defs>

      <!-- Background glow -->
      <ellipse cx="210" cy="160" rx="180" ry="120" fill="url(#glowGrad)" opacity="0.5"/>

      <!-- Main invoice card -->
      <g class="float1">
        <rect x="100" y="60" width="220" height="200" rx="14"
              fill="url(#cardGrad)" stroke="#00D4AA" stroke-width="1" stroke-opacity="0.3"/>
        <!-- Top accent bar -->
        <rect x="100" y="60" width="220" height="3" rx="2" fill="#00D4AA" opacity="0.7"/>
        <!-- GST logo area -->
        <rect x="116" y="80" width="40" height="40" rx="8" fill="rgba(0,212,170,0.1)"
              stroke="#00D4AA" stroke-width="1" stroke-opacity="0.4"/>
        <text x="136" y="105" fill="#00D4AA" font-size="16" font-weight="bold"
              text-anchor="middle" font-family="DM Sans, sans-serif">₹</text>
        <!-- Invoice title -->
        <text x="168" y="96" fill="#EDF2F7" font-size="10" font-weight="600"
              font-family="DM Sans, sans-serif">TAX INVOICE</text>
        <text x="168" y="110" fill="#A0AEC0" font-size="7.5"
              font-family="DM Mono, monospace">INV/2024/00847</text>
        <!-- GSTIN row -->
        <rect x="116" y="134" width="188" height="1" fill="#263045"/>
        <text x="116" y="150" fill="#A0AEC0" font-size="7" font-family="DM Mono,monospace">GSTIN</text>
        <text x="116" y="162" fill="#00D4AA" font-size="8" font-family="DM Mono,monospace"
              font-weight="500">27AABCC5544D1ZK</text>
        <!-- Merchant -->
        <text x="116" y="178" fill="#A0AEC0" font-size="7" font-family="DM Mono,monospace">MERCHANT</text>
        <text x="116" y="190" fill="#EDF2F7" font-size="8.5" font-family="DM Sans,sans-serif"
              font-weight="500">CloudPrint Media</text>
        <!-- Amount row -->
        <rect x="116" y="204" width="188" height="1" fill="#263045"/>
        <text x="116" y="220" fill="#A0AEC0" font-size="7" font-family="DM Mono,monospace">TOTAL AMOUNT</text>
        <text x="304" y="220" fill="#00D4AA" font-size="12" font-weight="700"
              text-anchor="end" font-family="DM Sans,sans-serif">₹12,490.35</text>
        <!-- Valid badge -->
        <rect x="116" y="232" width="58" height="18" rx="9"
              fill="rgba(0,212,170,0.12)" stroke="#00D4AA" stroke-width="0.7" stroke-opacity="0.5"/>
        <text x="145" y="244" fill="#00D4AA" font-size="7" font-weight="700"
              text-anchor="middle" font-family="DM Sans,sans-serif">✓ VALID</text>
      </g>

      <!-- Mini floating card: GST breakdown -->
      <g class="float2">
        <rect x="290" y="50" width="110" height="80" rx="10"
              fill="#0F1C34" stroke="#00D4AA" stroke-width="0.8" stroke-opacity="0.3"/>
        <rect x="290" y="50" width="110" height="2.5" rx="1.5" fill="#F5C842" opacity="0.7"/>
        <text x="300" y="68" fill="#A0AEC0" font-size="7" font-family="DM Mono,monospace">GST BREAKDOWN</text>
        <text x="300" y="82" fill="#EDF2F7" font-size="7.5" font-family="DM Sans,sans-serif">CGST 9%</text>
        <text x="388" y="82" fill="#00D4AA" font-size="7.5" text-anchor="end"
              font-family="DM Mono,monospace">₹423.68</text>
        <text x="300" y="96" fill="#EDF2F7" font-size="7.5" font-family="DM Sans,sans-serif">SGST 9%</text>
        <text x="388" y="96" fill="#00D4AA" font-size="7.5" text-anchor="end"
              font-family="DM Mono,monospace">₹423.67</text>
        <rect x="300" y="104" width="88" height="0.5" fill="#263045"/>
        <text x="300" y="116" fill="#F5C842" font-size="8" font-weight="700"
              font-family="DM Sans,sans-serif">Total GST</text>
        <text x="388" y="116" fill="#F5C842" font-size="8" font-weight="700"
              text-anchor="end" font-family="DM Mono,monospace">₹847.35</text>
      </g>

      <!-- Mini floating card: Validation -->
      <g class="float3">
        <rect x="20" y="200" width="100" height="70" rx="10"
              fill="#0F1C34" stroke="#00D4AA" stroke-width="0.8" stroke-opacity="0.3"/>
        <rect x="20" y="200" width="100" height="2.5" rx="1.5" fill="#00D4AA" opacity="0.6"/>
        <text x="70" y="218" fill="#A0AEC0" font-size="7" text-anchor="middle"
              font-family="DM Mono,monospace">VALIDATION</text>
        <circle cx="36" cy="234" r="5" fill="rgba(0,212,170,0.2)" stroke="#00D4AA" stroke-width="1"/>
        <text x="37" y="237" fill="#00D4AA" font-size="7" text-anchor="middle">✓</text>
        <text x="47" y="237" fill="#EDF2F7" font-size="7.5" font-family="DM Sans,sans-serif">GSTIN Valid</text>
        <circle cx="36" cy="250" r="5" fill="rgba(0,212,170,0.2)" stroke="#00D4AA" stroke-width="1"/>
        <text x="37" y="253" fill="#00D4AA" font-size="7" text-anchor="middle">✓</text>
        <text x="47" y="253" fill="#EDF2F7" font-size="7.5" font-family="DM Sans,sans-serif">Amounts Match</text>
      </g>

      <!-- Data stream lines -->
      <line x1="230" y1="160" x2="295" y2="100" stroke="#00D4AA" stroke-width="0.7"
            stroke-opacity="0.3" class="dash-anim"/>
      <line x1="160" y1="240" x2="100" y2="248" stroke="#00D4AA" stroke-width="0.7"
            stroke-opacity="0.3" class="dash-anim"/>

      <!-- Floating data nodes -->
      <circle cx="298" cy="98" r="3" fill="#00D4AA" opacity="0.6" filter="url(#glow)"/>
      <circle cx="99" cy="248" r="3" fill="#00D4AA" opacity="0.6" filter="url(#glow)"/>
      <circle cx="228" cy="162" r="2" fill="#F5C842" opacity="0.5"/>
    </svg>
    """

def upload_illustration():
    """SVG for upload page — document scanning with OCR beams."""
    return """
    <svg viewBox="0 0 300 240" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:300px;">
      <defs>
        <linearGradient id="docGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" style="stop-color:#0F1C34"/>
          <stop offset="100%" style="stop-color:#0B1628"/>
        </linearGradient>
        <style>
          .scan-beam { animation: beamScan 2.5s ease-in-out infinite; }
          @keyframes beamScan {
            0%   { transform: translateY(0);    opacity: 0.8; }
            50%  { transform: translateY(100px); opacity: 0.4; }
            100% { transform: translateY(0);    opacity: 0.8; }
          }
          .ocr-char { animation: charPop 0.3s ease both; }
          .upload-arrow { animation: arrowBounce 1.5s ease-in-out infinite; }
          @keyframes arrowBounce {
            0%,100% { transform: translateY(0); }
            50%      { transform: translateY(-6px); }
          }
        </style>
      </defs>

      <!-- Document -->
      <rect x="60" y="20" width="140" height="180" rx="12"
            fill="url(#docGrad)" stroke="#00D4AA" stroke-width="1" stroke-opacity="0.3"/>
      <rect x="60" y="20" width="140" height="3" rx="2" fill="#00D4AA" opacity="0.6"/>

      <!-- Doc lines -->
      <rect x="80" y="44" width="100" height="6" rx="3" fill="rgba(0,212,170,0.15)"/>
      <rect x="80" y="58" width="70" height="4" rx="2" fill="rgba(255,255,255,0.06)"/>
      <rect x="80" y="76" width="100" height="3" rx="2" fill="rgba(255,255,255,0.05)"/>
      <rect x="80" y="84" width="85" height="3" rx="2" fill="rgba(255,255,255,0.05)"/>
      <rect x="80" y="96" width="100" height="3" rx="2" fill="rgba(255,255,255,0.05)"/>
      <rect x="80" y="104" width="60" height="3" rx="2" fill="rgba(255,255,255,0.05)"/>
      <rect x="80" y="120" width="100" height="10" rx="4" fill="rgba(0,212,170,0.08)"
            stroke="#00D4AA" stroke-width="0.5" stroke-opacity="0.4"/>
      <text x="130" y="129" fill="#00D4AA" font-size="6.5" text-anchor="middle"
            font-family="DM Mono,monospace">27AABCC5544D1ZK</text>
      <rect x="80" y="148" width="100" height="3" rx="2" fill="rgba(255,255,255,0.05)"/>
      <rect x="80" y="158" width="65" height="3" rx="2" fill="rgba(255,255,255,0.05)"/>
      <rect x="80" y="172" width="100" height="8" rx="3" fill="rgba(245,200,66,0.1)"
            stroke="#F5C842" stroke-width="0.5" stroke-opacity="0.5"/>
      <text x="130" y="179" fill="#F5C842" font-size="7" text-anchor="middle"
            font-family="DM Sans,sans-serif" font-weight="600">₹ 12,490.35</text>

      <!-- Scan beam -->
      <rect x="60" y="20" width="140" height="8" rx="2"
            fill="rgba(0,212,170,0.12)" class="scan-beam"/>
      <line x1="60" y1="24" x2="200" y2="24" stroke="#00D4AA" stroke-width="1.5"
            stroke-opacity="0.5" class="scan-beam"/>

      <!-- Upload arrow on the right -->
      <g class="upload-arrow" transform="translate(240,80)">
        <circle cx="0" cy="0" r="28" fill="rgba(0,212,170,0.08)"
                stroke="#00D4AA" stroke-width="1" stroke-opacity="0.4"/>
        <text x="0" y="6" fill="#00D4AA" font-size="20" text-anchor="middle">↑</text>
      </g>

      <!-- OCR extracted tags -->
      <rect x="210" y="130" width="80" height="20" rx="6"
            fill="rgba(0,212,170,0.1)" stroke="#00D4AA" stroke-width="0.7" stroke-opacity="0.5"/>
      <text x="250" y="143" fill="#00D4AA" font-size="7" text-anchor="middle"
            font-family="DM Mono,monospace">OCR COMPLETE</text>

      <line x1="200" y1="140" x2="210" y2="140" stroke="#00D4AA" stroke-width="0.7"
            stroke-opacity="0.4" stroke-dasharray="3 2"/>
    </svg>
    """

def empty_records_illustration():
    """SVG for empty records state."""
    return """
    <svg viewBox="0 0 260 200" xmlns="http://www.w3.org/2000/svg"
         style="width:100%;max-width:260px;margin:0 auto;display:block;">
      <defs>
        <style>
          .pile-float { animation: pileFloat 4s ease-in-out infinite; transform-origin: 130px 100px; }
          @keyframes pileFloat { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-8px)} }
        </style>
      </defs>
      <g class="pile-float">
        <!-- Stack of invoice cards -->
        <rect x="70" y="70" width="120" height="90" rx="8" fill="#0F1C34"
              stroke="#263045" stroke-width="1" transform="rotate(-6,130,115)"/>
        <rect x="70" y="65" width="120" height="90" rx="8" fill="#0B1628"
              stroke="#263045" stroke-width="1" transform="rotate(-3,130,110)"/>
        <rect x="70" y="60" width="120" height="90" rx="8" fill="#0F1C34"
              stroke="rgba(0,212,170,0.2)" stroke-width="1"/>
        <rect x="70" y="60" width="120" height="3" rx="1.5" fill="#00D4AA" opacity="0.4"/>
        <rect x="85" y="75" width="90" height="5" rx="2.5" fill="rgba(0,212,170,0.12)"/>
        <rect x="85" y="86" width="65" height="3" rx="1.5" fill="rgba(255,255,255,0.05)"/>
        <rect x="85" y="94" width="90" height="3" rx="1.5" fill="rgba(255,255,255,0.04)"/>
        <!-- Big plus -->
        <circle cx="130" cy="116" r="18" fill="rgba(0,212,170,0.08)"
                stroke="rgba(0,212,170,0.25)" stroke-width="1.5" stroke-dasharray="4 3"/>
        <text x="130" y="122" fill="#00D4AA" font-size="20" text-anchor="middle"
              opacity="0.6">+</text>
      </g>
      <text x="130" y="170" fill="#A0AEC0" font-size="11" text-anchor="middle"
            font-family="DM Sans,sans-serif" font-weight="500">No invoices yet</text>
      <text x="130" y="185" fill="#4A5568" font-size="8.5" text-anchor="middle"
            font-family="DM Sans,sans-serif">Upload your first invoice to get started</text>
    </svg>
    """

def analytics_illustration():
    """Mini SVG bar chart for dashboard empty state."""
    return """
    <svg viewBox="0 0 200 120" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:200px;">
      <defs>
        <style>
          .bar1 { animation: growBar 1s ease 0.1s both; transform-origin: bottom; }
          .bar2 { animation: growBar 1s ease 0.2s both; transform-origin: bottom; }
          .bar3 { animation: growBar 1s ease 0.3s both; transform-origin: bottom; }
          .bar4 { animation: growBar 1s ease 0.4s both; transform-origin: bottom; }
          .bar5 { animation: growBar 1s ease 0.5s both; transform-origin: bottom; }
          @keyframes growBar {
            from { transform: scaleY(0); opacity: 0; }
            to   { transform: scaleY(1); opacity: 1; }
          }
        </style>
      </defs>
      <rect x="10" y="20" width="24" height="80" rx="5" fill="rgba(0,212,170,0.4)" class="bar1"/>
      <rect x="44" y="40" width="24" height="60" rx="5" fill="rgba(0,212,170,0.5)" class="bar2"/>
      <rect x="78" y="10" width="24" height="90" rx="5" fill="#00D4AA" class="bar3"/>
      <rect x="112" y="30" width="24" height="70" rx="5" fill="rgba(0,212,170,0.5)" class="bar4"/>
      <rect x="146" y="50" width="24" height="50" rx="5" fill="rgba(0,212,170,0.35)" class="bar5"/>
      <line x1="10" y1="105" x2="190" y2="105" stroke="rgba(255,255,255,0.08)" stroke-width="1"/>
    </svg>
    """

def render_illustration(svg_string: str, caption: str = ""):
    """Render an SVG illustration with optional caption."""
    st.markdown(f"""
    <div style="text-align:center; padding: 0.5rem 0;">
        {svg_string}
        {"" if not caption else f'<div style="color:#4A5568; font-size:0.75rem; margin-top:0.5rem;">{caption}</div>'}
    </div>
    """, unsafe_allow_html=True)