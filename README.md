# Conditions Agent

A LangGraph-based orchestrator for loan conditions evaluation in the mortgage underwriting process. This agent coordinates external services (Predicted Conditions API, Rack & Stack API, Conditions AI API) to evaluate whether uploaded documents satisfy loan conditions, with full observability through LangSmith tracing and PostgreSQL audit trails.

## Architecture Overview

The Conditions Agent is an **orchestrator** that:

1. **Loads predicted conditions** from the Predicted Conditions API
2. **Retrieves document data** from Rack & Stack API (classification + extraction)
3. **Calls Conditions AI API** for LLM-based evaluation (multi-model routing handled internally)
4. **Applies guardrails** to validate results and detect hallucinations
5. **Routes decisions** based on confidence thresholds
6. **Stores audit trail** in PostgreSQL for compliance and continuous improvement

### Key Clarification

The actual LLM-based evaluation and multi-model routing (GPT-5 mini, Claude Sonnet 4.5, GPT-5, Claude Haiku 4.5) happens **inside the Conditions AI service**, not in this agent. This agent focuses on orchestration, guardrails, routing, and persistence.

## Project Structure

```
conditions-agent/
├── agent/
│   ├── __init__.py
│   ├── graph.py          # LangGraph orchestrator definition
│   ├── state.py          # State schema (TypedDict)
│   └── nodes.py          # Node implementations
├── api/
│   ├── __init__.py
│   └── main.py           # FastAPI endpoints
├── config/
│   ├── __init__.py
│   └── settings.py       # Configuration management
├── database/
│   ├── __init__.py
│   ├── schema.sql        # PostgreSQL schema (template)
│   ├── models.py         # SQLAlchemy models
│   └── repository.py     # Database operations
├── services/
│   ├── __init__.py
│   ├── predicted_conditions.py  # Mocked Predicted Conditions API
│   ├── rack_and_stack.py        # Mocked Rack & Stack API
│   └── conditions_ai.py         # Mocked Conditions AI API
├── utils/
│   ├── __init__.py
│   ├── logging_config.py # Structured JSON logging
│   ├── tracing.py        # LangSmith integration
│   └── guardrails.py     # Validation & safety checks
├── .env.example          # Environment variables template
├── requirements.txt      # Python dependencies
└── README.md
```

## Features

### 🔄 LangGraph Orchestration
- State machine workflow with conditional routing
- Async execution for performance
- Automatic retry and error handling
- Full execution graph visualization

### 📊 LangSmith Tracing
- Complete execution traces with loan_guid tagging
- Token usage and cost tracking
- Latency monitoring
- Model breakdown analytics
- Searchable by loan_guid, condition_id, execution_id

### 🛡️ Guardrails & Validation
- Confidence threshold checking (default: 0.7)
- Hallucination detection via citation validation
- Business rules enforcement (19 configurable rules)
- Cost and latency budget enforcement
- Automatic flagging for human review

### 💾 PostgreSQL Audit Trail
- Complete execution history
- Condition-level evaluation storage
- RM feedback collection for continuous improvement
- Loan state persistence
- Configurable business rules

### 🔌 External Service Integration
- Predicted Conditions API client (mocked, ready for integration)
- Rack & Stack API client (mocked, ready for integration)
- Conditions AI API client (mocked, ready for integration)
- Async HTTP clients with timeout handling

## Installation

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- LangSmith account (for tracing)

### Setup

1. **Clone the repository**
```bash
git clone https://git.cybersoftbpo.com/naomi.amparo/conditions-agent.git
cd conditions-agent
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up PostgreSQL database**
```bash
createdb conditions_agent
psql conditions_agent < database/schema.sql
```

5. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your configuration
```

Required environment variables:
- `LANGSMITH_API_KEY`: Your LangSmith API key
- `DATABASE_URL`: PostgreSQL connection string
- `PREDICTED_CONDITIONS_API_URL`: Predicted Conditions service endpoint
- `RACK_AND_STACK_API_URL`: Rack & Stack service endpoint
- `CONDITIONS_AI_API_URL`: Conditions AI service endpoint

## Usage

### Starting the API Server

```bash
# Development
uvicorn api.main:app --reload --port 8000

# Production
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### API Endpoints

#### Evaluate Conditions

```bash
POST /api/v1/evaluate-conditions
Content-Type: application/json

{
  "loan_guid": "loan_123",
  "condition_doc_ids": ["doc_001", "doc_002", "doc_003"]
}
```

Response:
```json
{
  "execution_id": "550e8400-e29b-41d4-a716-446655440000",
  "loan_guid": "loan_123",
  "status": "completed",
  "requires_human_review": false,
  "evaluations": [
    {
      "condition_id": "cond_001",
      "condition_text": "Provide proof of income for the last 2 years",
      "result": "satisfied",
      "confidence": 0.95,
      "reasoning": "W-2 form for 2024 provided showing annual wages of $85,000",
      "model_used": "gpt-5-mini",
      "citations": ["doc_001"]
    }
  ],
  "validation_issues": [],
  "trace_url": "https://smith.langchain.com/o/conditions-agent/runs/...",
  "metadata": {
    "total_tokens": 2500,
    "cost_usd": 0.15,
    "latency_ms": 1850,
    "model_breakdown": {
      "gpt-5-mini": 2,
      "claude-sonnet-4.5": 2
    }
  }
}
```

#### Submit RM Feedback

```bash
POST /api/v1/feedback
Content-Type: application/json

