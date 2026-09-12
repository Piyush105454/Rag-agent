# Local Development Setup Guide

Follow these steps to get the RAG Knowledge Assistant running on your local machine.

## Prerequisites
- Docker and docker-compose
- Python 3.11+
- Node.js 20+

## 1. Environment Setup

Copy the example environment file and fill in your keys:

`ash
cp .env.example .env
``n
Open .env and fill in:
- GROQ_API_KEY: Get this from your Groq console.
- JWT_SECRET: Generate a random string.

*(Google Drive settings can be left blank for local testing).*

## 2. Start Services

Start the Postgres database, FastAPI backend, MCP server, and Next.js frontend using Docker Compose:

`ash
docker-compose up --build
``n
Wait until you see logs indicating that the database is ready and uvicorn is listening on port 8000.

## 3. Seed Test Documents

Run the seed script to create some mock documents in ./local_docs:

`ash
python scripts/seed_test_docs.py
``nThis will create sales_policy.txt, engineering_specs.txt, and hr_handbook.txt.

## 4. Ingest Documents

Run the ingestion script to process and embed the local documents into pgvector. This runs inside the backend container:

`ash
bash ./scripts/ingest_local.sh
``n
## 5. Generate a Test JWT

To chat with the agent, you need a valid JWT token. Generate one with the required skills/groups:

`ash
python scripts/generate_jwt.py --user-id testuser --groups general,engineering --secret YOUR_JWT_SECRET
``nCopy the token string that is printed.

## 6. Start Chatting

1. Open your browser to [http://localhost:3000](http://localhost:3000)
2. You should see the chat interface.
3. Paste the JWT token you copied into the auth input.
4. Try asking: *"What is the return policy?"*
