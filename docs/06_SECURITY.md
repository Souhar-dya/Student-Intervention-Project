# Security — AI-Powered Student Success Assistant

> **Document version:** 1.0
> **Project:** Student Success Assistant
> **Last updated:** 2026-06-15
> **Classification:** Internal — Security Architecture

---

## Table of Contents

1. [Authentication and Authorization](#1-authentication-and-authorization)
2. [Data Protection](#2-data-protection)
3. [API Security](#3-api-security)
4. [LLM Security](#4-llm-security)
5. [Storage Security](#5-storage-security)
6. [Open Issues and Recommendations](#6-open-issues-and-recommendations)
7. [Security Checklist](#7-security-checklist)

---

## 1. Authentication and Authorization

### 1.1 Authentication Scheme

The system uses a **custom HMAC-SHA256 token scheme** (not JWT). Tokens are self-contained bearer credentials issued upon successful login.

```
Token format:
  {base64url(payload)}.{base64url(HMAC-SHA256(payload, secret))}
```

**Payload structure:**

| Field | Type | Description |
|-------|------|-------------|
| `sub` | string | Username (currently always `"advisor"`) |
| `exp` | integer | Expiration Unix timestamp (default: 8 hours) |

**Token lifecycle:**

- **Issuance:** `POST /auth/login` validates static credentials (`SSA_AUTH_USERNAME` / `SSA_AUTH_PASSWORD`) using constant-time comparison (`hmac.compare_digest`). On success, returns `{ token, token_type, username }`.
- **Verification:** Every protected endpoint depends on `require_authenticated_user`, which decodes the payload, verifies the HMAC signature, checks expiration, and extracts the `sub` claim.
- **Format:** `Authorization: Bearer <token>`

**Code reference:** `core/security.py:18-94`

### 1.2 Public vs. Protected Endpoints

```
                          ┌──────────────────────────┐
                          │      Client Request       │
                          └────────────┬─────────────┘
                                       │
                            ┌──────────▼──────────┐
                            │  Is this a public    │
                            │  endpoint?           │
                            │                      │
                            │  /health             │
                            │  /ready              │
                            │  /auth/login         │
                            │  /auth/me            │
                            └──────┬──────┬────────┘
                                   │      │
                               Yes │      │ No
                                   │      │
                         ┌─────────▼┐    ┌▼──────────────────┐
                         │  Permit  │    │ Require Bearer     │
                         │  Access  │    │ Token via          │
                         └──────────┘    │ HTTPBearer         │
                                         │                    │
                                         │  ┌──────────────┐  │
                                         │  │ Verify HMAC  │  │
                                         │  │ Signature    │  │
                                         │  └──────┬───────┘  │
                                         │         │          │
                                         │  ┌──────▼───────┐  │
                                         │  │ Check Expiry │  │
                                         │  └──────┬───────┘  │
                                         │         │          │
                                         │    ┌────▼────┐     │
                                         │    │ Extract  │     │
                                         │    │ sub (usr)│     │
                                         │    └──────────┘     │
                                         └─────────┬──────────┘
                                                   │
                                          ┌────────▼────────┐
                                          │   Route Handler  │
                                          └─────────────────┘
```

**Public endpoints (no authentication):**

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Liveness probe |
| `GET` | `/ready` | Readiness probe |
| `POST` | `/auth/login` | Credential exchange for token |
| `GET` | `/auth/me` | Current session verification |

**Protected endpoints (Bearer token required):**

All routes under `/api/v1/*` require a valid HMAC bearer token, enforced by `require_authenticated_user` as a FastAPI dependency on the `protected_router`. This includes prediction, search, recommendation, evaluation, explanation, feedback, follow-up, insights, parent notification, and all admin routes.

**Code reference:** `api/router.py:19-35`

### 1.3 Authorization Model

- **Single user:** The system authenticates a single advisor identity. Credentials are statically configured via environment variables (`SSA_AUTH_USERNAME`, `SSA_AUTH_PASSWORD`).
- **No RBAC:** Role-based access control is not implemented. Every authenticated user has full access to all protected endpoints.
- **No user management:** There is no user registration, password reset, or user administration dashboard.
- **Session scope:** The `require_authenticated_user` dependency returns the username string. No further authorization checks exist at the route or resource level.

---

## 2. Data Protection

### 2.1 Secrets Management

All secrets, keys, and configuration values are managed through **environment variables** and loaded via **Pydantic Settings** (`core/config.py`).

**Secret environment variables:**

| Variable | Sensitivity | Description |
|----------|-------------|-------------|
| `SSA_AUTH_TOKEN_SECRET` | Critical | HMAC signing key for tokens |
| `SSA_AUTH_PASSWORD` | Critical | Advisor login password |
| `SSA_DATABASE_URL` | Critical | PostgreSQL connection string (may contain credentials) |
| `SSA_QDRANT_API_KEY` | High | Qdrant cloud API key |
| `SSA_OPENAI_API_KEY` | High | OpenAI API key (if OpenAI provider used) |
| `SSA_LANGCHAIN_API_KEY` | Medium | LangSmith API key |
| `SSA_SMTP_PASSWORD` | Medium | SMTP server password |
| `SSA_SMTP_USERNAME` | Medium | SMTP server username |

**Loading mechanism** (`core/config.py:70-74`):

```python
model_config = SettingsConfigDict(
    env_file=PROJECT_ROOT / ".env",
    env_prefix="SSA_",
    extra="ignore",
)
```

- Variables are read from a `.env` file at the project root, with an `SSA_` prefix.
- `.env` is listed in `.gitignore` and is never committed.
- A template (`.env.example`) is committed with placeholder values and documentation comments — it contains no real secrets.
- Settings are cached via `@lru_cache` on `get_settings()` to avoid repeated file reads.

### 2.2 Transport Layer Security (TLS)

- **PostgreSQL (Aiven):** TLS encryption is enabled by default on Aiven-managed PostgreSQL instances. The `psycopg` binary client connects over TLS when the `SSA_DATABASE_URL` uses the `postgresql+psycopg://` scheme with `sslmode=require` or equivalent.
- **Qdrant Cloud:** TLS is enforced by the Qdrant cloud endpoint (gRPC/REST over HTTPS). The `qdrant-client` library connects securely when the URL uses `https://`.
- **SMTP:** TLS is configurable via `SSA_SMTP_USE_TLS` (default: `true`) and `SSA_SMTP_PORT` (default: `587` for STARTTLS).
- **No HTTPS in application code:** TLS termination is expected at a reverse proxy (e.g., nginx, AWS ALB, Cloudflare). The FastAPI application itself runs over HTTP.

### 2.3 In-Transit Data Flow

```
                        ┌──────────────────────────────────────┐
                        │        Reverse Proxy / Load Balancer │
                        │      (HTTPS termination expected)     │
                        └────────────┬─────────────────────────┘
                                     │ HTTP (internal network)
                                     ▼
                        ┌──────────────────────────────────────┐
                        │   FastAPI Application (port 8000)     │
                        └──┬───────────────┬────────────────┬──┘
                           │               │                │
                    TLS    │          TLS   │           TLS  │
                    (Aiven)│      (Qdrant   │      (STARTTLS)│
                           │       Cloud)   │                │
                           ▼               ▼                ▼
                   ┌────────────┐  ┌────────────┐  ┌──────────────┐
                   │ PostgreSQL │  │   Qdrant   │  │ SMTP Server  │
                   │  (Aiven)   │  │  (Cloud)   │  │  (optional)  │
                   └────────────┘  └────────────┘  └──────────────┘
```

---

## 3. API Security

### 3.1 CORS (Cross-Origin Resource Sharing)

CORS is configured in `main.py:12-18` using FastAPI's `CORSMiddleware`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- Allowed origins are read from `SSA_CORS_ORIGINS` (default: `http://localhost:5173,http://127.0.0.1:5173`).
- In production, this should be restricted to the specific frontend origin(s).
- Arbitrary HTTP methods and headers are permitted in development.

### 3.2 Request Validation

All API endpoints use **Pydantic v2 schemas** for request validation. FastAPI automatically validates incoming JSON bodies against the defined schema, returning a `422 Unprocessable Entity` response with field-level error details if validation fails.

**Validation examples by endpoint:**

| Endpoint | Validated Fields | Constraints |
|----------|-----------------|-------------|
| `POST /auth/login` | `username`, `password` | 1–120 chars, 1–200 chars |
| `POST /api/v1/predict` | `StudentProfile` fields | Age 15–22, attendance 0–100, failures 0–4, etc. |
| `POST /api/v1/search` | `query`, `top_k`, `filters` | Query ≥ 3 chars, top_k 1–20 |
| `POST /api/v1/feedback` | `rating` | Must be `"useful"` or `"not_useful"` |
| `POST /api/v1/parent-email/send` | `parent_email`, `subject`, `body` | Email format, 3–160 chars, 10–5000 chars |

### 3.3 Error Handling

Error responses follow a consistent pattern:

- **401 Unauthorized:** Returns `{"detail": "Authentication required"}` with `WWW-Authenticate: Bearer` header. No information about why authentication failed (invalid token, expired, malformed).
- **422 Validation Error:** Returns standard FastAPI/Pydantic validation errors. Field-level messages are specific but do not expose internals.
- **500 Internal Server Error:** FastAPI defaults to generic error responses in production (when `SSA_ENVIRONMENT != "local"`). Stack traces are not exposed to API consumers.

**Authentication error implementation** (`core/security.py:89-93`):

```python
def _auth_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )
```

All authentication failures (missing token, invalid signature, expired token, empty subject) return the same generic message.

### 3.4 Endpoint Hardening

| Measure | Status | Details |
|---------|--------|---------|
| Bearer token on all data endpoints | ✅ Implemented | Via `protected_router` dependency |
| Input validation | ✅ Implemented | Pydantic schemas on every endpoint |
| Generic error messages | ✅ Implemented | Single message for all auth failures |
| HTTPS termination | ❌ Not in code | Expected at reverse proxy |
| Rate limiting | ❌ Not implemented | No protection against brute-force or DoS |
| Request size limits | ⚠️ FastAPI default | Default JSON body size limit applies |

---

## 4. LLM Security

### 4.1 Prompt Injection Mitigations

The system incorporates multiple layers of defense against prompt injection and prompt manipulation:

#### 4.1.1 Structured Schema-Based Input

All user-supplied text that reaches an LLM is first validated through Pydantic schemas. This ensures type safety and bounds checking before any prompt construction occurs.

#### 4.1.2 Template String Prompts

LLM prompts are constructed using **template strings** rather than raw concatenation. User input is interpolated into predefined templates, limiting the injection surface.

**Example from `insights_service.py:278-288`:**

```python
llm_prompt = (
    "You are a student-success data analyst. Answer the user's question directly using "
    "only the dataset facts below. ..."
    f"User question: {prompt}\n"
    f"Rows analyzed: {row_count}\n"
    f"Dataset summary: {summary}\n\n"
    f"Factor evidence:\n{factor_lines}\n\n"
    f"Top-performing student candidates:\n{top_student_lines}"
)
```

#### 4.1.3 Dataset-Scoped Guardrails

The **Insights Service** implements a prompt guardrail that restricts user queries to dataset-scoped terms:

**Guardrail implementation** (`insights_service.py:54-96`):

```python
ALLOWED_PROMPT_TERMS = (
    "student", "success", "failure", "fail", "pass", "risk",
    "grade", "mark", "score", "performance",
    "attendance", "absence", "absences",
    "study", "school", "education", "support",
    "dataset", "data", "uci",
    "family", "parent", "mother", "father", "guardian",
    "feature", "factor", "top", "best",
)
```

- Prompts are checked via `_is_allowed_prompt()` which tests if at least one allowed term is present (case-insensitive substring match).
- Rejected prompts return `generated_by: "guardrail"` with a fixed denial message. The LLM is never called.
- This prevents off-topic queries (e.g., personal questions, system instructions, unrelated topics).

### 4.2 LLM Call Flow

```
User Prompt ──► Guardrail Check ──► Allowed ──► Template Assembly ──► LLM Call
                    │                                    │
               ┌────┴────┐                      ┌────────┴────────┐
               │ Blocked │                      │ Structured Data │
               └─────────┘                      │ (factors, rows, │
                                                 │  student IDs)   │
                                                 └─────────────────┘
                                               
                                                    │
                                              ┌─────▼─────┐
                                              │ Parse JSON │
                                              │ or text    │
                                              └────────────┘
```

### 4.3 LLM Provider Security

| Provider | Transport | API Key Requirement |
|----------|-----------|-------------------|
| **Ollama** (local, default) | HTTP (localhost) | None — runs locally |
| **OpenAI** (optional) | HTTPS | `SSA_OPENAI_API_KEY` |

- When using Ollama, all LLM traffic stays on the local machine — no data leaves the host.
- When using OpenAI, the API key is stored in an environment variable and never exposed to clients.

### 4.4 Deterministic Fallbacks

Every LLM-dependent feature has a **deterministic fallback** that does not call any language model:

| Feature | Fallback | Trigger |
|---------|----------|---------|
| Insight factor analysis | CSV-based statistical analysis | LLM unavailable or unparseable response |
| Recommendation agent | Hardcoded intervention plan | LangGraph or LLM unavailable |
| Evaluation (LLM-as-judge) | Rubric-based scoring | Judge model unavailable |
| Follow-up assessment | Rule-based rubric | Judge model unavailable |

This ensures the system remains functional even when the LLM is unreachable, and prevents prompt injection from propagating beyond the LLM boundary.

---

## 5. Storage Security

### 5.1 PostgreSQL (Aiven)

| Attribute | Detail |
|-----------|--------|
| **Provider** | Aiven managed cloud |
| **In-transit encryption** | TLS (enforced by Aiven) |
| **At-rest encryption** | Handled by Aiven (provider-managed) |
| **Access control** | Database URL with embedded credentials (user/password) |
| **Network isolation** | Aiven allows IP allowlisting |

**Data stored:**
- `students` — Student demographic and academic records (name not stored, only school-assigned IDs)
- `student_cases` — Generated case narratives derived from student features
- `feedback` — Advisor ratings and notes on recommendations
- `evaluation_results` — LLM judge scores and notes
- `follow_up_cases` — Follow-up monitoring data, advisor notes, assessment results
- `follow_up_events` — Event history for follow-up cases

### 5.2 Qdrant Cloud

| Attribute | Detail |
|-----------|--------|
| **Provider** | Qdrant managed cloud |
| **In-transit encryption** | TLS (enforced by cloud endpoint) |
| **At-rest encryption** | Handled by Qdrant (provider-managed) |
| **Access control** | API key via `SSA_QDRANT_API_KEY` |
| **Collection** | `student_cases` (384-dim BGE embeddings) |

### 5.3 Data Classification

| Classification | Examples | Storage |
|----------------|----------|---------|
| **Student academic data** | Grades, attendance, failures, study time | PostgreSQL, Qdrant |
| **Personally identifiable information** | Student IDs (opaque identifiers, not SSN/names), parent email addresses | PostgreSQL |
| **Advisor data** | Feedback ratings, notes, follow-up assessments | PostgreSQL |
| **Credentials** | Auth token secret, API keys, database passwords | Environment variables only |

**Important:** The system does not store names, social security numbers, dates of birth, or any sensitive PII beyond what is typical for academic records. Student IDs are school-assigned identifiers.

---

## 6. Open Issues and Recommendations

### 6.1 Open Issues

| # | Issue | Severity | Impact | Status |
|---|-------|----------|--------|--------|
| 1 | No rate limiting | **High** | Brute-force login attacks, API abuse, DoS | Unaddressed |
| 2 | No audit logging | **High** | Cannot trace data access, no forensic capability | Unaddressed |
| 3 | No RBAC | **Medium** | All authenticated users have full access; no principle of least privilege | Unaddressed |
| 4 | No HTTPS in app code | **Medium** | Traffic between reverse proxy and application is HTTP; depends on network segmentation | Expected (see §6.2.1) |
| 5 | No API key rotation | **Medium** | Secrets cannot be rotated without application restart or config change | Unaddressed |
| 6 | Single static credential | **Medium** | `SSA_AUTH_USERNAME` / `SSA_AUTH_PASSWORD` is a single shared credential | Unaddressed |
| 7 | Token secret not auto-generated | **Low** | Default `SSA_AUTH_TOKEN_SECRET` is a placeholder; must be changed manually | Documented in `.env.example` |

### 6.2 Recommendations

#### 6.2.1 Implement Rate Limiting (High Priority)

Add rate limiting middleware to protect against brute-force attacks on `/auth/login` and DoS on API endpoints.

```
POST /auth/login       → 5 requests/minute per IP
POST /api/v1/*         → 100 requests/minute per token
GET  /api/v1/*         → 300 requests/minute per token
```

**Suggested approach:** Use `slowapi` (FastAPI-compatible) with Redis backend for distributed rate tracking, or in-memory rate limiting for single-instance deployments.

#### 6.2.2 Add Audit Logging (High Priority)

Implement structured audit logging for all data-access operations:

| Event | Fields to Log |
|-------|---------------|
| Authentication success/failure | Timestamp, source IP, username, outcome |
| Data access (search, predict, recommend) | Timestamp, user, endpoint, student_id(s) |
| Data mutation (feedback, follow-up updates) | Timestamp, user, resource ID, action |
| Admin operations | Timestamp, user, operation, parameters |

Logs should be written to a separate, append-only destination (e.g., AWS CloudWatch, a dedicated log index) with access restricted to security personnel.

#### 6.2.3 Implement Role-Based Access Control (Medium Priority)

| Role | Permissions |
|------|-------------|
| `advisor` | Read/write on student cases, feedback, follow-up |
| `admin` | All `advisor` permissions + admin operations (ingest, train, embeddings) |
| `viewer` | Read-only on analysis results, no mutations |

#### 6.2.4 Enforce HTTPS (Medium Priority)

Configure the reverse proxy to:
1. Terminate TLS at the edge
2. Set `Strict-Transport-Security` header
3. Forward requests to the FastAPI app over the internal network (HTTP acceptable within VPC)

#### 6.2.5 Introduce API Key Rotation (Medium Priority)

- Version secret values and support multiple concurrent valid secrets
- Add a `/auth/rotate` endpoint or configuration reload mechanism
- Recommended: use a secrets manager (e.g., AWS Secrets Manager, HashiCorp Vault)

#### 6.2.6 Strengthen Authentication (Medium Priority)

- Replace single static credential with per-user accounts
- Integrate with institutional SSO (SAML/OIDC/SAML) for existing identity providers
- If SSO is not feasible, implement password hashing (bcrypt/argon2) instead of environment-variable comparison

#### 6.2.7 Additional Recommendations

| Recommendation | Priority | Description |
|---------------|----------|-------------|
| Input size limits on LLM prompts | Low | Cap user prompt length to prevent token exhaustion attacks |
| Prompt output validation | Low | Validate LLM output structure before returning to client |
| Dependency vulnerability scanning | Medium | Regular `uv audit` or `pip-audit` runs in CI/CD |
| Container image scanning | Medium | If containerized, scan images for known CVEs |
| Secrets scanning pre-commit | Low | Add `trufflehog` or `git-secrets` to pre-commit hooks |

---

## 7. Security Checklist

### 7.1 Authentication & Authorization

- [x] HMAC-SHA256 bearer token (not JWT)
- [x] Constant-time credential comparison (`hmac.compare_digest`)
- [x] Token expiry enforcement (configurable TTL)
- [x] FastAPI dependency-based auth on all protected routes
- [x] Minimal public endpoints (health, ready, login, me)
- [ ] Rate limiting on login endpoint
- [ ] RBAC or permission model
- [ ] Multi-factor authentication
- [ ] Account lockout after failed attempts

### 7.2 Secrets & Configuration

- [x] Environment variables for all secrets (SSA_ prefix)
- [x] Pydantic Settings for type-safe config loading
- [x] `.env` excluded from version control
- [x] `.env.example` committed with placeholder values only
- [x] Template `.gitignore` with `.env` entry
- [ ] Secrets management solution (vault, secrets manager)
- [ ] Automated secret rotation

### 7.3 API Security

- [x] CORS with origin allowlist
- [x] Pydantic validation on all request bodies
- [x] Generic error messages (no stack traces)
- [x] Bearer token required for data endpoints
- [ ] Rate limiting
- [ ] Request body size limits
- [ ] API key rotation mechanism
- [ ] OpenAPI spec doesn't expose secrets

### 7.4 LLM Security

- [x] Structured schema input for LLM-bound data
- [x] Template-based prompt construction
- [x] Dataset-scoped prompt guardrails
- [x] Deterministic fallbacks for all LLM features
- [x] Local Ollama option (no data leaves host)
- [ ] Output validation/sanitization
- [ ] Prompt injection penetration testing
- [ ] Rate limits on LLM calls

### 7.5 Transport Security

- [x] TLS on PostgreSQL (Aiven managed)
- [x] TLS on Qdrant (cloud endpoint)
- [x] TLS option for SMTP (STARTTLS, configurable)
- [ ] HTTPS in application code
- [ ] HSTS headers
- [ ] mTLS for service-to-service communication

### 7.6 Data Storage

- [x] At-rest encryption handled by cloud providers
- [x] Minimal PII (no names, SSNs, DOBs)
- [x] Connection strings with embedded credentials
- [ ] Encryption at rest key management documented
- [ ] Data retention and deletion policy
- [ ] Regular backup and recovery testing

### 7.7 Monitoring & Incident Response

- [ ] Audit logging for data access
- [ ] Failed authentication logging
- [ ] Alerting on anomaly detection
- [ ] Incident response plan
- [ ] Security contact information

### 7.8 Dependency Security

- [ ] Regular vulnerability scanning (Dependabot, `uv audit`)
- [ ] Lockfile checked in (`uv.lock`)
- [ ] Minimal dependency footprint
- [ ] Container image signing (if containerized)

---

## Security Contacts

For security concerns, vulnerabilities, or incident reporting related to this project, please contact the project maintainer or open a GitHub issue on the repository.

---

*This document should be reviewed and updated as part of the development lifecycle, particularly when new authentication mechanisms, data stores, or LLM integrations are introduced.*
