# ReWOO Agent Transformation Plan

## Architecture Comparison

### Current (Deterministic Orchestrator)

```
Input → PreConditions → Transform → Conditions AI → Classify → Route → Store
```

- Fixed sequence, no reasoning
- Cannot adapt to different scenarios
- Limited to predefined workflow

### Target (ReWOO Agent)

```
Hybrid Input → Planner (Plan) → Worker (Execute) → Solver (Synthesize) → Stream Results
```

- Reasoning-driven execution
- Adapts to natural language instructions
- Can handle expanded use cases

## Key Changes

### 1. Hybrid Input Schema

**New Request Format** (`api/main.py`):

```python
class ReWOOAgentRequest(BaseModel):
    # Structured metadata (always required)
    metadata: Dict[str, Any] = Field(
        ..., 
        description="Structured data: loan_program, classification, borrower_info, extracted_entities"
    )
    
    # Natural language instructions (optional)
    instructions: Optional[str] = Field(
        None,
        description="Natural language query like 'Evaluate loan conditions' or 'Check if documents are sufficient'"
    )
    
    # S3 paths (can be multiple documents)
    s3_pdf_paths: List[str] = Field(
        ...,
        description="List of S3 paths to documents"
    )
    
    # Optional output destination
    output_destination: Optional[str] = None
```

**Example Inputs**:

*Simple (current scope)*:

```json
{
  "metadata": {
    "loan_program": "Flex Supreme",
    "classification": "1120 Corporate Tax Return",
    "borrower_info": {...},
    "extracted_entities": {...}
  },
  "instructions": "Evaluate all loan conditions for this tax return",
  "s3_pdf_paths": ["rm-conditions/doc1.pdf"]
}
```

*Expanded (future scope)*:

```json
{
  "metadata": {
    "loan_program": "Flex Supreme",
    "classification": "Bank Statements",
    "borrower_info": {...}
  },
  "instructions": "Check if these bank statements are sufficient for income verification. If not, tell me what's missing.",
  "s3_pdf_paths": ["rm-conditions/statement1.pdf", "rm-conditions/statement2.pdf"]
}
```

### 2. ReWOO Module Implementation

**New file: `agent/rewoo_agent.py`**

Three distinct modules:

#### Planner Module

- Accepts hybrid input
- Uses LLM to create execution plan
- Returns structured plan with tool calls
```python
async def planner_node(state: ReWOOState) -> Dict[str, Any]:
    """
    PLANNER: Analyze input and create execution plan.
    
    Guided constraints:
 - Must include: PreConditions API → Conditions AI API
 - Can add: S3 retrieval, database queries, additional checks
    """
    
    # Build prompt for planner
    prompt = f"""
    You are a loan conditions evaluation agent. Analyze this request and create an execution plan.
    
    REQUIRED STEPS:
 1. Call PreConditions API to predict deficient conditions
 2. Call Conditions AI API to evaluate documents
    
    OPTIONAL STEPS (use if needed):
 - retrieve_s3_document: Fetch additional documents
 - query_database: Check historical evaluations
    
    Request:
    Metadata: {state['metadata']}
    Instructions: {state['instructions'] or 'Evaluate all loan conditions'}
    Documents: {state['s3_pdf_paths']}
    
    Create a step-by-step plan with tool calls.
    """
    
    # Call LLM to generate plan
    plan = await llm.ainvoke(prompt)
    
    # Parse plan into structured format
    parsed_plan = parse_plan(plan)
    
    return {
        "plan": parsed_plan,
        "stage": "planning_complete"
    }
```


#### Worker Module

- Executes plan WITHOUT LLM reasoning
- Calls tools in sequence/parallel
- No expensive token consumption
```python
async def worker_node(state: ReWOOState) -> Dict[str, Any]:
    """
    WORKER: Execute plan by calling tools.
    
    No LLM reasoning here - just execution.
    This is where ReWOO saves 80% of tokens compared to ReAct.
    """
    
    plan = state['plan']
    evidence = {}
    
    for step in plan['steps']:
        tool_name = step['tool']
        tool_input = step['input']
        
        # Execute tool (no LLM calls here!)
        if tool_name == "call_preconditions_api":
            result = await tools.call_preconditions(tool_input)
        elif tool_name == "call_conditions_ai_api":
            result = await tools.call_conditions_ai(tool_input)
        elif tool_name == "retrieve_s3_document":
            result = await tools.retrieve_s3(tool_input)
        elif tool_name == "query_database":
            result = await tools.query_db(tool_input)
        
        # Store evidence
        evidence[step['id']] = result
        
        # Stream progress
        yield {
            "stage": "worker_progress",
            "step": step['id'],
            "tool": tool_name,
            "status": "completed"
        }
    
    return {
        "evidence": evidence,
        "stage": "worker_complete"
    }
```


