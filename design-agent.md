# RAG-Based Company Knowledge Assistant — System Design

**Prepared for:** Team review
**Status:** Proposal / Design phase
**Author:** Piyush

---

## 1. Objective

Build an internal chatbot that can answer questions from our own company documents (PDFs, PPTs, and other known files) with accurate, source-cited answers — similar in spirit to the QGPT architecture pattern (App Engine → Orchestrator → Azure Search → Knowledge Store, with an LLM in the loop via RAG).

---

## 2. Approach: RAG, not fine-tuning

| | RAG | Fine-tuning |
|---|---|---|
| Adding new knowledge | Update the index, no retraining | Requires retraining on every doc change |
| Cost | Low — embedding + storage | High — GPU time, data prep |
| Source citation | Yes — can point to exact document/page | No — knowledge is baked into weights |
| Hallucination control | Better — grounded in retrieved text | Worse — model can still fabricate |
| Best suited for | Injecting knowledge (our use case) | Changing tone, style, or behavior |

**Decision:** RAG is the right approach for company-document Q&A. Fine-tuning would only be worth revisiting later if we need the model to consistently follow a very specific response format/style, and even then it would sit on top of RAG, not replace it.

---

## 3. Architecture Overview

```
User → App Layer (Next.js + FastAPI)
              │
              ▼
        Orchestrator (LangGraph agent)
         │                        │
         ▼                        ▼
   Vector DB                    LLM
 (Qdrant / pgvector)      (API or self-hosted)
         ▲
         │
   Ingestion Pipeline
 (PDF / PPT parser + chunker)
         ▲
         │
   Source documents (PDF, PPT, other files)
```

**Flow:**
1. Documents are parsed and chunked offline by the ingestion pipeline, embedded, and stored in the vector DB.
2. A user query hits the app layer, which passes it to the orchestrator.
3. The orchestrator (LangGraph) retrieves relevant chunks from the vector DB, optionally reranks them, and sends the query + context to the LLM.
4. The LLM generates an answer; the app layer returns it along with source citations (which document/page it came from).

---

## 4. Components & Tech Stack

| Component | Technology | Notes |
|---|---|---|
| Frontend | Next.js | Chat UI, source citation display |
| Backend API | FastAPI (Python) | Query endpoint, auth, orchestration entry point |
| Orchestrator | LangGraph | Query rewriting → retrieval → (optional) rerank → generation |
| Vector database | pgvector (Postgres) or Qdrant | pgvector if we want to stay on our existing Postgres/EC2 setup; Qdrant if we need heavier filtering/scale later |
| Embeddings | `sentence-transformers` (open-source) or OpenAI/Gemini embeddings | Open-source keeps cost at zero; hosted embeddings trade cost for slightly better retrieval quality |
| Reranker (optional) | `bge-reranker` (cross-encoder) | Improves precision of top-k retrieved chunks before they reach the LLM |
| LLM | GPT-4o / Claude / Gemini (API) **or** Llama 3.1 / Mistral via `vLLM` (self-hosted) | API is faster to ship; self-hosted keeps data in-house but needs GPU + maintenance |
| Document parsing | `pdfplumber` / `PyMuPDF` (PDF), `python-pptx` (PPT), or `unstructured` (handles both + tables/images) | `unstructured` is the fastest path to a working pipeline |
| Deployment | Docker + docker-compose | Matches existing team skillset; can move to Kubernetes later if scale demands it |
| Evaluation | `ragas` | Measures faithfulness and answer relevance before sign-off |

---

## 5. Ingestion Pipeline (Detail)

1. Parse source files (PDF via `pdfplumber`/`PyMuPDF`, PPT via `python-pptx`, or both via `unstructured`).
2. Chunk text — 500–800 tokens per chunk, ~15% overlap between chunks.
3. Generate embeddings for each chunk.
4. Store embeddings + metadata (source filename, page/slide number) in the vector DB.
5. Re-run this pipeline whenever documents are added or updated — no model retraining required.

---

## 6. Access Control

