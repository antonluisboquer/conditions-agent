# Conditions Agent Architecture

## Overview

The Conditions Agent is a **LangGraph-based orchestrator** that coordinates external services to evaluate whether uploaded loan documents satisfy predicted conditions. It focuses on orchestration, guardrails, and persistence while delegating LLM evaluation to the specialized Conditions AI service.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         External Services                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │ Predicted        │  │ Rack & Stack     │  │ Conditions   │  │
│  │ Conditions API   │  │ API              │  │ AI API       │  │
│  │                  │  │                  │  │              │  │
│  │ • Predicts loan  │  │ • Classifies     │  │ • Multi-LLM  │  │
│  │   conditions     │  │   documents      │  │   evaluation │  │
│  │ • Returns list   │  │ • Extracts       │  │ • GPT-5 mini │  │
│  │   of required    │  │   entities       │  │ • Claude 4.5 │  │
│  │   docs           │  │ • Returns JSON   │  │ • GPT-5      │  │
│  └────────┬─────────┘  └────────┬─────────┘  └──────┬───────┘  │
│           │                     │                     │          │
└───────────┼─────────────────────┼─────────────────────┼──────────┘
            │                     │                     │
            │                     │                     │
            ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Conditions Agent                            │
│                  (LangGraph Orchestrator)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                   LangGraph State Machine                  │  │
│  ├───────────────────────────────────────────────────────────┤  │
│  │                                                             │  │
│  │  ┌─────────────────┐      ┌─────────────────┐            │  │
│  │  │ Load Conditions │──────│ Load Documents  │            │  │
│  │  └─────────────────┘      └────────┬────────┘            │  │
│  │                                     │                      │  │
│  │                          ┌──────────▼──────────┐          │  │
│  │                          │ Call Conditions AI  │          │  │
│  │                          └──────────┬──────────┘          │  │
│  │                                     │                      │  │
│  │                          ┌──────────▼──────────┐          │  │
│  │                          │ Apply Guardrails    │          │  │
│  │                          └──────────┬──────────┘          │  │
│  │                                     │                      │  │
│  │                          ┌──────────▼──────────┐          │  │
│  │                          │ Confidence Router   │          │  │
│  │                          └─────┬──────────┬────┘          │  │
│  │                                │          │                │  │
│  │                          ≥0.7  │          │ <0.7           │  │
│  │                                │          │                │  │
│  │                   ┌────────────▼──┐  ┌───▼──────────┐    │  │
│  │                   │ Store Results │  │ Human Review │    │  │
│  │                   └───────────────┘  └──────┬───────┘    │  │
│  │                                              │             │  │
│  │                                    ┌─────────▼─────────┐  │  │
│  │                                    │  Store Results    │  │  │
│  │                                    └───────────────────┘  │  │
│  │                                                             │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    Supporting Components                   │  │
│  ├───────────────────────────────────────────────────────────┤  │
│  │                                                             │  │
│  │  • Guardrails Validator                                    │  │
│  │    - Confidence thresholds                                 │  │
│  │    - Hallucination detection                               │  │
│  │    - Business rules enforcement                            │  │
│  │    - Cost/latency limits                                   │  │
│  │                                                             │  │
│  │  • Tracing Manager (LangSmith)                             │  │
│  │    - Execution traces                                      │  │
│  │    - Token/cost tracking                                   │  │
│  │    - Latency monitoring                                    │  │
│  │    - Tagging & search                                      │  │
│  │                                                             │  │
│  │  • Database Repository                                     │  │
│  │    - Execution tracking                                    │  │
│  │    - Evaluation storage                                    │  │
│  │    - RM feedback collection                                │  │
│  │    - Loan state management                                 │  │
│  │                                                             │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                   │
└───────────────────────────────┬───────────────────────────────────┘
                                │
                                ▼
                 ┌──────────────────────────────┐
                 │      FastAPI Endpoints       │
                 ├──────────────────────────────┤
                 │ POST /evaluate-conditions    │
                 │ POST /feedback               │
                 │ GET  /executions/:id         │
                 │ GET  /loans/:guid/state      │
                 │ GET  /health                 │
                 └──────────────┬───────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   Client Applications  │
                    │   (Brokers, RMs, UI)   │
                    └───────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                       Data Storage Layer                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    PostgreSQL Database                    │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │                                                            │  │
│  │  • agent_executions       - High-level tracking          │  │
│  │  • condition_evaluations  - Per-condition results        │  │
│  │  • rm_feedback            - RM corrections/feedback      │  │
│  │  • loan_state             - Current loan status          │  │
│  │  • business_rules         - Configurable rules           │  │
│  │                                                            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    Observability & Monitoring                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────┐         ┌──────────────────┐             │
│  │   LangSmith      │         │ Structured Logs  │             │
│  │                  │         │                  │             │
│  │ • Full traces    │         │ • JSON format    │             │
│  │ • Token usage    │         │ • execution_id   │             │
│  │ • Cost tracking  │         │ • timestamps     │             │
│  │ • Latency graphs │         │ • error details  │             │
│  │ • Search by tags │         │ • confidence     │             │
│  └──────────────────┘         └──────────────────┘             │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Request Initiation

```
Broker/UI → POST /api/v1/evaluate-conditions
           {
             "loan_guid": "loan_123",
             "condition_doc_ids": ["doc_001", "doc_002"]
           }
```

### 2. State Initialization

```python
AgentState {
  loan_guid: "loan_123",
  condition_doc_ids: ["doc_001", "doc_002"],
  execution_metadata: {
    execution_id: UUID,
    started_at: timestamp,
    trace_id: LangSmith_trace_id
  }
}
```