#### Solver Module

- Synthesizes all evidence
- Uses LLM to answer original query
- Produces final response
```python
async def solver_node(state: ReWOOState) -> Dict[str, Any]:
    """
    SOLVER: Synthesize evidence and produce final answer.
    """
    
    prompt = f"""
    Based on the execution plan and gathered evidence, answer the user's request.
    
    Original Request: {state['instructions']}
    
    Plan: {state['plan']}
    
    Evidence Gathered:
    {format_evidence(state['evidence'])}
    
    Provide a comprehensive answer with:
 1. Summary of findings
 2. Fulfilled vs not fulfilled conditions
 3. Any missing information
 4. Recommendations
    """
    
    # Call LLM for synthesis
    answer = await llm.ainvoke(prompt)
    
    # Format for frontend
    formatted_results = format_solver_output(answer, state['evidence'])
    
    return {
        "final_results": formatted_results,
        "stage": "solver_complete"
    }
```


### 3. Tool Definitions

**New file: `agent/tools.py`**

Wrap existing services as tools:

```python
class ConditionsAgentTools:
    """Tools available to the ReWOO agent."""
    
    @tool
    async def call_preconditions_api(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict deficient conditions based on loan metadata.
        
        Args:
            metadata: Borrower info, loan program, classification, extracted entities
        
        Returns:
            Predicted conditions with compartments and priorities
        """
        return await preconditions_client.predict_conditions(metadata)
    
    @tool
    async def call_conditions_ai_api(
        self, 
        conditions: List[Dict], 
        documents: List[str]
    ) -> Dict[str, Any]:
        """
        Evaluate conditions against uploaded documents.
        
        Args:
            conditions: List of conditions to evaluate
            documents: S3 paths to documents
        
        Returns:
            Evaluation results with fulfilled/not fulfilled status
        """
        # Transform and call Conditions AI
        transformed_input = transform_for_conditions_ai(conditions, documents)
        return await conditions_ai_client.evaluate(transformed_input)
    
    @tool
    async def retrieve_s3_document(self, s3_path: str) -> Dict[str, Any]:
        """
        Retrieve document metadata and preview from S3.
        
        Args:
            s3_path: S3 URI to document
        
        Returns:
            Document metadata and preview
        """
        # Fetch from S3
        bucket, key = parse_s3_path(s3_path)
        result = s3_client.get_object(Bucket=bucket, Key=key)
        
        return {
            "path": s3_path,
            "size": result['ContentLength'],
            "last_modified": result['LastModified'],
            "preview": extract_preview(result['Body'])
        }
    
    @tool
    async def query_database(self, query: str) -> List[Dict[str, Any]]:
        """
        Query historical loan evaluations.
        
        Args:
            query: Query type (e.g., 'similar_loans', 'condition_history')
        
        Returns:
            Historical evaluation data
        """
        return await repository.query_historical_evaluations(query)
```

### 4. Updated State Schema

**File: `agent/rewoo_state.py`**

```python
class ReWOOState(TypedDict, total=False):
    # Input
    metadata: Dict[str, Any]  # Structured loan data
    instructions: Optional[str]  # Natural language query
    s3_pdf_paths: List[str]  # Documents to evaluate
    output_destination: Optional[str]
    
    # ReWOO Stages
    plan: Dict[str, Any]  # Planner output
    evidence: Dict[str, Any]  # Worker output
    final_results: Dict[str, Any]  # Solver output
    
    # Streaming
    stage: str  # 'planning', 'working', 'solving', 'complete'
    current_step: Optional[str]
    
    # Metadata
    execution_metadata: ExecutionMetadata
```

### 5. Streaming Implementation

**Updated: `agent/rewoo_graph.py`**

