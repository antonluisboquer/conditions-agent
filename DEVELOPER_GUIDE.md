# Conditions Agent - Developer Guide

**Last Updated**: November 14, 2025

This guide covers workflows, data transformations, troubleshooting, bug fixes, and edge case handling for developers working with the Conditions Agent.

---

## Table of Contents

1. [Agent Workflows](#agent-workflows)
2. [Data Transformations](#data-transformations)
3. [Recent Bug Fixes](#recent-bug-fixes)
4. [Edge Case Handling](#edge-case-handling)
5. [Airflow DAG Troubleshooting](#airflow-dag-troubleshooting)
6. [Performance & Optimization](#performance--optimization)
7. [Team Onboarding & AWS Setup](#team-onboarding--aws-setup)

---

## Agent Workflows

The ReWOO agent supports 4 distinct workflows based on input:

### Workflow 1: Deficiencies Only (Scenario 1)

**Use Case**: Predict what conditions might be deficient based on document metadata

**When to Use**:
- ✅ User wants to know what's missing
- ✅ No documents uploaded yet
- ✅ Early loan stage (application review)
- ✅ Quick turnaround needed

**Flow**:
```
User Input (borrower info, loan program, document metadata)
         ↓
┌────────────────────┐
│  PreConditions API │ (LangGraph Cloud)
└────────┬───────────┘
         │ Returns: final_results.top_n (scored deficiencies)
         ↓
┌────────────────────┐
│  Synthesize &      │
│  Return to User    │
└────────────────────┘
```

**Input Example**:
```json
{
  "metadata": {
    "documents": [
      {
        "classification": "Bank Statement",
        "extracted_entities": {"bank": {"name": "CITI BANK"}}
      }
    ],
    "loan_program": "Flex Supreme",
    "borrower_info": {"borrower_type": "W2"}
  },
  "instructions": "What conditions are deficient?",
  "s3_pdf_paths": []
}
```

**Output Format**:
```json
{
  "deficiencies": [
    {
      "condition_id": "Closing: Final 1003-URLA signed",
      "priority_score": 0.935,
      "detection_confidence": 0.89,
      "actionable_instruction": "Obtain URLA 1003 signed...",
      "severity": "high"
    }
  ],
  "summary": {
    "total_deficiencies": 8,
    "high_priority": 8
  }
}
```

**Agent Implementation**:
- **Planner**: Only plans `call_preconditions_api`
- **Worker**: Executes PreConditions call
- **Solver**: Synthesizes `final_results.top_n` into user-friendly format

---

### Workflow 2: Validation Only (Scenario 2)

**Use Case**: Validate uploaded documents against known conditions (skip prediction)

**When to Use**:
- ✅ Conditions already known (not predicted)
- ✅ Manual condition entry by RM
- ✅ Just need document validation
- ✅ Conditions come from another system

**Flow**:
```
User Input (known conditions + S3 PDFs)
         ↓
┌────────────────────┐
│  Transform Known   │
│  Conditions to     │
│  Conditions AI     │
└────────┬───────────┘
         ↓
┌────────────────────┐
│  Conditions AI     │ (Airflow DAG)
└────────┬───────────┘
         │ Validates docs
         ↓
┌────────────────────┐
│  Fetch & Return    │
│  Results           │
└────────────────────┘
```

**Input Example**:
```json
{
  "metadata": {
    "conditions": [
      {
        "condition_id": 1,
        "condition_name": "Bank Statements - 2 Months",
        "description": "Provide 2 consecutive months...",
        "category": "Assets"
      }
    ]
  },
  "instructions": "Validate these specific conditions",
  "s3_pdf_paths": [
    "s3://rm-conditions/Bank_Statement_Oct_2024.pdf"
  ]
}
```

**Agent Implementation**:
- **Planner**: Plans `call_conditions_ai_api` only
- **Worker**: Transforms metadata → Calls Conditions AI
- **Solver**: Returns validation results

**Key Fix** (November 2025): Added `transform_metadata_to_conditions_ai()` to handle direct metadata input.

---

### Workflow 3: S3 Access Test (Scenario 3)

**Use Case**: Verify S3 connectivity and document access

**When to Use**:
- ✅ Testing S3 credentials
- ✅ Verifying document availability
- ✅ Debugging S3 permission issues

**Flow**:
```
User Input (S3 paths only)
         ↓
┌────────────────────┐
│  Fetch S3 Files    │
│  & Return Metadata │
└────────────────────┘
```

---

### Workflow 4: Full Evaluation (Scenario 4)

**Use Case**: Complete workflow - predict deficiencies → validate documents

**When to Use**:
- ✅ Documents uploaded to S3
- ✅ Need both prediction and validation
- ✅ Ready for underwriting/approval
- ✅ Want automated fulfillment detection

**Flow**:
```
User Input (borrower info + loan program + S3 PDFs)
         ↓
┌────────────────────┐
│  PreConditions API │
└────────┬───────────┘
         │ Returns: final_results.top_n
         ↓
┌────────────────────┐
│  Transform to      │
│  Conditions AI     │
│  Input Format      │
└────────┬───────────┘
         ↓
┌────────────────────┐
│  Conditions AI     │ (Airflow DAG)
└────────┬───────────┘
         │ Validates documents
         ↓
┌────────────────────┐
│  Fetch S3 Results  │
│  & Synthesize      │
└────────────────────┘
```

**Output Format**:
```json
{
  "predicted_deficiencies": [...],
  "document_validation": [
    {
      "condition_id": "...",
      "validation_status": "fulfilled",
      "confidence": 0.92,
      "evidence": "Document X shows...",
      "requires_review": false
    }
  ],
  "summary": {
    "predicted_deficiencies": 8,
    "fulfilled": 2,
    "not_fulfilled": 6,
    "auto_approved": 2,
    "needs_rm_review": 6
  }
}
```

**Agent Implementation**:
- **Planner**: Plans `call_preconditions_api` → `call_conditions_ai_api`
- **Worker**: 
  1. Executes PreConditions
  2. Transforms `final_results.top_n` to Conditions AI format
  3. Executes Conditions AI
  4. Fetches S3 results
- **Solver**: Synthesizes predictions + validations

---

## Data Transformations

### PreConditions Output → Conditions AI Input

The transformer prioritizes `final_results.top_n` (scored deficiencies) over `deficient_conditions` (raw deficiencies).

#### Field Mapping Table

| Conditions AI Field | PreConditions Source | Example |
|---------------------|---------------------|---------|
| `condition.id` | Sequential (1, 2, 3...) | `1` |
| `condition.name` | `top_n[i].condition_id` | `"Closing: Final 1003-URLA signed"` |
| `condition.data.Title` | `top_n[i].condition_id` | `"Closing: Final 1003-URLA signed"` |
| `condition.data.Category` | `"; ".join(compartments)` | `"Loan & Property; Agreements"` |
| `condition.data.Description` | `top_n[i].actionable_instruction` | `"Obtain URLA 1003 signed..."` |

#### Key Details

**Category Field**:
- Combines ALL top-level `compartments` from PreConditions output
- Same combined string used for ALL conditions
- Format: `"Category1; Category2; Category3"`

**Example**:
```python
compartments = [
  "Loan & Property Information",
  "Acknowledgments & Agreements",
  "Borrower Information"
]
combined_category = "; ".join(compartments)
# Result: "Loan & Property Information; Acknowledgments & Agreements; Borrower Information"
```

#### Implementation (`utils/transformers.py`)

```python
def transform_preconditions_to_conditions_ai(...):
    # Extract compartments
    compartments = cloud_output.get('compartments', [])
    combined_category = "; ".join(compartments)
    
    # Prefer final_results.top_n (scored)
    final_results = cloud_output.get('final_results', {})
    top_n = final_results.get('top_n', [])
    
    if top_n:
        # Use scored and prioritized deficiencies
        for idx, cond in enumerate(top_n, 1):
            conditions.append({
                "condition": {
                    "id": idx,
                    "name": cond['condition_id'],
                    "data": {
                        "Title": cond['condition_id'],
                        "Category": combined_category,  # Same for all
                        "Description": cond['actionable_instruction']
                    }
                }
            })
    else:
        # Fallback to deficient_conditions
        ...
```

**Benefits of Using `final_results.top_n`**:
- ✅ Prioritized by `priority_score`
- ✅ Includes `detection_confidence`
- ✅ Rich metadata (severity, impact, urgency)
- ✅ Clear `actionable_instruction`
- ✅ Contains `original_deficiency` with full details

---

### Metadata Conditions → Conditions AI Input

For validation-only scenarios where conditions are provided directly:

```python
def transform_metadata_to_conditions_ai(metadata, s3_pdf_paths, ...):
    conditions = metadata.get('conditions', [])
    
    return {
        "conf": {
            "conditions": [
                {
                    "condition": {
                        "id": idx,
                        "name": cond.get('condition_name'),
                        "data": {
                            "Title": cond.get('condition_name'),
                            "Category": cond.get('category', 'General'),
                            "Description": cond.get('description')
                        }
                    }
                }
                for idx, cond in enumerate(conditions, 1)
            ],
            "s3_pdf_paths": [...],
            "output_destination": "..."
        }
    }
```

---

## Recent Bug Fixes

### Fix 1: Session Token Support (November 2025)

**Problem**: `test_s3_access.py` was failing with `InvalidAccessKeyId` despite having temporary credentials with session token.

**Root Cause**: Test script wasn't passing `aws_session_token` to boto3.

**Solution**:
- Updated `get_s3_client()` in `tests/test_s3_access.py` to handle session tokens
- Implemented same 4-tier authentication priority as main app
- Added display of authentication method in test output

**Files Modified**:
- `tests/test_s3_access.py`
- `config/settings.py` (added `aws_session_token` field)
- `services/conditions_ai.py` (updated S3 client init)
- `utils/aws_credentials.py` (added session token support)

---

### Fix 2: Validation Scenario Worker Error (November 2025)

**Problem**: 
```
worker error for validation scenario:
call_conditions_ai_api requires transformed_input or preconditions_output
```

**Root Cause**: Tool didn't accept raw metadata conditions for validation-only scenarios.

**Solution**:
1. Created `transform_metadata_to_conditions_ai()` in `utils/transformers.py`
2. Updated `call_conditions_ai_api` tool to accept 3 input types:
   - `transformed_input` (ready to use)
   - `preconditions_output` (transform from PreConditions)
   - `metadata` (transform from raw conditions) ← **NEW**
3. Updated `worker_node` to detect validation-only scenarios

**Files Modified**:
- `utils/transformers.py`
- `agent/tools.py`
- `agent/rewoo_agent.py`

---

### Fix 3: S3 Polling Timeout (November 2025)

**Problem**: `NoSuchKey` error after DAG completed successfully - file wasn't available immediately.

**Root Cause**: DAG completion doesn't guarantee S3 file is written immediately. There's a small delay.

**Solution**:
- Added polling to `fetch_s3_results()` in `services/conditions_ai.py`
- Polls for up to 180 seconds (3 minutes) with 5-second intervals
- Improved error messages showing wait time

**Before**:
```python
# Single attempt - fails immediately
response = self.s3_client.get_object(Bucket=bucket, Key=key)
```

**After**:
```python
# Retry with polling
max_wait_seconds = 180
poll_interval = 5

while elapsed < max_wait_seconds:
    try:
        response = self.s3_client.get_object(Bucket=bucket, Key=key)
        return results  # Success!
    except NoSuchKey:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
```

---

### Fix 4: Airflow DAG Tasks Skipped (November 2025)

**Problem**: DAG reported "success" but `analyze_conditions` and `compile_and_save_results` tasks were **skipped**, resulting in no S3 output file.

**Root Cause**: 
- Documents uploaded (Title Report, Flood Cert) didn't match predicted conditions (Bank Statement, Credit Report)
- Relevance check marked ALL conditions as "unrelated"
- `show_relevance()` returned empty list `[]`
- `.expand()` with empty list → tasks automatically skipped
- No output file written

**Solution**:
- Updated `tests/scenario_4_full_evaluation.json` with relevant documents
- Changed from unrelated docs to matching docs:
  - Bank Statement - August 2025.pdf
  - URLA 1003 Application.pdf
  - Credit Report - September 2025.pdf

**Key Learning**: Airflow's `.expand()` with empty list causes task skipping (not failure). DAG still reports "success".

**Files Modified**:
- `tests/scenario_4_full_evaluation.json`

---

## Edge Case Handling

### No Relevant Documents Scenario (November 2025)

**Problem**: In production, there will be cases where **no documents match conditions**. Agent should handle this gracefully.

**Solution Implemented**:

#### 1. S3 Fetch Graceful Failure (`services/conditions_ai.py`)

```python
try:
    s3_results = await self.fetch_s3_results(output_destination)
    return s3_results
except FileNotFoundError as e:
    # DAG completed but no output - no relevant documents
    logger.warning(f"DAG completed but no S3 output: {e}")
    
    return {
        "processing_status": "completed_no_relevant_documents",
        "s3_output_written": False,
        "processed_conditions": [],
        "message": "No documents were relevant to the specified conditions"
    }
```

#### 2. Classify Node Handling (`agent/nodes.py`)

```python
processing_status = conditions_ai_output.get('processing_status')
if processing_status == 'completed_no_relevant_documents':
    logger.info("No relevant documents found - skipping classification")
    return {
        "fulfilled_conditions": [],
        "not_fulfilled_conditions": [],
        "requires_human_review": False,
        "auto_approved_count": 0
    }
```

#### 3. Store Node Special Result (`agent/nodes.py`)

```python
if is_no_relevant_docs:
    final_results = {
        "status": "completed_no_relevant_documents",
        "summary": {
            "no_relevant_documents": True,
            "message": "No uploaded documents were relevant to conditions"
        },
        "conditions": [],
        "note": "DAG completed but found no relevant documents"
    }
```

**Expected Behavior**:
1. ✅ PreConditions predicts deficiencies
2. ✅ Conditions AI DAG runs with unrelated documents
3. ✅ Relevance check marks all as "unrelated"
4. ✅ DAG completes but skips analysis tasks
5. ✅ No S3 output file written
6. ✅ Agent detects missing file gracefully
7. ✅ Returns `status: "completed_no_relevant_documents"`

**Files Modified**:
- `services/conditions_ai.py`
- `agent/nodes.py`

---

## Airflow DAG Troubleshooting

### Understanding Task Skipping

**When Airflow skips tasks**:
- Task's trigger rule not satisfied (default: `all_success`)
- Upstream task failed or was skipped
- Dynamic task mapping (`.expand()`) with empty list
- Branch operator chose different path

**Key Insight**: DAG can report "success" even with skipped tasks!

### Debugging Skipped Tasks

#### Step 1: Check Task Status

1. Go to Airflow UI
2. Navigate to DAG: `check_condition_v3`
3. Click **Graph** tab
4. Identify which tasks are skipped (gray color)

#### Step 2: Find First Skipped Task

- Click on the **first** skipped task
- Check logs for skip reason
- Look for trigger rule violations

#### Step 3: Check XCom Values

1. Click **XCom** tab (top right of DAG run)
2. Find task that parses/validates input
3. Check `return_value` - is it empty or None?

#### Step 4: Verify Input Format

Compare what we're sending vs. what DAG expects:

**Our Format**:
```json
{
  "conf": {
    "conditions": [
      {
        "condition": {
          "id": 1,
          "name": "...",
          "data": {...}
        }
      }
    ],
    "s3_pdf_paths": [...],
    "output_destination": "..."
  }
}
```

**Check DAG Code**:
- Field names match?
- Structure correct?
- Data types valid?

#### Step 5: Check Relevance Filtering

If `analyze_conditions` is skipped:
- Check `show_relevance` task output
- Is it returning empty list `[]`?
- Are documents actually relevant to conditions?

### Common Causes

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| All tasks skipped | Invalid/empty input | Check XCom from input parsing task |
| `analyze_conditions` skipped | Empty relevance list | Use relevant documents |
| `compile_results` skipped | Upstream task failed | Check analyze task logs |
| No S3 output | Task that writes skipped | Trace back to first skip |

---

## Performance & Optimization

### S3 Polling Configuration

**Current Settings** (`services/conditions_ai.py`):
```python
# DAG completion polling
max_wait_seconds = 600  # 10 minutes
poll_interval = 10      # Check every 10 seconds

# S3 file polling
max_wait_seconds = 180  # 3 minutes
poll_interval = 5       # Check every 5 seconds
```

**Tuning Guidelines**:
- **Short DAG runs** (< 2 min): Current settings OK
- **Long DAG runs** (> 5 min): Increase DAG polling timeout
- **Slow S3 writes**: Increase S3 polling timeout
- **Fast feedback needed**: Decrease poll intervals (but watch API rate limits)

### Credential Refresh

**IAM Role Assumption**:
- Session duration: 1 hour
- Refresh trigger: 5 minutes before expiration
- Automatic refresh: Yes

**To extend session duration**:
```python
# In utils/aws_credentials.py
DurationSeconds=7200  # 2 hours (max depends on role config)
```

### Logging Levels

**Production**: `LOG_LEVEL=INFO`
- Shows major workflow steps
- Error messages
- Performance metrics

**Debugging**: `LOG_LEVEL=DEBUG`
- Full DAG input payloads
- S3 polling attempts
- Authentication details
- Detailed transformations

---

## Testing Best Practices

### 1. Use Relevant Test Data

**Bad** (Scenario 4):
```json
"s3_pdf_paths": [
  "s3://rm-conditions/TitleReport.pdf",    // Unrelated
  "s3://rm-conditions/FloodCert.pdf"       // Unrelated
]
```

**Good** (Scenario 4):
```json
"s3_pdf_paths": [
  "s3://rm-conditions/BankStatement.pdf",  // Matches predicted condition
  "s3://rm-conditions/URLA1003.pdf",       // Matches predicted condition
  "s3://rm-conditions/CreditReport.pdf"    // Matches predicted condition
]
```

### 2. Test Edge Cases

- ✅ No documents provided (deficiencies only)
- ✅ Known conditions (validation only)
- ✅ No relevant documents (graceful handling)
- ✅ S3 access errors
- ✅ API timeouts

### 3. Verify Each Workflow

Run all 4 scenarios:
```bash
python tests/test_rewoo_scenarios.py
```

1. Deficiencies Only
2. Validation Only
3. S3 Access
4. Full Evaluation

### 4. Check Logs

Always review logs for:
- Authentication method used
- Transformation mappings
- DAG run IDs
- S3 polling attempts
- Error messages

---

## Architecture Patterns

### ReWOO Agent Pattern

```
┌─────────────────────────────────────────┐
│            ReWOO Agent                   │
│                                          │
│  ┌──────────┐   ┌──────────┐  ┌──────┐ │
│  │ Planner  │ → │  Worker  │ → │Solver│ │
│  └──────────┘   └──────────┘  └──────┘ │
│       │              │             │     │
│       │              │             │     │
│    Create         Execute      Synthesize│
│     Plan          Tools        Results   │
└─────────────────────────────────────────┘
```

**Planner**: Analyzes instructions → Creates execution plan
**Worker**: Executes tools → Builds evidence
**Solver**: Synthesizes evidence → Generates final answer

### Streaming Architecture

```
Agent Graph
     │
     ├─→ Node 1 completes → Stream update
     │
     ├─→ Node 2 completes → Stream update
     │
     ├─→ Node 3 completes → Stream update
     │
     └─→ Final node → Stream complete result
```

Each node completion triggers a streaming event to the frontend.

---

## Summary

**Key Takeaways**:

1. **4 Workflows**: Deficiencies only, Validation only, S3 access, Full evaluation
2. **Data Transformation**: `final_results.top_n` → Conditions AI format
3. **Category Mapping**: Combined string of ALL compartments
4. **Edge Cases**: Graceful handling of no relevant documents
5. **Airflow Debugging**: Check task status, XComs, and relevance filtering
6. **Authentication**: 4-tier priority (Role → Temp → Static → Default)
7. **S3 Polling**: Accommodates async writes (180s timeout)

**For Setup**: See `SETUP_GUIDE.md`
**For Testing**: See `tests/test_rewoo_scenarios.py`
**For API**: See `api/main.py`

---

## Team Onboarding & AWS Setup

### AWS SSO Configuration for Team Members

The Conditions Agent uses **AWS IAM Identity Center (SSO)** for authentication. Team members with `AWSReservedSSO_PowerUserAccess_d933572f88f33718` permission set can assume the `ConditionsAgentRole` for S3 access.

---

### Prerequisites

Each team member needs:
- ✅ AWS CLI version 2 installed
- ✅ Access to Cybersoft AWS organization through SSO
- ✅ Python 3.8+ installed
- ✅ Git installed

---

### Quick Setup (10 minutes)

#### Step 1: Install AWS CLI v2

**Windows:**
```powershell
# Download and install
https://awscli.amazonaws.com/AWSCLIV2.msi

# Verify
aws --version  # Should show: aws-cli/2.x.x
```

**macOS:**
```bash
curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
sudo installer -pkg AWSCLIV2.pkg -target /
```

**Linux:**
```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

---

#### Step 2: Configure SSO

```bash
aws configure sso
```

**Enter these values:**

| Prompt | Value |
|--------|-------|
| SSO session name | `conditions-agent` |
| SSO start URL | `https://cybersoft.awsapps.com/start` |
| SSO region | `ap-southeast-1` |
| SSO registration scopes | `sso:account:access` (press Enter for default) |

**Browser will open for authentication.**

**When prompted, select:**
- Account: `872194582181`
- Role: `PowerUserAccess`
- Default region: `us-east-1`
- Output format: `json`
- Profile name: `PowerUserAccess-872194582181`

---

#### Step 3: Clone & Setup Project

```bash
# Clone repository
git clone <repo-url>
cd conditions-agent

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

#### Step 4: Configure .env

```bash
# AWS Configuration (Same for everyone)
AWS_ROLE_ARN=arn:aws:iam::872194582181:role/ConditionsAgentRole
AWS_PROFILE=PowerUserAccess-872194582181
AWS_REGION=us-east-1
S3_OUTPUT_BUCKET=rm-conditions

# Personal Settings
LANGSMITH_API_KEY=your_personal_langsmith_key
LANGSMITH_PROJECT=conditions-agent
LANGSMITH_TRACING_V2=true

# Shared Configuration
AIRFLOW_BASE_URL=<shared_airflow_url>
AIRFLOW_USERNAME=<your_username>
AIRFLOW_PASSWORD=<your_password>
PRECONDITIONS_DEPLOYMENT_URL=<shared_deployment_url>
PRECONDITIONS_API_KEY=<shared_api_key>
```

---

#### Step 5: Login & Test

```bash
# Login to SSO (do this daily or when credentials expire)
aws sso login --profile PowerUserAccess-872194582181

# Test S3 access
python tests/test_s3_access.py

# Should show: ✅ Successfully assumed role and connected to S3!
```

---

### How Authentication Works

```
1. SSO Login (PowerUserAccess role)
   ↓
2. Code reads AWS_PROFILE from .env
   ↓
3. boto3 uses SSO cached credentials
   ↓
4. Code automatically assumes ConditionsAgentRole
   ↓
5. Uses that role's credentials for S3 access
   ↓
6. Auto-refreshes when expired
```

**Key Points**:
- ✅ Each person uses their own SSO credentials
- ✅ Everyone assumes the same `ConditionsAgentRole`
- ✅ Role has S3 permissions
- ✅ Credentials auto-refresh (no manual copying!)

---

### Daily Workflow

```bash
# Morning: Login to SSO
aws sso login --profile PowerUserAccess-872194582181

# Activate virtual environment
# Windows:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

# Start working
python api/main.py
# or
python tests/test_rewoo_scenarios.py
```

---

### Troubleshooting

#### "Unable to locate credentials"

**Solution:**
```bash
aws sso login --profile PowerUserAccess-872194582181
```

---

#### "Profile not found"

**Solution:**
```bash
aws configure sso  # Re-run configuration
```

---

#### "AWS CLI version 1" or "aws configure sso not found"

**Problem:** Old AWS CLI doesn't support SSO.

**Solution:**
```bash
# Uninstall v1
pip uninstall awscli

# Install v2 (download from https://aws.amazon.com/cli/)
# Restart terminal
aws --version  # Verify v2
```

---

#### "Access Denied" when assuming role

**Problem:** Missing permissions.

**Solution:**
- Verify you have PowerUserAccess through SSO
- Contact AWS admin if role assignment is missing
- Check you're in the correct AWS account (872194582181)

---

#### load_dotenv issues in tests

**Problem:** Test scripts can't find AWS credentials from .env.

**Solution:**
Add to top of test file:
```python
from dotenv import load_dotenv
load_dotenv()  # Load .env before importing settings
```

---

### Important Configuration Values

| Setting | Value |
|---------|-------|
| **SSO Start URL** | `https://cybersoft.awsapps.com/start` |
| **SSO Region** | `ap-southeast-1` |
| **AWS Account** | `872194582181` |
| **Role ARN** | `arn:aws:iam::872194582181:role/ConditionsAgentRole` |
| **S3 Bucket** | `rm-conditions` |
| **Default Region** | `us-east-1` |
| **Profile Name** | `PowerUserAccess-872194582181` |

---

### Common Commands

```bash
# SSO Login
aws sso login --profile PowerUserAccess-872194582181

# Check AWS Identity
aws sts get-caller-identity --profile PowerUserAccess-872194582181

# Test S3 Access
python tests/test_s3_access.py

# Run Agent
python api/main.py

# Run Test Scenarios
python tests/test_rewoo_scenarios.py

# SSO Logout
aws sso logout
```

---

### Security Best Practices

**Never commit:**
- ❌ `.env` file (contains secrets)
- ❌ `.aws/` directory (contains credentials)
- ❌ Any files with API keys or passwords

**Safe to share:**
- ✅ SSO start URL
- ✅ Role ARN
- ✅ Account ID
- ✅ S3 bucket name
- ✅ AWS region

**Personal/secret:**
- 🔐 LangSmith API key
- 🔐 Airflow credentials
- 🔐 SSO session credentials

---

### Additional Resources

- **Full Setup Guide:** `SETUP_GUIDE.md`
- **API Documentation:** `http://localhost:8000/docs` (when running)
- **Architecture:** `ARCHITECTURE.md`
- **AWS CLI v2 Docs:** https://docs.aws.amazon.com/cli/latest/userguide/

---

**Happy coding!** 🚀