{
  "evaluation_id": "eval_uuid",
  "rm_user_id": "rm_john_doe",
  "feedback_type": "correct",
  "corrected_result": "unsatisfied",
  "notes": "Document is outdated, needs 2024 version"
}
```

#### Get Execution Details

```bash
GET /api/v1/executions/{execution_id}
```

#### Get Loan State

```bash
GET /api/v1/loans/{loan_guid}/state
```

#### Health Check

```bash
GET /health
```

## LangGraph Workflow

The agent follows this execution flow:

```
┌─────────────────┐
│ Load Conditions │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Load Documents  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Call            │
│ Conditions AI   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Apply           │
│ Guardrails      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Confidence      │
│ Router          │
└─────┬───────┬───┘
      │       │
  ≥0.7│       │<0.7
      │       │
      ▼       ▼
┌─────────┐ ┌────────────┐
│ Store   │ │ Human      │
│ Results │ │ Review     │
└─────────┘ └─────┬──────┘
                   │
                   ▼
             ┌─────────┐
             │ Store   │
             │ Results │
             └─────────┘
```

### Node Descriptions

1. **load_conditions_node**: Fetches predicted conditions from API
2. **load_documents_node**: Retrieves rack & stack results for documents
3. **call_conditions_ai_node**: Calls external Conditions AI for evaluation
4. **apply_guardrails_node**: Validates results, checks citations, applies business rules
5. **confidence_router_node**: Routes based on confidence threshold
6. **human_review_node**: Flags uncertain cases for RM review
7. **store_results_node**: Persists all results to PostgreSQL

## Database Schema

The PostgreSQL schema includes:

- **agent_executions**: High-level execution tracking
- **condition_evaluations**: Detailed evaluation results
- **rm_feedback**: Relationship Manager feedback
- **loan_state**: Current loan status
- **business_rules**: Configurable validation rules

**Note**: The schema in `database/schema.sql` is a template and will be finalized later.

## Monitoring & Observability

### LangSmith Tracing

Every execution is automatically traced with:
- Full execution graph
- Token usage per model
- Cost breakdown
- Latency metrics
- Custom tags (loan_guid, condition_id, execution_id)

Access traces at: `https://smith.langchain.com/o/conditions-agent/`

### Structured Logging

JSON-formatted logs with:
- `execution_id`: Unique execution identifier
- `decision`: Agent routing decisions
- `confidence`: Model confidence scores
- `model_used`: Which model handled each condition
- `tokens_used`: Token consumption
- `cost_usd`: Estimated cost
- `latency_ms`: Execution time

## Guardrails

The agent implements multiple layers of validation:

1. **Confidence Threshold**: Flags evaluations below 0.7 confidence
2. **Citation Validation**: Ensures all "satisfied" results reference actual documents
3. **Business Rules**: Configurable rules stored in PostgreSQL
4. **Cost Limits**: Prevents runaway costs (default: $5 per execution)
5. **Timeout Protection**: 30-second execution limit

## Continuous Improvement

The system supports a feedback flywheel:

1. **RM provides feedback** via `/api/v1/feedback` endpoint
2. **Feedback stored** with full execution context in PostgreSQL
3. **Weekly analysis** of patterns (can be implemented separately)
4. **Prompt/rule updates** based on feedback
5. **Measure improvement** through LangSmith metrics

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Code Quality

```bash
# Format code
black .

# Lint code
ruff check .

# Type checking
mypy .
```

### Mock Services

All external services are currently mocked with realistic responses:
- `services/predicted_conditions.py`: Returns 4 sample conditions
- `services/rack_and_stack.py`: Returns 3 sample documents
- `services/conditions_ai.py`: Returns evaluation results with different models

To integrate real services, update the client classes to make actual HTTP calls (commented examples provided in code).

## Configuration

Key configuration options in `.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `CONFIDENCE_THRESHOLD` | Minimum confidence for auto-approval | 0.7 |
| `MAX_EXECUTION_TIMEOUT_SECONDS` | Execution timeout | 30 |
| `COST_BUDGET_USD_PER_EXECUTION` | Maximum cost per execution | 5.0 |
| `LANGSMITH_PROJECT` | LangSmith project name | conditions-agent |
| `DATABASE_POOL_SIZE` | PostgreSQL connection pool size | 10 |

## Troubleshooting

### LangSmith Traces Not Appearing

Ensure these environment variables are set:
```bash
LANGSMITH_TRACING_V2=true
LANGSMITH_API_KEY=your_key_here
LANGSMITH_PROJECT=conditions-agent
```

### Database Connection Errors

Check PostgreSQL connection string format:
```bash
DATABASE_URL=postgresql://user:password@localhost:5432/conditions_agent
```

### Import Errors

Ensure all dependencies are installed:
```bash
pip install -r requirements.txt
```

## Production Deployment

### Docker (Recommended)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### Environment Variables

In production, use a secrets manager (AWS Secrets Manager, Azure Key Vault, etc.) for:
- `LANGSMITH_API_KEY`
- `DATABASE_URL`
- API endpoint credentials

## License

Proprietary - CYBERSOFT

## Contributing

For internal development only. Contact the team lead for contribution guidelines.

## Support

For questions or issues, contact:
- Team: conditions-ai@cybersoftbpo.com
- Slack: #conditions-agent