### 3. Node Execution Sequence

```
load_conditions_node
  ↓ GET /predicted-conditions/loan_123
  ↓ Returns: List[Condition]
  
load_documents_node
  ↓ POST /rack-and-stack/documents
  ↓ Returns: List[DocumentData]
  
call_conditions_ai_node
  ↓ POST /conditions-ai/evaluate
  ↓ Returns: EvaluationResponse {
  ↓   evaluations: List[ConditionEvaluationResult],
  ↓   total_tokens: 2500,
  ↓   cost_usd: 0.15,
  ↓   model_breakdown: {...}
  ↓ }
  
apply_guardrails_node
  ↓ validate_evaluations()
  ↓ - Check confidence thresholds
  ↓ - Validate citations
  ↓ - Apply business rules
  ↓ Returns: (validated_evals, requires_review, issues)
  
confidence_router_node
  ↓ if requires_review → human_review_node
  ↓ else → store_results_node
  
store_results_node
  ↓ INSERT INTO agent_executions
  ↓ INSERT INTO condition_evaluations
  ↓ UPDATE loan_state
```

### 4. Response

```json
{
  "execution_id": "UUID",
  "status": "completed",
  "requires_human_review": false,
  "evaluations": [...],
  "trace_url": "https://smith.langchain.com/...",
  "metadata": {
    "total_tokens": 2500,
    "cost_usd": 0.15,
    "latency_ms": 1850
  }
}
```

## Component Details

### LangGraph State

The `AgentState` TypedDict flows through the graph:

```python
{
  # Input
  "loan_guid": str,
  "condition_doc_ids": List[str],
  
  # Loaded Data
  "conditions": List[Condition],
  "uploaded_docs": List[DocumentData],
  
  # Evaluation Results
  "conditions_ai_response": EvaluationResponse,
  "evaluations": List[ConditionEvaluationResult],
  "confidence_scores": Dict[str, float],
  
  # Decision Flags
  "requires_human_review": bool,
  "validation_issues": List[str],
  
  # Metadata
  "execution_metadata": ExecutionMetadata,
  "status": str,
  "error": Optional[str]
}
```

### Guardrails

1. **Confidence Threshold**: Min 0.7 for auto-approval
2. **Citation Validation**: "satisfied" results must cite documents
3. **Business Rules**: Loaded from PostgreSQL, applied dynamically
4. **Cost Limits**: Default $5.00 per execution
5. **Timeout Protection**: 30-second execution limit

### Tracing

Every execution is automatically traced with:

- **Run Tree**: Complete graph execution
- **Tags**: `loan_guid`, `execution_id`, `agent_name`, `condition_id`
- **Metadata**: Tokens, cost, latency, model breakdown
- **Errors**: Full stack traces for failures

## Database Schema

### agent_executions
High-level execution tracking with status, timestamps, costs.

### condition_evaluations
Per-condition results with confidence, reasoning, citations.

### rm_feedback
Relationship Manager corrections for continuous improvement.

### loan_state
Current status of each loan through the pipeline.

### business_rules
Configurable validation rules with JSON configuration.

## Security & Compliance

- **Audit Trail**: Every decision stored in PostgreSQL
- **Traceability**: Full execution graph in LangSmith
- **Feedback Loop**: RM corrections tracked for improvement
- **Cost Control**: Budget alerts and limits
- **Error Handling**: Graceful degradation with logging

## Scalability

- **Async I/O**: All external calls are async
- **Connection Pooling**: PostgreSQL connection pool
- **Stateless**: Agent can be horizontally scaled
- **Caching**: External service responses cacheable
- **Rate Limiting**: Can be added at API gateway level

## Multi-Model Strategy (In Conditions AI)

The Conditions AI service handles model routing:

| Model | Use Case | Workload | Cost/1M Tokens |
|-------|----------|----------|----------------|
| GPT-5 mini | Simple matching | 60% | $0.25 in / $2.00 out |
| Claude Sonnet 4.5 | Complex reasoning | 20% | $3.00 in / $15.00 out |
| GPT-5 | Agentic orchestration | 15% | $1.25 in / $10.00 out |
| Claude Haiku 4.5 | Fallback | 5% | $0.25 in / $1.25 out |

**Total Cost**: ~$0.15 per condition evaluation

## Future Enhancements

1. **Caching Layer**: Redis for frequently accessed conditions
2. **Batch Processing**: Evaluate multiple loans in parallel
3. **Real-time Updates**: WebSocket notifications for long-running evals
4. **A/B Testing**: Compare different guardrail configurations
5. **Analytics Dashboard**: Real-time metrics and trends
6. **Auto-tuning**: Adjust confidence thresholds based on RM feedback

## Monitoring & Alerts

### Key Metrics

- **Execution Success Rate**: Target >95%
- **Human Review Rate**: Target <20%
- **Average Latency**: Target <3s
- **Cost per Execution**: Target <$0.20
- **Token Efficiency**: Track tokens/condition

### Alerts

- Execution failure rate >5%
- Cost exceeds budget
- Latency >5s (95th percentile)
- Database connection failures
- External service timeouts

## Development Workflow

1. **Local Development**: Run with mocked services
2. **Integration Testing**: Test with staging APIs
3. **LangSmith Review**: Analyze traces before deployment
4. **Staging Deployment**: Full system test
5. **Production Deployment**: Blue-green deployment
6. **Monitoring**: Watch metrics and traces
7. **Feedback Loop**: Collect RM feedback
8. **Continuous Improvement**: Update based on feedback

