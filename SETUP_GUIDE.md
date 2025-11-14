# Conditions Agent - Setup & Configuration Guide

**Last Updated**: November 14, 2025

This guide covers everything you need to configure and run the Conditions Agent, including AWS credentials, environment variables, and service integrations.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Environment Configuration](#environment-configuration)
3. [AWS Credential Setup (4 Options)](#aws-credential-setup)
4. [Service Integrations](#service-integrations)
5. [Testing Your Setup](#testing-your-setup)
6. [Troubleshooting](#troubleshooting)

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Create `.env` File

```bash
cp .env.example .env
# Edit .env with your credentials
```

### 3. Configure AWS Credentials

Choose ONE of the 4 authentication methods below.

### 4. Run the Agent

```bash
# Start API
python api/main.py

# Or run tests
python tests/test_rewoo_scenarios.py
```

---

## Environment Configuration

### Required Environment Variables

Create a `.env` file with:

```bash
# ============================================================================
# LangSmith Configuration (Required)
# ============================================================================
LANGSMITH_API_KEY=your_langsmith_api_key_here
LANGSMITH_PROJECT=conditions-agent
LANGSMITH_TRACING_V2=true

# ============================================================================
# LLM Configuration (Required)
# ============================================================================
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ANTHROPIC_MODEL=claude-sonnet-4-5-20250929
OPENAI_API_KEY=your_openai_api_key_here
PLANNER_MODEL=gpt-4o-mini
SOLVER_MODEL=gpt-4o-mini
PLANNER_TEMPERATURE=0.1
SOLVER_TEMPERATURE=0.3

# ============================================================================
# PreConditions API (LangGraph Cloud) - Required
# ============================================================================
PRECONDITIONS_DEPLOYMENT_URL=https://your-deployment.langsmith.com
PRECONDITIONS_API_KEY=your_langsmith_api_key
PRECONDITIONS_ASSISTANT_ID=your_assistant_id

# ============================================================================
# Conditions AI (Airflow) - Required
# ============================================================================
CONDITIONS_AI_API_URL=https://uat-airflow-llm.cybersoftbpo.ai
AIRFLOW_USERNAME=your_username
AIRFLOW_PASSWORD=your_password

# ============================================================================
# S3 Configuration - Choose ONE authentication method below
# ============================================================================
# See "AWS Credential Setup" section for details

# ============================================================================
# Database Configuration (Optional)
# ============================================================================
DATABASE_URL=postgresql://user:password@localhost:5432/conditions_agent
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20

# ============================================================================
# Agent Configuration (Optional)
# ============================================================================
CONFIDENCE_THRESHOLD=0.7
MAX_EXECUTION_TIMEOUT_SECONDS=30
COST_BUDGET_USD_PER_EXECUTION=5.0

# ============================================================================
# API Configuration (Optional)
# ============================================================================
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# ============================================================================
# Logging (Optional)
# ============================================================================
LOG_LEVEL=INFO
LOG_FORMAT=json
```

---

## AWS Credential Setup

The agent supports **4 authentication methods** with the following priority:

```
1. IAM Role Assumption (AWS_ROLE_ARN)
   ↓ (if not set)
2. Temporary Credentials with Session Token (AWS_SESSION_TOKEN)
   ↓ (if not set)
3. Static Credentials (AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY)
   ↓ (if not set)
4. Default Credential Chain (IAM instance profile, ~/.aws/credentials, etc.)
```

### Option 1: IAM Role Assumption ⭐ RECOMMENDED

**Use when**: Your coworker provides an IAM role ARN for S3 access

**Pros**: Most secure, automatic credential refresh, follows AWS best practices

**Setup**:

```bash
# In .env
AWS_ROLE_ARN=arn:aws:iam::123456789012:role/YourS3AccessRole
AWS_REGION=us-east-1
S3_OUTPUT_BUCKET=rm-conditions
```

**How it works**:
- Agent uses STS (Security Token Service) to assume the role
- Temporary credentials obtained with 1-hour duration
- Automatically refreshed 5 minutes before expiration
- All S3 operations tracked with role identity

**Requirements**:
- Your AWS user must have `sts:AssumeRole` permission
- The role must have a trust policy allowing your user
- The role must have S3 read permissions

**Trust Policy Example** (Ask your coworker to add this):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::YOUR-ACCOUNT-ID:user/YOUR-USERNAME"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

---

### Option 2: Temporary Credentials with Session Token

**Use when**: You have temporary credentials from MFA, SSO, or another source

**Pros**: Works with existing temporary credentials, backwards compatible

**Setup**:

```bash
# In .env
AWS_ACCESS_KEY_ID=ASIAXXXXXXXXXXXXXXXX
AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
AWS_SESSION_TOKEN=your_session_token_here
AWS_REGION=us-east-1
S3_OUTPUT_BUCKET=rm-conditions
```

**How it works**:
- Agent uses your provided temporary credentials directly
- Typically expire after 1 hour (depends on source)
- RefreshableS3Client attempts to refresh before expiration

**When to use**:
- ✅ You already have temporary credentials
- ✅ You use AWS CLI with MFA
- ✅ You use AWS SSO
- ✅ Migration period before role assumption setup

---

### Option 3: Static Credentials (Legacy)

**Use when**: Role assumption not available yet

**Pros**: Simple, works everywhere

**Cons**: Less secure, no automatic rotation, must manage keys manually

**Setup**:

```bash
# In .env
AWS_ACCESS_KEY_ID=AKIAXXXXXXXXXXXXXXXX
AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
AWS_REGION=us-east-1
S3_OUTPUT_BUCKET=rm-conditions
```

**Security Warning**: ⚠️ Not recommended for production. Migrate to Option 1 when possible.

---

### Option 4: Default Credential Chain

**Use when**: Running on AWS infrastructure (EC2, ECS, Lambda)

**Pros**: No configuration needed, uses infrastructure IAM roles

**Setup**:

```bash
# In .env - leave AWS credentials UNSET
AWS_REGION=us-east-1
S3_OUTPUT_BUCKET=rm-conditions
```

**How it works**:
- boto3 automatically checks multiple sources in order:
  1. IAM instance profile (EC2)
  2. Environment variables
  3. AWS CLI credentials (`~/.aws/credentials`)
  4. ECS container credentials
  5. EKS pod credentials

**When to use**:
- ✅ Running on EC2 with instance profile
- ✅ Running on ECS/Fargate with task role
- ✅ Local development with AWS CLI configured
- ✅ CI/CD pipelines with AWS credentials

---

## Service Integrations

### PreConditions API (LangGraph Cloud)

The PreConditions API predicts deficient loan conditions based on document metadata.

**Configuration**:
```bash
PRECONDITIONS_DEPLOYMENT_URL=https://your-deployment.langsmith.com
PRECONDITIONS_API_KEY=your_langsmith_api_key
PRECONDITIONS_ASSISTANT_ID=your_assistant_id
```

**Test Connection**:
```python
from services.preconditions import PreConditionsClient
import asyncio

async def test():
    client = PreConditionsClient()
    result = await client.predict_deficiencies({
        "borrower_info": {"borrower_type": "W2"},
        "loan_program": "Flex Supreme",
        "documents": []
    })
    print(result)

asyncio.run(test())
```

---

### Conditions AI (Airflow v3)

The Conditions AI DAG validates documents against predicted conditions.

**Configuration**:
```bash
CONDITIONS_AI_API_URL=https://uat-airflow-llm.cybersoftbpo.ai
AIRFLOW_USERNAME=your_username
AIRFLOW_PASSWORD=your_password
```

**Important Notes**:
- Currently uses `check_condition_v3` DAG
- Code comments may reference "v5" - this is historical
- Ensure the DAG is deployed and accessible
- DAG requires S3 write permissions for output

**Test Connection**:
```python
from services.conditions_ai import ConditionsAIClient
import asyncio

async def test():
    client = ConditionsAIClient()
    # Test with minimal input
    result = await client.evaluate(...)
    print(result)

asyncio.run(test())
```

---

## Testing Your Setup

### 1. Test S3 Access

```bash
python tests/test_s3_access.py
```

**Expected Output**:
```
✓ AWS Region: us-east-1
✓ Authentication: IAM Role Assumption (arn:aws:iam::...)
✓ S3 Connectivity: Success
✓ Test file uploaded successfully
✓ Test file downloaded successfully
```

### 2. Test ReWOO Scenarios

```bash
python tests/test_rewoo_scenarios.py
```

**Available Scenarios**:
1. **Deficiencies Only** - Predict conditions without validation
2. **Validation Only** - Validate documents against known conditions
3. **S3 Access** - Verify S3 document retrieval
4. **Full Evaluation** - Complete workflow (PreConditions → Conditions AI)

### 3. Start API Server

```bash
python api/main.py
```

**Test Streaming Endpoint**:
```bash
curl -N -X POST http://localhost:8000/api/v1/evaluate-loan-conditions \
  -H "Content-Type: application/json" \
  -d @tests/scenario_1_deficiencies_only.json
```

---

## Troubleshooting

### AWS Credential Issues

#### Error: "InvalidAccessKeyId"

**Cause**: Credentials are invalid or expired

**Solutions**:
1. Check if using temporary credentials - verify `AWS_SESSION_TOKEN` is set
2. Verify access key starts with `ASIA` (temporary) or `AKIA` (static)
3. Regenerate credentials if expired
4. Check AWS region is correct

#### Error: "User is not authorized to perform: sts:AssumeRole"

**Cause**: Your user can't assume the specified role

**Solutions**:
1. Ask your coworker to add your user ARN to the role's trust policy
2. Verify your user has `sts:AssumeRole` permission
3. Check the role ARN is correct

#### Error: "Access Denied" when accessing S3

**Cause**: IAM role/user lacks S3 permissions

**Solutions**:
1. Verify role/user has `s3:GetObject` and `s3:ListBucket` permissions
2. Check bucket name is correct
3. Verify S3 bucket policy allows your role/user

### Service Connection Issues

#### PreConditions API Connection Failed

**Check**:
- `PRECONDITIONS_DEPLOYMENT_URL` is correct
- `PRECONDITIONS_API_KEY` is valid
- LangGraph Cloud deployment is running
- Network connectivity to LangSmith

#### Airflow DAG Not Found

**Check**:
- `CONDITIONS_AI_API_URL` is correct
- `check_condition_v3` DAG exists and is deployed
- Username/password are correct
- Airflow webserver is accessible

### Logs and Debugging

**Enable DEBUG logging**:
```bash
# In .env
LOG_LEVEL=DEBUG
```

**Check which authentication method is being used**:
```
INFO: Assuming IAM role: arn:aws:iam::123456789012:role/YourS3AccessRole
# or
INFO: Creating S3 client with temporary credentials (session token)
# or
INFO: Creating S3 client with static credentials
# or
INFO: Using default AWS credential chain
```

---

## Architecture Summary

```
┌──────────────────────────────────────────────────────┐
│                  Conditions Agent                     │
│                                                       │
│  ┌──────────────┐                                    │
│  │   ReWOO      │  Planner → Worker → Solver         │
│  │   Agent      │                                     │
│  └──────┬───────┘                                    │
│         │                                             │
│         ├─→ [PreConditions API] (LangGraph Cloud)    │
│         │         ↓                                   │
│         │   Predict Deficiencies                     │
│         │                                             │
│         ├─→ [Conditions AI] (Airflow v3 DAG)         │
│         │         ↓                                   │
│         │   Validate Documents                       │
│         │         ↓                                   │
│         ├─→ [S3] Fetch Results                       │
│         │                                             │
│         └─→ [Synthesize] Final Results               │
│                                                       │
└──────────────────────────────────────────────────────┘
                        │
                        │ AWS Credentials
                        ↓
        ┌───────────────────────────────┐
        │  AWS (4 authentication modes) │
        │  1. Role Assumption           │
        │  2. Temporary Credentials     │
        │  3. Static Credentials        │
        │  4. Default Credential Chain  │
        └───────────────────────────────┘
```

---

## Next Steps

1. ✅ Complete environment configuration
2. ✅ Choose and configure AWS authentication method
3. ✅ Test S3 access
4. ✅ Run test scenarios
5. ✅ Start API server
6. ✅ Integrate with frontend

**For more details, see**:
- `DEVELOPER_GUIDE.md` - Workflows, troubleshooting, bug fixes
- `tests/test_rewoo_scenarios.py` - Example usage
- `api/main.py` - API endpoint documentation

---

## Support

**Configuration Issues**: Check `.env` file matches template above
**AWS Issues**: Verify IAM permissions and trust policies  
**Service Issues**: Check API URLs and credentials
**Bug Reports**: Include logs with `LOG_LEVEL=DEBUG`

**All set! Ready to process loan conditions** 🚀

