# ReWOO Agent Test Scenarios

This directory contains test inputs for different ReWOO agent use cases. Each scenario tests whether the agent correctly chooses the appropriate tools based on user instructions.

## 📋 Scenarios

### Scenario 1: Deficiency Prediction Only
**File:** `scenario_1_deficiencies_only.json`

**User Instruction:** "Determine what conditions are deficient for this borrower and loan."

**Expected Tools:** 
- ✅ `call_preconditions_api` ONLY

**Input:**
- Full loan metadata (documents, borrower info, loan program)
- NO S3 paths (not checking documents yet)

**Use Case:** User wants to know what conditions they'll need to collect before running full evaluation.

---

### Scenario 2: Document Validation Only
**File:** `scenario_2_validation_only.json`

**User Instruction:** "Check if the uploaded documents satisfy these specific conditions."

**Expected Tools:**
- ✅ `call_conditions_ai_api` ONLY

**Input:**
- Pre-defined conditions list (already know what to check)
- S3 paths to documents

**Use Case:** User already knows what conditions are required, just needs to verify documents satisfy them.

---

### Scenario 3: S3 Access Check
**File:** `scenario_3_s3_access.json`

**User Instruction:** "Verify that you can access these S3 documents."

**Expected Tools:**
- ✅ `retrieve_s3_document` ONLY

**Input:**
- NO metadata
- S3 paths only

**Use Case:** Infrastructure test - verify S3 credentials and document accessibility.

---

### Scenario 4: Full Evaluation
**File:** `scenario_4_full_evaluation.json`

**User Instruction:** "Perform a complete loan conditions evaluation."

**Expected Tools:**
- ✅ `call_preconditions_api` (predict deficiencies)
- ✅ `call_conditions_ai_api` (validate documents)

**Input:**
- Full loan metadata
- S3 paths to documents

**Use Case:** Complete end-to-end loan evaluation workflow.

---

## 🧪 Running Tests

### Option 1: Interactive Test Script
```bash
python tests/test_rewoo_scenarios.py
```

Select individual scenarios or run all:
- `1` - Scenario 1 (Deficiencies only)
- `2` - Scenario 2 (Validation only)
- `3` - Scenario 3 (S3 access)
- `4` - Scenario 4 (Full evaluation)
- `all` - Run all scenarios

### Option 2: LangGraph Studio
1. Start `langgraph dev`
2. Open LangGraph Studio
3. Load any scenario JSON file
4. Run and observe which tools the planner chooses

### Option 3: Direct API Call
```bash
# Scenario 1
curl -X POST http://localhost:2024/threads \
  -H "Content-Type: application/json" \
  -d @tests/scenario_1_deficiencies_only.json
```

---

## ✅ Success Criteria

### Scenario 1 Success
- Planner creates 1 step
- Step uses `call_preconditions_api`
- Returns list of predicted deficient conditions
- Does NOT call Conditions AI

### Scenario 2 Success
- Planner creates 1 step
- Step uses `call_conditions_ai_api`
- Returns fulfillment status for each condition
- Does NOT call PreConditions

### Scenario 3 Success
- Planner creates 1-2 steps (one per document)
- Steps use `retrieve_s3_document`
- Returns document metadata and access status
- Does NOT call other APIs

### Scenario 4 Success
- Planner creates 2 steps
- Step 1: `call_preconditions_api`
- Step 2: `call_conditions_ai_api` (uses output from Step 1)
- Returns complete evaluation with fulfilled/not fulfilled counts

---

## 🎯 Expected Tool Selection Logic

The planner should follow these rules:

| User Wants | Expected Tools |
|------------|---------------|
| "What's deficient?" | PreConditions only |
| "Do docs satisfy conditions?" | Conditions AI only |
| "Can you access S3?" | retrieve_s3_document only |
| "Full evaluation" | PreConditions → Conditions AI |
| "Historical data" | query_database only |

---

## 🔧 Troubleshooting

### Agent always calls both PreConditions AND Conditions AI
**Problem:** Planner prompt is too rigid

**Solution:** Check `agent/rewoo_agent.py` planner prompt has clear decision rules

### Agent doesn't call any tools
**Problem:** LLM not configured or prompt format wrong

**Solution:** 
- Verify `OPENAI_API_KEY` in `.env`
- Check `config/llm.py` planner_llm is configured

### Fallback plan always used
**Problem:** Planner LLM failing to generate valid JSON

**Solution:**
- Check LLM response format in logs
- May need to adjust prompt formatting
- Verify model supports JSON output

---

## 📊 Example Output

### Scenario 1 - Deficiency Prediction
```json
{
  "plan": {
    "summary": "Predict deficient conditions based on loan metadata",
    "steps": [
      {
        "id": "step_1",
        "tool": "call_preconditions_api",
        "description": "Call PreConditions to predict deficiencies",
        "input": {"metadata": {...}}
      }
    ]
  }
}
```

### Scenario 4 - Full Evaluation
```json
{
  "plan": {
    "summary": "Complete loan evaluation: predict deficiencies then validate documents",
    "steps": [
      {
        "id": "step_1",
        "tool": "call_preconditions_api",
        "description": "Predict deficient conditions",
        "input": {"metadata": {...}}
      },
      {
        "id": "step_2",
        "tool": "call_conditions_ai_api",
        "description": "Validate documents against predicted conditions",
        "input": {
          "preconditions_output": "{{step_1}}",
          "documents": [...]
        }
      }
    ]
  }
}
```

