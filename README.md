# ⚖️ LexGuard AI: Enterprise DPDP Compliance Auditor

<p align="center">
  <img src="https://raw.githubusercontent.com/sujalmeena7/lexguard-ai/main/assets/banner_screenshot.png" width="600" alt="LexGuard AI Banner">
</p>

**LexGuard AI** is a production-grade, hybrid SaaS platform designed to automate document compliance auditing against India's **Digital Personal Data Protection (DPDP) Act 2023**. By combining high-velocity LLM inference with a tiered RAG architecture, LexGuard transforms complex legal documents into actionable risk assessments in under 2 seconds.

---

## 🏗️ System Architecture

LexGuard AI utilizes a decoupled, high-performance architecture to ensure scalability and visual excellence:

- **Frontend (Vercel)**: A premium, static landing page built with modern CSS (glassmorphism) and a live audit widget.
- **API Engine (Render)**: A FastAPI-based backend managing lead capture, document analysis, and MongoDB persistence.
- **Audit Dashboard (Streamlit)**: An enterprise-grade data visualization platform for deep-dive compliance metrics and PDF report generation.
- **LLM Layer**: Llama 3 70B orchestrated via **Groq LPU™** for near-instantaneous inference.

---

## 🌟 Key Features

- **⚡ Sub-2s Audit Latency**: Optimized inference pipelines using Groq for real-time compliance feedback.
- **🛡️ Tiered RAG Strategy**: Utilizes `ParentDocumentRetriever` with ChromaDB to maintain context across large legal agreements.
- **📈 Compliance Scoring**: Proprietary algorithm generating a 0-100% risk score mapped to specific DPDP sections.
- **💎 Premium UI/UX**: Custom-themed "LexGuard Pro" dashboard featuring dark-mode aesthetics and Satoshi typography.
- **📊 Admin Portal**: Integrated lead management and audit tracking dashboard for enterprise administrators.
- **🔄 Fault Tolerance**: Implemented exponential backoff and retry logic using `Tenacity` to ensure 99.9% audit success rates.

---

## 🛠️ Tech Stack

| Component | Technology |
| :--- | :--- |
| **Inference** | Llama 3 (via Groq) |
| **Backend** | FastAPI, Python 3.14 |
| **Database** | MongoDB (Lead Storage), ChromaDB (Vector Store) |
| **Frontend** | Vanilla JS, CSS3 (Custom Glassmorphism), Streamlit |
| **Orchestration** | LangChain, Pydantic v2 |
| **Reliability** | Tenacity (Retry Logic), SlowAPI (Rate Limiting) |

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- MongoDB Instance
- Groq API Key

### Local Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/sujalmeena7/lexguard-ai.git
   cd lexguard-ai
   ```

2. **Backend Configuration:**
   Create a `.env` file in the `backend/` directory:
   ```env
   MONGO_URL=your_mongodb_uri
   DB_NAME=lexguard_db
   GROQ_API_KEY=your_groq_key
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install -r backend/requirements.txt
   ```

4. **Run the Platform:**
   - **Launch Dashboard**: `streamlit run app.py`
   - **Launch API**: `python backend/server.py`
   - **Launch Frontend**: `cd dashboard && npm run dev`

---

## 🛡️ Security & Reliability

- **Rate Limiting**: Enforced via `SlowAPI` to prevent API abuse.
- **Data Isolation**: Unique `analysis_id` tracking for all lead conversions.
- **Resilient AI**: All LLM calls wrap in a retry decorator to handle transient network failures gracefully.

---

## 💼 Business Inquiries

LexGuard AI is developed by **Sujal Meena**. For strategic partnerships, custom legal-tech implementations, or enterprise licensing, please reach out:

- **Email**: [meenasujal60@gmail.com](mailto:meenasujal60@gmail.com)
- **LinkedIn**: [Sujal Meena](https://linkedin.com/in/sujalmeena7)

---

<p align="center">Built with ❤️ for the Indian Startup Ecosystem.</p>
