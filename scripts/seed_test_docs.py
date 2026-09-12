#!/usr/bin/env python3
"""
scripts/seed_test_docs.py

Creates a ./local_docs/ directory and writes three realistic sample text
files that the RAG ingestion pipeline can index. These files simulate
multi-page corporate documents with varied content across access groups.

Run from the repo root:
    python scripts/seed_test_docs.py

Files created:
    local_docs/sales_policy.txt       -- access_group: sales
    local_docs/engineering_specs.txt  -- access_group: engineering
    local_docs/hr_handbook.txt        -- access_group: general
"""

import os
import sys
from pathlib import Path

DOCS_DIR = Path(__file__).parent.parent / "local_docs"

# ---------------------------------------------------------------------------
# Document content definitions
# ---------------------------------------------------------------------------

SALES_POLICY = """\
ACME CORPORATION — SALES POLICY AND PROCEDURES MANUAL
Version 3.2 | Effective Date: January 1, 2025
============================================================

PAGE 1 — INTRODUCTION AND SCOPE
============================================================

1.1 Purpose
This Sales Policy Manual establishes the standards, procedures, and
guidelines governing ACME Corporation's commercial sales activities.
All members of the Sales, Business Development, and Account Management
teams are required to adhere to this policy.

1.2 Scope
This policy applies to:
  - Direct enterprise sales (B2B contracts >$10,000 ARR)
  - SMB self-serve sales (B2B contracts $1,000–$10,000 ARR)
  - Channel partner resellers
  - Government and public sector sales

1.3 Policy Owner
VP of Sales (currently Sarah Mitchell, sarah.mitchell@acme.com)
Last reviewed: December 2024

============================================================
PAGE 2 — PRICING AND DISCOUNTING
============================================================

2.1 Standard List Prices
All prices are denominated in USD. Current list prices are maintained
in the product catalog on Salesforce and are updated quarterly.

Product Tier     | Monthly ARR   | Annual ARR
-----------------|---------------|-------------
Starter          | $199/mo       | $1,990/yr
Professional     | $799/mo       | $7,990/yr
Enterprise       | $2,499/mo     | $24,990/yr
Enterprise Plus  | Custom quote  | Custom quote

2.2 Approved Discount Thresholds
Account Executives may approve discounts up to the following limits
without additional sign-off:

  - AE authority:          Up to 15% off list price
  - Regional VP authority: Up to 25% off list price
  - VP Sales authority:    Up to 35% off list price
  - CEO approval required: Above 35%

2.3 Discount Justification
Any discount above 10% requires a business justification entered in
Salesforce opportunity notes. Valid justifications include:
  a) Competitive displacement (attach competitor quote)
  b) Strategic account (revenue potential >$500K)
  c) Anchor customer in new vertical
  d) Multi-year upfront payment (3+ years)

2.4 Bundling Rules
Product bundles must include at least the Professional tier base. Add-on
modules cannot be sold without a core platform license.

============================================================
PAGE 3 — RETURN AND REFUND POLICY
============================================================

3.1 Subscription Refunds
ACME offers a 30-day money-back guarantee for new Starter and Professional
subscriptions. Enterprise subscriptions are non-refundable after the
contract execution date unless explicitly stated in the MSA.

3.2 Refund Process
To initiate a refund:
  1. Customer submits request via support@acme.com
  2. Account Executive confirms eligibility in Salesforce
  3. Finance team processes refund within 5 business days
  4. Refund method mirrors original payment method

3.3 Exceptions
  - Annual contracts paid upfront: Pro-rated refund for unused months
  - Add-on modules: Refundable within 14 days of purchase
  - Professional Services: Non-refundable once work has commenced

============================================================
PAGE 4 — COMMISSION AND COMPENSATION
============================================================

4.1 Commission Structure (FY2025)
Base commission rates for new ARR:
  - Starter/Pro deals:        8% of first-year ARR
  - Enterprise deals:         10% of first-year ARR
  - Renewals (no expansion):  2% of ARR
  - Expansions/upsells:       8% of incremental ARR

4.2 Accelerators
  - Quarterly quota attainment >100%: 1.25x multiplier
  - Quarterly quota attainment >125%: 1.5x multiplier
  - Multi-year deals (2 yr):          1.15x multiplier
  - Multi-year deals (3+ yr):         1.25x multiplier

4.3 Commission Payment Schedule
Commissions are paid on the 15th of the month following the month in
which payment is collected from the customer. SPIFF bonuses for Q-end
pushes are paid with the following month's regular commissions.

4.4 Clawback Policy
If a customer churns within 6 months of the sale close date, 50% of
the original commission paid will be clawed back from the AE's next
commission check.

============================================================
PAGE 5 — CRM AND DEAL MANAGEMENT
============================================================

5.1 Salesforce Hygiene Requirements
All opportunities must be updated in Salesforce within 24 hours of
any meaningful customer interaction. Required fields for pipeline deals:
  - Next step with date
  - Close date (realistic, not end-of-quarter padding)
  - Stage
  - Amount (ARR)
  - Primary contact with title

5.2 Forecasting Categories
  - Closed Won:   Contract executed, invoice sent
  - Commit:       >90% probability, verbal or written commitment received
  - Best Case:    50–90% probability
  - Pipeline:     10–50% probability
  - Omitted:      <10% or no activity in 30 days

5.3 Deal Desk Process
Deals requiring non-standard terms (custom SLA, IP indemnification,
liability caps above $1M, or custom DPA) must be routed through Deal
Desk at dealdesk@acme.com with a minimum 5 business day turnaround.
"""

