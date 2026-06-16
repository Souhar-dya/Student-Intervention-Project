# System Diagrams — AI-Powered Student Success Assistant

> Mermaid diagrams for architecture, data flow, and process visualization.
> Render with any Mermaid-compatible viewer (VS Code, GitHub, mermaid.live).

---

## 1. High-Level System Architecture

```mermaid
C4Context
    title System Context — Student Success Assistant

    Person(advisor, "Student Advisor", "University staff who monitors at-risk students")
    Person(student, "Student", "Receives intervention recommendations")

    System(ssa, "Student Success Assistant", "AI-powered system that predicts at-risk students and recommends interventions")

    System_Ext(db, "PostgreSQL (Aiven)", "Relational data store\nstudents, cases, feedback, evaluations, follow-ups")
    System_Ext(qdrant, "Qdrant Cloud", "Vector database\n384-dim BGE embeddings + payload metadata")
    System_Ext(llm, "Ollama (Local)", "LLM inference\nllama3.2:3b on port 11434")
    System_Ext(smtp, "SMTP (optional)", "Parent notification emails")

    Rel(advisor, ssa, "Uses", "HTTPS (5173)")
    Rel(ssa, db, "Reads/Writes", "psycopg (TLS)")
    Rel(ssa, qdrant, "Searches/Indexes", "REST (TLS)")
    Rel(ssa, llm, "Invokes", "HTTP (localhost:11434)")
    Rel(ssa, smtp, "Sends", "SMTP (TLS)")
```

---

## 2. Hexagonal Architecture (Ports & Adapters)

```mermaid
block-beta
    columns 3

    block:adapters_out("Outbound Adapters"):1
        l1("PostgresAdapter")
        l2("QdrantAdapter")
        l3("OllamaAdapter")
        l4("SmtpAdapter")
    end

    block:ports("Ports"):1
        m1("StudentRepository")
        m2("CaseRepository")
        m3("FeedbackRepository")
        m4("FollowUpRepository")
        m5("LLMClient")
        m6("EmbeddingService")
    end

    block:app("Application"):1
        r1("PredictionService")
        r2("RetrievalService")
        r3("RecommendationService")
        r4("EvaluationService")
        r5("FollowUpService")
        r6("InsightService")
    end

    block:domain("Domain"):1
        d1("StudentProfile")
        d2("RiskCategory")
        d3("JudgeScores")
        d4("FollowUpCase")
        d5("FeedbackEntry")
    end

    block:api("API Layer"):1
        a1("FastAPI Routes")
        a2("Pydantic Schemas")
        a3("Auth Middleware")
    end

    adapters_out --> ports
    ports --> app
    app --> domain
    app --> api
```

---

## 3. RAG Pipeline

```mermaid
flowchart LR
    A[Query] --> B[Metadata Filtering]
    B --> C[Dense Search<br/>Qdrant + BGE<br/>top_k=50]
    B --> D[Sparse Search<br/>BM25 via Qdrant<br/>top_k=50]
    C --> E[RRF Fusion<br/>k=60]
    D --> E
    E --> F[Top 20]
    F --> G[BGE Reranker<br/>Cross-Encoder]
    G --> H[Top 5 Cases]
    H --> I[LLM Recommendation]
    I --> J[Final Plan]
```

---

## 4. LangGraph Agent Workflow

```mermaid
stateDiagram-v2
    [*] --> RetrievalAgent
    RetrievalAgent --> PredictionAgent : cases + query
    PredictionAgent --> RecommendationAgent : risk + drivers
    RecommendationAgent --> ExplanationAgent : plan
    ExplanationAgent --> [*] : final response

    state RetrievalAgent {
        [*] --> HybridSearch
        HybridSearch --> Rerank
        Rerank --> FormatContext
        FormatContext --> [*]
    }

    state PredictionAgent {
        [*] --> LoadModel
        LoadModel --> ComputeRisk
        ComputeRisk --> IdentifyDrivers
        IdentifyDrivers --> [*]
    }

    state RecommendationAgent {
        [*] --> BuildPrompt
        BuildPrompt --> InvokeLLM
        InvokeLLM --> ParseResponse
        ParseResponse --> [*]
    }

    state ExplanationAgent {
        [*] --> LoadSHAP
        LoadSHAP --> ComputeContributions
        ComputeContributions --> FormatExplanation
        FormatExplanation --> [*]
    }
```

---

## 5. Fallback Architecture

```mermaid
flowchart TD
    subgraph LLM_Fallback["LLM Chain"]
        A[LangGraph Agent] -->|fails| B[Direct LLM Call]
        B -->|fails| C[Drafted Intervention Plan]
    end

    subgraph Eval_Fallback["Evaluation Chain"]
        D[LLM-as-Judge] -->|fails or invalid JSON| E[Rubric Baseline]
    end

    subgraph FollowUp_Fallback["Follow-Up Chain"]
        F[LLM Assessment] -->|fails| G[Signal-Counting Rubric]
    end

    subgraph Retrieval_Fallback["Retrieval Chain"]
        H[Hybrid Search] -->|fails| I[Repository Search]
        I -->|fails| J[Synthetic Data]
    end

    subgraph Prediction_Fallback["Prediction Chain"]
        K[ML Artifact] -->|missing| L[Baseline Advisor Score]
    end

    subgraph Embed_Fallback["Embedding Chain"]
        M[Sentence-Transformers] -->|fails| N[Hash-Based Fallback]
    end
```