```python
def create_rewoo_agent_graph():
    """Create ReWOO agent graph with streaming."""
    
    workflow = StateGraph(ReWOOState)
    
    # Add ReWOO nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("worker", worker_node)
    workflow.add_node("solver", solver_node)
    workflow.add_node("store_results", store_results_node)
    
    # ReWOO flow: Plan → Work → Solve → Store
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "worker")
    workflow.add_edge("worker", "solver")
    workflow.add_edge("solver", "store_results")
    workflow.add_edge("store_results", END)
    
    return workflow.compile()


async def run_rewoo_agent_streaming(
    metadata: Dict[str, Any],
    s3_pdf_paths: List[str],
    instructions: Optional[str] = None,
    output_destination: Optional[str] = None
) -> AsyncIterator[Dict[str, Any]]:
    """
    Run ReWOO agent with streaming output.
    
    Yields events for:
 - Plan creation
 - Worker progress (each tool call)
 - Solver synthesis
 - Final results
    """
    
    initial_state = {
        "metadata": metadata,
        "instructions": instructions,
        "s3_pdf_paths": s3_pdf_paths,
        "output_destination": output_destination,
        "stage": "initializing"
    }
    
    app = create_rewoo_agent_graph()
    
    async for event in app.astream(initial_state):
        stage = event.get('stage')
        
        if stage == 'planning_complete':
            yield {
                "stage": "plan",
                "plan": event['plan'],
                "timestamp": datetime.utcnow().isoformat()
            }
        
        elif stage == 'worker_progress':
            yield {
                "stage": "worker",
                "step": event['step'],
                "tool": event['tool'],
                "status": event['status'],
                "timestamp": datetime.utcnow().isoformat()
            }
        
        elif stage == 'solver_complete':
            yield {
                "stage": "solver",
                "results": event['final_results'],
                "timestamp": datetime.utcnow().isoformat()
            }
```

### 6. API Endpoint Changes

**Updated: `api/main.py`**

```python
@app.post("/api/v1/evaluate-conditions")
async def evaluate_conditions(request: ReWOOAgentRequest):
    """
    ReWOO Agent endpoint with streaming.
    
    Streams:
 - Plan (what the agent will do)
 - Worker progress (tool execution)
 - Solver synthesis (final answer)
    """
    
    async def event_generator():
        async for event in run_rewoo_agent_streaming(
            metadata=request.metadata,
            s3_pdf_paths=request.s3_pdf_paths,
            instructions=request.instructions,
            output_destination=request.output_destination
        ):
            yield f"data: {json.dumps(event, default=str)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
```

### 7. LLM Configuration

**New file: `config/llm.py`**

```python
from langchain_openai import ChatOpenAI
from config.settings import settings

# Planner LLM (needs reasoning)
planner_llm = ChatOpenAI(
    model="gpt-4-turbo-preview",
    temperature=0.1,  # Low temp for consistent planning
    streaming=True
)

# Solver LLM (needs synthesis)
solver_llm = ChatOpenAI(
    model="gpt-4-turbo-preview",
    temperature=0.3,  # Slightly higher for natural responses
    streaming=True
)
```

## Migration Strategy

### Phase 1: Maintain Backward Compatibility

1. Keep existing orchestrator (`agent/graph.py`)
2. Add new ReWOO agent alongside (`agent/rewoo_agent.py`)
3. Provide both endpoints:

            - `/api/v1/evaluate-loan-conditions` (old orchestrator)
            - `/api/v1/evaluate-conditions` (new ReWOO agent)

### Phase 2: Gradual Rollout

1. Test ReWOO with current scope (structured input only)
2. Add natural language support
3. Expand to new use cases (document sufficiency, missing info)
4. Deprecate old orchestrator

## Expected Benefits

### Token Efficiency (ReWOO vs ReAct)

- **ReAct**: ~10,000 tokens per evaluation (repeated reasoning)
- **ReWOO**: ~2,000 tokens per evaluation (plan once, execute)
- **Savings**: ~80% reduction in LLM costs

### Adaptability

- Current: Fixed workflow only
- ReWOO: Handles "What conditions apply?", "Are docs sufficient?", "What's missing?"

### Robustness

- Tool failures don't break the agent
- Can continue with partial evidence
- Solver provides best-effort answer

## Testing Strategy

1. **Unit Tests**: Test each ReWOO module independently
2. **Integration Tests**: Test full ReWOO flow with mocked tools
3. **Comparison Tests**: Same input through both orchestrator and ReWOO
4. **Token Usage**: Verify 80% reduction vs current approach
5. **Expanded Use Cases**: Test with natural language queries

## Files to Create/Modify

### New Files

- `agent/rewoo_agent.py` - ReWOO modules (Planner, Worker, Solver)
- `agent/rewoo_state.py` - ReWOO state schema
- `agent/rewoo_graph.py` - ReWOO graph definition
- `agent/tools.py` - Tool definitions
- `config/llm.py` - LLM configuration
- `tests/test_rewoo_agent.py` - ReWOO tests

### Modified Files

- `api/main.py` - Add ReWOO endpoint
- `config/settings.py` - Add LLM settings (OpenAI API key, model names)
- `requirements.txt` - Add `langchain`, `langchain-openai`

### Keep Unchanged (Backward Compatibility)

- `agent/graph.py` - Original orchestrator
- `agent/nodes.py` - Original nodes
- `services/preconditions.py` - PreConditions client
- `services/conditions_ai.py` - Conditions AI client
