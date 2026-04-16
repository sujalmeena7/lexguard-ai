# ⚖️ LexGuard AI: Enterprise DPDP Compliance Auditor

<p align="center">
  <img src="https://raw.githubusercontent.com/sujalmeena7/lexguard-ai/main/assets/banner_screenshot.png" width="600">
</p>

**LexGuard AI** is a high-precision, LLM-powered compliance engine designed to automate the auditing of legal contracts against India's **Digital Personal Data Protection (DPDP) Act 2023**.

By leveraging **RAG (Retrieval-Augmented Generation)** and **Llama 3 (via Groq)**, LexGuard transforms dense legal jargon into actionable risk scores and professional audit reports in seconds.

[🚀 View Live Demo](https://lexguard-ai-h5on.vercel.app/) | [📧 Request Enterprise Access](mailto:meenasujal60@gmail.com)

---

## 🌟 Key Features

* **⚡ Instant Legal Audits:** Upload any privacy policy or data-sharing agreement for a deep-scan against DPDP 2023 clauses.
* **📊 Compliance Health Score:** Visual gauges (powered by Plotly) that give an immediate "Red/Green" status on document safety.
* **🔒 Privacy-First Architecture:** Built using a private vector store (ChromaDB) ensuring sensitive legal data is never used for model training.
* **📄 Professional PDF Generation:** Export branded, board-ready compliance reports with one click (Premium feature).
* **🛡️ Secure Access Control:** Integrated "Gated Content" logic to protect high-value audit insights.

---

## 🛠️ The Tech Stack

| Layer | Technology |
| :--- | :--- |
| **Brain** | Llama 3 (Inference via **Groq** for < 2s latency) |
| **Orchestration** | LangChain (RAG Pipeline) |
| **Frontend** | Streamlit (Modern Dark-Mode UI) |
| **Vector DB** | ChromaDB (Local/Ephemeral Storage) |
| **Visualization** | Plotly & FPDF (Reporting) |

---

## 🛡️ Intellectual Property & Licensing

This repository serves as a **Technical Demonstration** of my capabilities in RAG (Retrieval-Augmented Generation) and Legal-Tech engineering. 

* **Proprietary Logic:** The core prompt engineering, compliance scoring algorithms, and PDF generation logic are the intellectual property of the developer (**Sujal Meena**).
* **Usage:** You are welcome to clone this repository for **personal educational purposes** or to review the code quality for hiring/partnership evaluations.
* **Restricted Use:** Commercial redistribution, white-labeling, or using this code to launch a competing service without written consent is strictly prohibited.

---

## 🛠️ Technical Architecture (High-Level)

For security and IP protection, the production environment variables (API Keys) and specific Vector Store weights are not included in this public repository. 

1.  **Ingestion:** Documents are processed via a custom PDF-to-Text pipeline.
2.  **Vectorization:** Text chunks are embedded and stored in an ephemeral **ChromaDB** instance.
3.  **Inference:** Queries are routed through **LangChain** to the **Llama 3 70B** model via the **Groq LPU™** Inference Engine.
4.  **Verification:** The "Premium Access" layer validates session state before unlocking the **FPDF-based** report generator.

---

## 🤝 Collaboration & Customization

If you are a legal firm or a developer interested in building a production-grade version of this tool with custom DPDP-specific datasets, please reach out via the contact details below.

---

## 💼 Business & Enterprise Inquiries

LexGuard AI is currently available for **Strategic Partnerships** and **Custom Legal-Tech Implementations**.

If you are a startup founder or legal firm looking to automate your DPDP 2023 compliance workflow, let's talk.

| | |
| :--- | :--- |
| **Developer** | Sujal Meena |
| **Contact** | [meenasujal60@gmail.com](mailto:meenasujal60@gmail.com) |
| **Response Time** | Within 2 hours |

---

<p align="center">Built with ❤️ for the Indian Startup Ecosystem.</p>
