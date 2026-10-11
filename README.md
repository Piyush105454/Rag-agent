# ⚡ Enterprise RAG Knowledge Assistant

A production-grade, zero-hallucination **Enterprise Retrieval-Augmented Generation (RAG) System** built with **FastAPI**, **PostgreSQL + pgvector**, **LangGraph**, **Groq (`openai/gpt-oss-120b`)**, and **Next.js 14**.

---

## 🌟 Key Highlights & Capabilities

- 🔒 **Row-Level RBAC Gating:** Vector queries enforce `access_group = ANY(:user_groups)` natively at the database level, preventing confidential data leakage across teams (General, Sales, Engineering, Product).
- 🎯 **Two-Stage Precision Retrieval:**
  - **Stage 1 (Coarse Retrieval):** `BAAI/bge-small-en-v1.5` embeddings (384-dim) with cosine similarity over HNSW index (`m=16, ef_construction=64`).
  - **Stage 2 (Fine Reranking):** `BAAI/bge-reranker-base` CrossEncoder with joint query-document self-attention.
- 🛡️ **Confidence Guardrail:** Calibrated confidence scoring short-circuits execution before invoking the LLM if the retrieved context does not meet the confidence threshold ($\ge 0.40$), eliminating hallucinations.
- ⚡ **Ultra-Low Latency Inference:** Powered by Groq's high-throughput LPU cloud (`openai/gpt-oss-120b`) with Server-Sent Events (SSE) streaming directly to the browser.
- 📑 **Multi-Format Ingestion:** Ingests PDF, PPTX, TXT, and Markdown while preserving document structure and tables.
- 💻 **Modern Glassmorphic UI:** Next.js 14 (App Router) interface featuring inline clickable source citation pills (`[Source: sales_policy.txt, p.1]`), confidence badges, and document directory sidebar.

---

## 🏗️ System Architecture

```text
┌────────────────────────────────────────────────────────┐
│              Next.js 14 Frontend (:3000)               │
│    • Real-Time Chat   • Source Pills   • Doc Sidebar   │
└───────────────────────────┬────────────────────────────┘
                            │ SSE Stream (POST /query)
                            ▼
┌────────────────────────────────────────────────────────┐
│             FastAPI Backend Orchestrator               │
│                                                        │
│  ┌──────────────────┐      ┌─────────────────────────┐ │
│  │ 1. Query Rewrite │ ───► │  2. RBAC Vector Search  │ │
│  └──────────────────┘      └───────────┬─────────────┘ │
│                                        ▼               │
│  ┌──────────────────┐      ┌─────────────────────────┐ │
│  │ 4. Conf. Guard   │ ◄─── │ 3. CrossEncoder Rerank  │ │
│  └────────┬─────────┘      └─────────────────────────┘ │
│           ▼ (If >= 0.40)                               │
│  ┌──────────────────┐                                  │
│  │ 5. Groq Stream   │                                  │
│  └──────────────────┘                                  │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│            PostgreSQL + pgvector (Docker)              │
│       • Table: chunks (vector(384), access_group)      │
│       • Index: HNSW (vector_cosine_ops)                │
└────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed & running.
- Python 3.11+
- Node.js 18+

### 2. Clone & Setup Environment
```bash
git clone https://github.com/Piyush105454/Rag-agent.git
cd Rag-agent

# Create environment file from template
cp .env.example .env
```
Fill in your `GROQ_API_KEY` in `.env`.

### 3. Start Database (pgvector)
```bash
docker compose up postgres -d
```

### 4. Setup Backend
```bash
# In project root
python -m venv .venv
# On Windows:
.\.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

pip install -r backend/requirements.txt

# Run seed test documents & Ingestion
python scripts/seed_test_docs.py
python -m backend.app.drive.sync sync_local_folder --path ./local_docs --group general

# Launch backend
cd backend
uvicorn app.main:app --port 8000 --reload
```

### 5. Setup Frontend
```bash
cd frontend
npm install
npm run dev
```
Open **[http://localhost:3000](http://localhost:3000)** in your browser!

---

## 📁 Repository Structure

```text
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routes (/query, /documents, /health)
│   │   ├── auth/           # JWT verification & RBAC user context
│   │   ├── db/             # SQLAlchemy + asyncpg session & models
│   │   ├── embeddings/     # Singleton BGE-small embedder & LRU cache
│   │   ├── ingestion/      # Multi-format parsers (PDF, PPTX) & chunker
│   │   ├── orchestrator/   # LangGraph nodes (rewrite, retrieve, rerank, guard)
│   │   └── vector_store/   # Pgvector store with HNSW index & RBAC filtering
├── frontend/               # Next.js 14 App Router, Tailwind CSS, SSE hooks
├── scripts/                # JWT generator & local seeding scripts
├── docker-compose.yml      # Container orchestration
└── .env.example            # Environment variables template
```

---

## 🔒 Security & Privacy

- **Zero Secret Commits:** API keys, certificates, database credentials, and service accounts are excluded via strict `.gitignore`.
- **RBAC Isolation:** All retrieval requests are filtered by the authenticated user's assigned access groups.

---

## 📜 License
MIT License. Free for open-source and commercial use.
