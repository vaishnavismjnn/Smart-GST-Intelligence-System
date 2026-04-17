## Smart GST Intelligence System AI-Powered Financial Orchestration and OCR Extraction for MSMEs

## EXECUTIVE SUMMARY AND PROBLEM STATEMENT
Small business owners and freelancers currently operate within a "manual paper trap." Managing a high volume of physical receipts and digital images for tax purposes is time-consuming and prone to human error. When invoice details—such as GSTINs, taxable amounts, and vendor names—are entered manually into spreadsheets, the risk of data entry mistakes increases. This leads to severe financial discrepancies, specifically the loss of Input Tax Credit (ITC).

Furthermore, once these documents are filed, retrieving specific information or analyzing long-term business margins is nearly impossible without a centralized digital system. The Smart GST Intelligence System bridges this gap by converting physical paper into structured, actionable digital intelligence.

## DEEPEND PROJECT SCOPE
This system is strictly tailored for B2B (Business-to-Business) transactions where both the issuer and the receiver are GST-registered entities.

The scope includes:
Target Audience: Micro, Small, and Medium Enterprises (MSMEs), independent contractors, and freelance consultants.
Document Focus: Standardized tax invoices, purchase receipts, and digital bills.
Extraction Targets: Vendor Name, 15-digit GSTIN, Invoice Date, Taxable Amount, GST Breakdown (CGST/SGST/IGST), Total Value, and Line-Item Details.
Financial Objective: Automate the calculation of Net GST Liability (Output Tax minus Input Tax) to prevent overpayment and duplicate tax claims.

## SYSTEM ARCHITECTURE
The system operates on a modular, four-layer pipeline to ensure scalability and data integrity:

User Interaction Layer (Frontend): A Python-based web interface managing user authentication, file uploads (JPG/PNG/PDF), and real-time visual feedback.

Processing & Extraction Layer (AI Engine): The core intelligence layer utilizing OCR to digitize text, followed by a Large Language Model (LLM) to map raw text to structured JSON schemas.

Validation & Storage Layer (Backend): A verification engine that validates Indian GSTIN formats via regex, checks mathematical accuracy (Taxable + GST = Total), flags duplicates, and archives data securely.

Analytics & Output Layer (BI Tool): A business intelligence layer that transforms database queries into interactive financial charts and exports data for Chartered Accountants.

## CURRENT CAPABILITIES(IMPLEMENTED FEATURES)
The frontend shell and integration contracts are fully operational.

Secure Access: Local authentication system managing user sessions and secure login routing.

Premium User Interface: Dark-themed, glassmorphism UI built with custom CSS for a modern, enterprise-grade feel.

Multi-Format Ingestion: Robust upload interface accepting image files and PDFs.

Data Review Console: Visual confidence scoring system (Red/Orange/Green) highlighting the accuracy of extracted OCR data for user verification.

Business Intelligence Dashboard: Interactive visualizations detailing historical spending trends, category-wise breakdowns, and vendor-specific outgoings.

Audit Queues: Dedicated data tables highlighting low-confidence extractions and flagging potential duplicate invoice entries.

Data Portability: One-click CSV export functionality to generate accountant-ready MSME reports.

Invoice Generation Module: A dedicated form to compute tax distributions and structure standardized outbound invoices.

Offline Demo Mode: A fully populated mock-data state allowing UI/UX demonstration without backend connectivity.

## DEVELOPMENT ROADMAP(FEATURES TO IMPLEMENT)
Phase 1: Core Backend & OCR Engine
Develop the backend API using FastAPI to handle asynchronous image and text processing requests.
Integrate the base OCR pipeline (Tesseract/EasyOCR) for raw text extraction.
Build the mathematical and structural validation logic (15-digit GSTIN validation and basic data validation).

Phase 2: Artificial Intelligence Integration
Connect the extraction pipeline to an LLM (e.g., LLaMA 3.1 or GPT) using strict JSON output prompts to intelligently map OCR text to database fields.
Implement LayoutLMv3 for advanced spatial understanding of complex or unstandardized invoice layouts.
Develop the "Virtual CFO" module to analyze extracted data and provide automated advice on expense leakage and profit margins.

Phase 3: Storage & Advanced UI
Integrate MongoDB to replace local memory handling, enabling permanent, searchable digital archives.
Build the backend PDF generation engine to output downloadable, GST-compliant invoices.
Integrate the Web Speech API to enable hands-free, voice-activated database queries.
Upgrade the analytics dashboard to include predictive forecasting trendlines based on historical data.

## TECHNOLOGY STACK
Frontend: Streamlit, Plotly, Pandas  
Backend: FastAPI (development)  
Deployment: Render (hosting)  
AI: Tesseract, EasyOCR, LLM, LayoutLMv3  
Database: MongoDB  


## SYSTEM ARCHITECTURE
<img width="500" alt="WhatsApp Image 2026-04-17 at 3 10 53 PM" src="https://github.com/user-attachments/assets/bda28873-79ef-4693-90ad-7dd28118c4c1" />



<img width="400" alt="ChatGPT Image Apr 17, 2026, 02_53_26 PM" src="https://github.com/user-attachments/assets/fb239aae-6d4d-4d7a-93b7-6176403afd53" />