ENGINEERING_SPECS = """\
ACME CORPORATION — ENGINEERING TECHNICAL SPECIFICATIONS
Platform Architecture v2.4 | Updated: September 2025
============================================================

PAGE 1 — SYSTEM OVERVIEW
============================================================

1.1 Architecture Summary
ACME Platform is a multi-tenant SaaS application built on a microservices
architecture deployed on AWS. The system processes approximately 2 million
API requests per day across its production cluster.

Core components:
  - API Gateway:     Kong (self-managed, k8s)
  - Backend:         Python (FastAPI) + Node.js (BFF)
  - Data layer:      PostgreSQL 16 (RDS), Redis 7 (ElastiCache)
  - Vector store:    pgvector on dedicated RDS instance
  - Message queue:   Amazon SQS + SNS
  - Object storage:  S3 + CloudFront CDN
  - Observability:   Datadog APM, CloudWatch, PagerDuty

1.2 Deployment Regions
  - Primary:      us-east-1 (N. Virginia)
  - Secondary:    eu-west-1 (Ireland) — EU data residency
  - DR standby:   us-west-2 (Oregon) — RTO 4h, RPO 1h

============================================================
PAGE 2 — API SPECIFICATIONS
============================================================

2.1 Authentication
All API endpoints require JWT Bearer authentication unless marked public.
Token format: HS256 signed, 24-hour expiry, claims include:
  - sub:    user UUID
  - org_id: organization UUID
  - roles:  array of role strings
  - exp:    Unix timestamp

Public endpoints (no auth required):
  GET  /health
  GET  /api/v1/status
  POST /api/v1/auth/login
  POST /api/v1/auth/refresh

2.2 Rate Limiting
Per-token rate limits enforced at API Gateway:
  Starter tier:       100 req/min, 10,000 req/day
  Professional tier:  500 req/min, 100,000 req/day
  Enterprise tier:    2,000 req/min, unlimited/day

Rate limit headers returned on every response:
  X-RateLimit-Limit: 500
  X-RateLimit-Remaining: 487
  X-RateLimit-Reset: 1720000000

2.3 Core API Endpoints
POST /api/v1/documents
  Upload a document for processing. Accepts multipart/form-data.
  Max file size: 50MB. Supported types: PDF, DOCX, XLSX, TXT, MD.
  Returns: { document_id, status: "processing" | "ready" | "failed" }

GET /api/v1/documents
  List documents accessible to the authenticated user.
  Query params: page, limit, access_group, search
  Returns: paginated document array

POST /api/v1/query
  Submit a natural language query against the knowledge base.
  Body: { question: string, stream?: boolean, top_k?: number }
  Streaming: SSE (text/event-stream) when stream=true

GET /api/v1/documents/{doc_id}/chunks
  Retrieve indexed chunks for a document (admin only).

============================================================
PAGE 3 — DATABASE SCHEMA
============================================================

3.1 Primary Tables (PostgreSQL)
documents
  - id            UUID PRIMARY KEY DEFAULT gen_random_uuid()
  - org_id        UUID NOT NULL REFERENCES organizations(id)
  - file_name     TEXT NOT NULL
  - source        TEXT NOT NULL  -- "drive" | "local" | "upload"
  - access_group  TEXT NOT NULL
  - drive_file_id TEXT
  - indexed_at    TIMESTAMPTZ
  - chunk_count   INTEGER DEFAULT 0
  - metadata      JSONB DEFAULT '{}'
  - created_at    TIMESTAMPTZ DEFAULT NOW()

document_chunks
  - id            UUID PRIMARY KEY DEFAULT gen_random_uuid()
  - document_id   UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE
  - chunk_index   INTEGER NOT NULL
  - text          TEXT NOT NULL
  - token_count   INTEGER NOT NULL
  - page_number   INTEGER DEFAULT 1
  - embedding     vector(384)        -- BAAI/bge-small-en-v1.5
  - access_group  TEXT NOT NULL
  - metadata      JSONB DEFAULT '{}'
  - created_at    TIMESTAMPTZ DEFAULT NOW()

3.2 Indexes
  CREATE INDEX CONCURRENTLY idx_chunks_embedding
    ON document_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m=16, ef_construction=64);

  CREATE INDEX idx_chunks_access_group
    ON document_chunks (access_group);

  CREATE INDEX idx_chunks_document
    ON document_chunks (document_id);

3.3 Access Control Pattern
All queries filter chunks by access_group using:
  WHERE access_group = ANY(:user_groups)
Groups are extracted from the JWT claims array at query time.
No row-level security (RLS) is used — application-level filtering.

============================================================
PAGE 4 — ML PIPELINE
============================================================

4.1 Embedding Model
  Model:      BAAI/bge-small-en-v1.5
  Dimensions: 384
  Device:     CPU (controlled by EMBED_DEVICE env var)
  Batch size: 32 documents per batch

4.2 Reranker
  Model:      BAAI/bge-reranker-base (cross-encoder)
  Input:      Query + top-K retrieved chunks (K=20)
  Output:     Reranked top-N chunks (N=5)
  Device:     CPU

4.3 LLM
  Provider:   Groq API
  Model:      llama-3.1-70b-versatile (default)
  Max tokens: 2048 output
  Streaming:  Yes (token-by-token via SSE)

4.4 Chunking Strategy
  Tokenizer:    tiktoken cl100k_base
  Target size:  650 tokens per chunk
  Overlap:      15% (approximately 98 tokens)
  Boundary:     Sentence-aware splitting

============================================================
PAGE 5 — INFRASTRUCTURE AND DEVOPS
============================================================

5.1 Container Registry
All services are packaged as Docker images and stored in ECR.
Image tags follow semantic versioning: v{major}.{minor}.{patch}

5.2 CI/CD Pipeline (GitHub Actions)
  - PR checks:   lint (ruff, mypy), unit tests, security scan (trivy)
  - Main branch: build images, push to ECR, deploy to staging
  - Tags:        deploy to production (manual approval required)

5.3 Environment Variables (required)
  GROQ_API_KEY           Groq API key for LLM calls
  JWT_SECRET             HS256 signing secret
  DATABASE_URL           PostgreSQL connection string
  REDIS_URL              Redis connection string
  EMBED_DEVICE           "cpu" or "cuda"
  GOOGLE_SERVICE_ACCOUNT_JSON  Path to service account key file
  DRIVE_FOLDER_ID        Root Google Drive folder to index

5.4 Health Check Endpoints
  GET /health         Returns 200 with {"status":"ok","version":"x.x.x"}
  GET /health/db      Checks DB connectivity
  GET /health/redis   Checks Redis connectivity

5.5 SLAs
  API availability:    99.9% uptime (excluding maintenance windows)
  P50 query latency:   <1.5s (first token)
  P95 query latency:   <4s   (first token)
  Ingestion throughput: 500 pages/minute
"""