---

## 6. Follow-Up Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Open: Case Created
    Open --> Assessed: Advisor clicks Assess
    Assessed --> Closed: Advisor closes
    Open --> Closed: Auto-close (Low Risk)

    state Open {
        [*] --> AwaitingReview
        AwaitingReview --> LLMAssessment
        LLMAssessment --> WaitForAdvisor
        WaitForAdvisor --> Assessed
    }

    state Assessed {
        [*] --> DecisionRecorded
        DecisionRecorded --> [*]
    }

    Closed --> [*]
```

---

## 7. ER Diagram

```mermaid
erDiagram
    students {
        text student_id PK
        text school
        int age
        int attendance
        int failures
        int absences
        int study_time
        float previous_grade_average
        int final_grade
        text outcome
        jsonb raw_payload
    }

    student_cases {
        text case_id PK
        text student_id FK
        text case_text
        jsonb payload
    }

    feedback {
        text feedback_id PK
        text query
        text recommendation
        text rating
        text advisor_note
        timestamptz created_at
    }

    evaluation_results {
        text evaluation_id PK
        text query
        text recommendation
        jsonb scores
        text notes
        timestamptz created_at
    }

    follow_up_cases {
        text case_id PK
        text student_id FK
        jsonb student_profile
        text parent_email
        text school
        text risk_category
        float risk_score
        text model_name
        text recommendation
        text recommendation_summary
        jsonb evidence_case_ids
        text note
        text status
        text escalation_target
        text last_event
        text plan_followed
        text attendance_trend
        text marks_trend
        text failures_trend
        text follow_up_decision
        text follow_up_rationale
        text follow_up_next_steps
        float follow_up_confidence
        text follow_up_generated_by
        timestamptz follow_up_assessed_at
        timestamptz closed_at
        timestamptz created_at
        timestamptz updated_at
    }

    follow_up_events {
        text event_id PK
        text case_id FK
        text event_type
        text title
        text note
        jsonb payload
        timestamptz created_at
    }

    students ||--o{ student_cases : "has"
    students ||--o{ follow_up_cases : "referenced in"
    follow_up_cases ||--o{ follow_up_events : "tracks"
```

---

## 8. Evaluation (LLM-as-Judge) Flow

```mermaid
flowchart LR
    A[Query + Recommendation + Evidence] --> B[Build Judge Prompt]
    B --> C[Invoke LLM]
    C --> D{JSON Valid?}
    D -->|Yes| E[Parse JudgeScores]
    D -->|No| F[Regex: quote unquoted keys]
    F --> G{Valid now?}
    G -->|Yes| E
    G -->|No| H[Rubric Baseline]

    E --> I[Compute Overall<br/>(relevance + groundedness + consistency + usefulness) / 4]
    H --> I
    I --> J[Store in evaluation_results]
    J --> K[Return EvaluationResponse]
```

---

## 9. Frontend Screen Flow

```mermaid
flowchart LR
    A[LoginPage] --> B[DashboardPage]

    B --> C[Prepare Tab]
    B --> D[Student Tab]
    B --> E[Factors Tab]
    B --> F[Analysis Tab]
    B --> G[Evaluate Tab]
    B --> H[Follow-Up Tab]

    C --> C1[Init Storage]
    C --> C2[Ingest Dataset]
    C --> C3[Build Embeddings]
    C --> C4[Train Models]

    D --> D1[Load Student]
    D --> D2[Predict Risk]
    D --> D3[Search Cases]
    D --> D4[Recommend]
    D --> D5[Parent Email]

    E --> E1[Factor Analysis]
    E --> E2[Guardrail Check]

    F --> F1[Full Analysis]
    F --> F2[SHAP Explanation]
    F --> F3[Feedback Buttons]

    G --> G1[Evaluate with LLM Judge]
    G --> G2[Score Display]

    H --> H1[Load Follow-Up Cases]
    H --> H2[View Detail]
    H --> H3[Assess / Close]
    H --> H4[History Timeline]
```

---

## 10. Feedback Loop

```mermaid
flowchart LR
    subgraph Advisor["Advisor Workflow"]
        A[View Recommendation] --> B[Rate: Useful / Not Useful]
        B --> C[Optional Note]
    end

    subgraph Storage["Storage"]
        D[feedback table<br/>PostgreSQL]
    end

    subgraph Retrieval["Retrieval Enhancement"]
        E[Retrieve Feedback<br/>for Similar Queries]
        F[Inject into<br/>Recommendation Prompt]
    end

    A --> D
    C --> D
    D --> E
    E --> F
    F --> G[Better Recommendations]
    G -.-> A
```

---

## 11. Risk Prediction Pipeline

```mermaid
flowchart LR
    A[Student Features] --> B{Model Available?}
    B -->|Yes| C[Load ML Artifact]
    B -->|No| D[Baseline Formula]

    C --> E{XGBoost}
    C --> F{Logistic Regression}
    C --> G{Random Forest}

    E --> H[SHAP TreeExplainer]
    F --> H
    G --> H

    H --> I[Risk Score]
    D --> I

    I --> J{Score >= 0.62?}
    J -->|Yes| K[High Risk]
    J -->|No| L{Score >= 0.32?}
    L -->|Yes| M[Medium Risk]
    L -->|No| N[Low Risk]

    K --> O[Top Contributors]
    M --> O
    N --> O
```