If certain documents or the whole assistant should be restricted to specific teams (as in the reference architecture's "Restricted to Group" pattern):
- Add a role/group field to the user's auth token (JWT).
- Filter vector DB queries by document-level access tags matching the user's group.
- Keep this simple for MVP — expand to fine-grained per-document ACLs only if needed.

---

## 7. Deployment Plan

- `docker-compose` services: `postgres` (with `pgvector` extension) or `qdrant`, `fastapi-backend`, `nextjs-frontend`.
- Deploy on existing EC2 infrastructure to start — no new infra needed for MVP.
- Environment variables for LLM API keys / self-hosted model endpoint.
- Move to a managed vector DB or Kubernetes only once usage/scale justifies it.

---

## 8. Evaluation & Monitoring

- Use `ragas` to score faithfulness (is the answer grounded in retrieved context?) and answer relevance before rollout.
- Log every query, retrieved chunks, and final answer for manual review during the pilot phase.
- Track retrieval hit rate — are the right chunks being retrieved for known test questions?

---

## 9. Build Phases

| Phase | Deliverable |
|---|---|
| 1 | Ingestion script — parse + chunk + embed a sample set of docs into the vector DB |
| 2 | Manual retrieval test — confirm relevant chunks come back for sample queries |
| 3 | Basic `/query` FastAPI endpoint — retrieve top-k → prompt LLM → return answer + citations |
| 4 | Wrap with LangGraph — add query rewriting, reranking, multi-turn memory |
| 5 | Next.js chat UI |
| 6 | Dockerize + deploy on EC2 |
| 7 | Evaluate with `ragas`, fix gaps, pilot with a small user group |
| 8 | Add access control / group restrictions if required |

---

## 10. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Poor retrieval quality on scanned/image-heavy PPTs | Add OCR fallback (`pytesseract`) during ingestion |
| LLM hallucination despite retrieved context | Enforce "answer only from context" prompting + faithfulness checks via `ragas` |
| Data sensitivity if using an external LLM API | Evaluate self-hosted LLM option if documents are confidential |
| Scaling vector search as document count grows | Start with pgvector, migrate to Qdrant if latency/filtering becomes a bottleneck |

---

## 11. Agent Rules (System Prompt for the Assistant)

The orchestrator should enforce these rules on every response — bake them into the LLM's system prompt, not just into documentation:

1. **Answer only from retrieved context.** If the retrieved chunks don't contain the answer, say so explicitly — never fill gaps from general knowledge.
2. **Always cite sources.** Every answer must reference the document name and page/slide it came from.
3. **Respect access control.** Never surface content from a document the requesting user's group isn't permitted to see, even if it's semantically the best match.
4. **No fabrication of numbers, names, or policies.** If confidence in a retrieved chunk is low (low similarity score), say the answer is uncertain instead of guessing.
5. **Stay in scope.** Decline questions unrelated to company documents rather than answering from the LLM's general training data — this keeps the assistant trustworthy for its actual job.
6. **Log every query and answer** for review, but never expose one user's query history to another user.

This system prompt should be injected server-side in the orchestrator, not client-side, so it can't be bypassed by the frontend.

---

## 12. Google Drive as a Data Source

Instead of (or alongside) a static PDF/PPT dump, pull source documents directly from Google Drive so the knowledge base stays current automatically:

- **Auth:** Use a Google service account with read access to the target shared drive/folder (cleaner than per-user OAuth for an internal tool).
- **Sync strategy:** Start with polling (e.g., every 15–30 min, list files modified since last sync using the Drive API's `modifiedTime` filter) — simpler to build than push notifications. Move to Drive API push notifications (webhooks) later if near-real-time sync is needed.
- **Pipeline hook:** New/changed files feed into the same ingestion pipeline (Section 5) — parse → chunk → embed → upsert into the vector DB, replacing old chunks for that file.
- **Permission mapping:** If Drive folders already mirror team structure, map folder → access group so document-level ACLs (Section 6) stay consistent automatically instead of being maintained by hand.
- **Deleted files:** Track a `file_id → chunk_ids` mapping so that when a file is deleted or moved out of scope in Drive, its chunks are removed from the vector DB too — otherwise the assistant will keep citing content that no longer exists.

---

## 13. Improving Accuracy & Speed

| Lever | What it does |
|---|---|
| Hybrid search (vector + BM25 keyword) | Catches exact-term matches (names, codes, IDs) that pure embedding similarity can miss |
| Reranking (`bge-reranker`) | Reorders top-k retrieved chunks by actual relevance before they reach the LLM — usually the single biggest accuracy win |
| Query rewriting | Orchestrator rephrases vague/short user queries into a clearer retrieval query before searching |
| Chunk size tuning | Too large = irrelevant context dilutes the answer; too small = context gets fragmented. Test 500–800 tokens as a starting point, tune from evaluation results |
| Response streaming | Stream LLM tokens to the frontend as they generate instead of waiting for the full answer — big perceived-speed improvement |
| Caching | Cache embeddings for unchanged documents and answers for frequently repeated questions |
| Async I/O | FastAPI + async DB/LLM calls so one slow request doesn't block others |

---

## 14. Master Build Prompt

A single prompt you can hand to an AI coding assistant (e.g., Claude Code) to scaffold the whole platform end to end, in line with everything above:

```
Build a RAG-based company knowledge assistant with the following architecture and rules.

STACK:
- Frontend: Next.js (chat UI with streaming responses and inline source citations)
- Backend: FastAPI (Python), async throughout
- Orchestrator: LangGraph agent — nodes for query rewriting, retrieval, reranking, generation
- Vector DB: pgvector on Postgres
- Embeddings: sentence-transformers (open-source, local)
- Reranker: bge-reranker cross-encoder
- LLM: pluggable — support both an API provider (OpenAI/Anthropic/Gemini) and a self-hosted
  model via vLLM, selected by an environment variable
- Ingestion source: Google Drive (service account auth, poll every 15 min for changed files
  via the Drive API modifiedTime filter), plus a fallback local-folder PDF/PPT ingestion path
- Deployment: Docker + docker-compose (postgres+pgvector, fastapi backend, next.js frontend)

INGESTION PIPELINE:
- Parse PDFs and PPTs using the `unstructured` library (fallback to pdfplumber/python-pptx
  if needed), extract text and tables
- Chunk text at 500-800 tokens with ~15% overlap
- Embed each chunk and upsert into pgvector with metadata: source file name, page/slide
  number, Drive folder (mapped to an access group), file_id, chunk_id
- On re-sync, replace chunks for changed files and delete chunks for removed files

ORCHESTRATOR RULES (enforce server-side in the system prompt, not client-side):
1. Answer only from retrieved context — never fill gaps from general knowledge
2. Always cite the source document and page/slide for every claim
3. Filter retrieval results by the requesting user's access group before they ever reach
   the LLM — never let ungranted content leak into context
4. If retrieval confidence is low, respond with uncertainty instead of guessing
5. Decline questions outside the scope of the indexed documents
6. Log query, retrieved chunk IDs, and final answer per request; never expose one user's
   history to another

API:
- POST /query — body: {question, user_id}; returns {answer, sources: [{file, page}],
  confidence}. Should stream tokens.
- Auth: JWT with a `group` claim; backend filters vector search by group before ranking.

MCP PLUGIN INTERFACE:
- Also expose the orchestrator as an MCP server using the official MCP Python SDK, over
  SSE/HTTP (not stdio, since it needs to be reachable remotely as an installable plugin)
- Tools: query_company_docs(question, group) -> {answer, sources} and
  list_available_documents(group) -> [{file, updated}]
- Reuse the same JWT/group auth and the same orchestrator function as the REST API —
  do not duplicate retrieval/generation logic between the two interfaces

EVALUATION:
- Add a ragas-based evaluation script that scores faithfulness and answer relevance
  against a small set of test Q&A pairs before this is considered production-ready.

Build this as a working local-dev setup with docker-compose first (mock Drive folder is
fine to start), then wire in the real Google Drive service account credentials.
```

Adjust the LLM provider, vector DB choice, and access-control granularity in this prompt based on team decisions from Sections 2, 4, and 6.

---

## 15. Exposing the Agent as an MCP Plugin

This is the key requirement: the agent shouldn't just be a REST API behind your own frontend — it should be **usable as a plugin/tool by any MCP-compatible AI client** (Claude Desktop, Claude Code, other agents), the same way you'd add any MCP connector. This is the modern equivalent of a "downloadable plugin."

- **Use the official MCP SDK** (`mcp` Python package) to wrap your existing orchestrator logic as MCP tools — don't rewrite the retrieval/generation logic, just add a new interface layer that calls into it.
- **Expose these tools:**
  - `query_company_docs(question: str, group: str) → {answer, sources}`
  - `list_available_documents(group: str) → [{file, updated}]`
- **Transport:** Use SSE/HTTP (not stdio) since people will connect to this remotely rather than running it locally — this is what makes it "installable" for others rather than a local-only script.
- **Auth:** Reuse the same JWT/group-based auth as the REST API so access control isn't duplicated or inconsistent between the two interfaces.
- **Result:** Once deployed, anyone with an MCP-capable client just adds your server's URL as a connector and can immediately call `query_company_docs` as a tool — no custom integration code needed on their end. Your REST API (Section 3) and this MCP server become two thin interfaces on top of one orchestrator — keep the logic in one place.

---

## 16. Prerequisites — What to Learn Before Building

You already have Python, React/Next.js, Docker, PyTorch, scikit-learn, and some LangGraph — that covers most of this. Fill these specific gaps before starting:

- **Vector embeddings & similarity search** — what an embedding is, cosine similarity, why chunking matters. This is the foundation everything else sits on.
- **LangGraph fundamentals** — state graphs, nodes/edges, how to structure a multi-step agent (retrieve → rerank → generate) rather than a single prompt call.
- **FastAPI async patterns** — async DB calls, streaming responses (`StreamingResponse`) so the chat UI doesn't feel slow.
- **Google Drive API + service accounts** — OAuth2 service account setup, `files.list` with `modifiedTime` filtering, scopes/permissions.
- **Prompt engineering for grounded QA** — how to write a system prompt that reliably makes an LLM refuse to answer outside provided context (this is a real skill, not just "tell it not to hallucinate").
- **Basic RAG evaluation** — what faithfulness and answer-relevance mean, how `ragas` scores them, so you can tell if a change actually improved the system or not.
- **MCP (Model Context Protocol) basics** — how MCP servers/tools work and how the official Python SDK exposes a function as a callable tool over SSE/HTTP; this is what makes the agent "plugin-installable" for other AI clients.

You don't need to master all of these before writing code — pick up embeddings + LangGraph basics first (they're the core), and learn the Drive API and evaluation pieces when you reach those build phases.

---

*Open question for the team: confirm document sensitivity level, since this decides whether we use an LLM API or a self-hosted model.*