HR_HANDBOOK = """\
ACME CORPORATION — EMPLOYEE HANDBOOK
Human Resources | Version 8.0 | Effective January 2025
============================================================

PAGE 1 — WELCOME AND COMPANY VALUES
============================================================

1.1 Welcome Message from the CEO
Welcome to ACME Corporation! We are a team of curious problem-solvers
building technology that helps businesses unlock the value in their
institutional knowledge. We are glad you are here.

1.2 Our Core Values
  TRUST:      We default to trusting our colleagues and our customers.
  CURIOSITY:  We ask why before we ask how.
  IMPACT:     We measure success by outcomes, not effort.
  INCLUSION:  Every voice shapes our decisions.
  SPEED:      We prefer done over perfect, and iterate from there.

1.3 Company Overview
  Founded:     2019 (San Francisco, CA)
  Employees:   ~320 globally
  Offices:     San Francisco (HQ), New York, London, Singapore
  Remote:      ~40% of workforce is fully remote

============================================================
PAGE 2 — BENEFITS AND COMPENSATION
============================================================

2.1 Base Salary
Salaries are benchmarked annually to the 65th percentile of Radford
survey data for our size band. Bands are reviewed each January.

2.2 Equity
All full-time employees receive equity grants:
  - Standard vest schedule: 4 years with 1-year cliff
  - Cliff: 25% vests at 12 months
  - Remaining: monthly vesting over 36 months
  - Refresh grants: annual for exceeds-expectations performers

2.3 Health Insurance (US employees)
  Medical:  ACME covers 100% of employee premium, 80% of dependents
  Dental:   100% employee, 80% dependents
  Vision:   100% employee, 80% dependents
  Provider: Anthem Blue Cross (PPO and HDHP options)

2.4 Retirement (US employees)
  - 401(k) with Fidelity
  - ACME matches 4% of salary (dollar-for-dollar)
  - Vesting: immediate for employer match

2.5 International Benefits
  UK:  Private health insurance via Bupa, pension via Royal London
  SG:  CPF contributions per statutory requirements, supplemental Cigna

2.6 Additional Benefits
  Learning budget:        $2,000/year (books, courses, conferences)
  Home office stipend:    $750 one-time for new hires
  Wellness stipend:       $100/month (gym, apps, etc.)
  Meal vouchers:          $200/month for SF/NY/London office employees
  Parental leave:         16 weeks fully paid (all genders)
  Fertility support:      Up to $10,000 lifetime benefit

============================================================
PAGE 3 — TIME OFF POLICY
============================================================

3.1 Paid Time Off (PTO)
ACME uses an unlimited PTO policy. There is no accrual, no rollover,
and no payout upon departure. The expectation is that employees take
a minimum of 15 days per year.

3.2 How to Request Time Off
  1. Discuss with your manager at least 2 weeks in advance for
     absences of 5+ business days.
  2. Submit request in Rippling (HR system) under "Time Off."
  3. Manager approves in Rippling. You will receive email confirmation.
  4. Block your calendar and set an out-of-office reply.

3.3 Company Holidays (US, 2025)
  Jan 1  New Year Day        Jul 4  Independence Day
  Jan 20 MLK Day             Sep 1  Labor Day
  Feb 17 Presidents Day      Nov 27 Thanksgiving
  May 26 Memorial Day        Dec 25 Christmas Day
  Plus 2 floating holidays of your choice.

3.4 Sick Leave
  Sick leave is separate from PTO and does not count against it.
  Use the "Sick Leave" category in Rippling. No approval required.
  For absences >5 consecutive sick days, a doctor's note is required.

3.5 Volunteer Time Off
  All employees receive 16 hours (2 days) of paid volunteer time off
  annually. Coordinate with your manager and log in Rippling as "VTO."

============================================================
PAGE 4 — REMOTE WORK AND WORKPLACE
============================================================

4.1 Remote Work Policy
Fully remote employees may work from any location within their
contracted country. Travel to your nearest ACME office is expected
at least once per quarter for team rituals.

4.2 Work Hours
ACME is a results-oriented workplace. There are no mandated core
hours globally. However:
  - Employees must be reachable during 10am–3pm in their local time
    zone on business days.
  - Team meetings are scheduled to avoid routinely requiring early
    morning or late evening attendance.

4.3 Equipment Policy
  New hires choose between:
  - MacBook Pro 14" (M3 chip) — standard engineering
  - MacBook Air 13" (M3 chip) — standard non-engineering
  - Windows option available on request

  Equipment ships before start date. All equipment remains ACME
  property and must be returned within 10 business days of departure.

4.4 Home Office
Remote employees must maintain a suitable, private workspace.
ACME is not responsible for internet connectivity costs unless
mandated by local law.

============================================================
PAGE 5 — PERFORMANCE AND GROWTH
============================================================

5.1 Performance Review Cycle
  - Mid-year review:  July (360-degree feedback, no ratings)
  - Annual review:    January (ratings, compensation adjustments)
  - New hire review:  90-day check-in with manager

5.2 Performance Ratings
  Exceeds Expectations (EE)    Top ~15% of performers
  Meets Expectations (ME)      Majority of employees
  Partially Meets (PM)         Improvement plan required
  Does Not Meet (DNM)          At-risk for separation

5.3 Promotion Process
  1. Manager nominates during bi-annual calibration (Jan, Jul)
  2. Calibration panel (skip-level + HR) approves or holds
  3. Offers communicated within 2 weeks of calibration
  4. Effective first day of following month

5.4 Learning and Development
  Use your $2,000 annual budget for:
  - Online courses (Coursera, Udemy, Pluralsight, etc.)
  - Books (physical or digital)
  - Industry conferences (travel covered separately)
  - Professional certifications (AWS, GCP, PMP, etc.)

  Submit reimbursement receipts via Expensify within 30 days of purchase.

============================================================
PAGE 6 — CODE OF CONDUCT
============================================================

6.1 Professional Conduct
ACME expects all employees to behave with integrity, respect, and
professionalism at all times, including at company events, on Slack,
in customer calls, and on social media when representing ACME.

6.2 Conflicts of Interest
Employees must disclose any situation that creates or could appear
to create a conflict of interest. This includes:
  - Investments in ACME customers or competitors (>1% ownership)
  - Employment at a competing company
  - Personal relationships with direct reports

  Disclose via conflict-of-interest@acme.com.

6.3 Anti-harassment Policy
ACME has zero tolerance for harassment or discrimination of any kind.
Report concerns to your People Business Partner or anonymously via
the EthicsPoint hotline: 1-800-555-0199 or acme.ethicspoint.com.

6.4 Confidentiality
All employees sign an NDA as part of onboarding. Company data,
customer data, and product roadmaps are confidential. Do not share
outside ACME without explicit written authorization.
"""

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    documents = [
        ("sales_policy.txt", SALES_POLICY),
        ("engineering_specs.txt", ENGINEERING_SPECS),
        ("hr_handbook.txt", HR_HANDBOOK),
    ]

    for filename, content in documents:
        path = DOCS_DIR / filename
        path.write_text(content, encoding="utf-8")
        size_kb = len(content.encode("utf-8")) / 1024
        lines = content.count("\n")
        print(f"  Created: {path}  ({size_kb:.1f} KB, {lines} lines)")

    print()
    print(f"Created {len(documents)} seed documents in {DOCS_DIR}/")
    print()
    print("Next steps:")
    print("  1. Run the ingestion pipeline:")
    print("     docker exec backend python -m app.ingestion.pipeline ingest ./local_docs sales")
    print("     docker exec backend python -m app.ingestion.pipeline ingest ./local_docs engineering")
    print("     docker exec backend python -m app.ingestion.pipeline ingest ./local_docs general")
    print()
    print("  2. Or use the local sync command:")
    print("     bash scripts/ingest_local.sh")


if __name__ == "__main__":
    main()
