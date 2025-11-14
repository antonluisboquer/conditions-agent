# Conditions Agent - Documentation Index

**Last Updated**: November 14, 2025

All documentation consolidated into 2 comprehensive guides + 1 implementation reference.

---

## 📚 Core Documentation

### 1. [SETUP_GUIDE.md](SETUP_GUIDE.md) - **START HERE**

**For**: First-time setup, configuration, environment variables

**Covers**:
- ✅ Quick start instructions
- ✅ Environment configuration (.env file)
- ✅ **AWS credential setup (4 authentication methods)**
  - IAM Role Assumption (recommended)
  - Temporary credentials with session token
  - Static credentials (legacy)
  - Default credential chain
- ✅ Service integrations (PreConditions API, Conditions AI)
- ✅ Testing your setup
- ✅ Troubleshooting common issues

**Read this if**:
- You're setting up the agent for the first time
- You need to configure AWS credentials
- You're getting authentication errors
- You want to test your setup

---

### 2. [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)

**For**: Developers working with the agent, understanding workflows, debugging

**Covers**:
- ✅ **4 Agent workflows** (Deficiencies Only, Validation Only, S3 Access, Full Evaluation)
- ✅ **Data transformations** (PreConditions → Conditions AI mapping)
- ✅ **Recent bug fixes** (Session token, Validation scenario, S3 polling, DAG skipping)
- ✅ **Edge case handling** (No relevant documents, graceful failures)
- ✅ **Airflow DAG troubleshooting** (Skipped tasks, XCom debugging, relevance filtering)
- ✅ **Performance & optimization** (Polling timeouts, credential refresh, logging)
- ✅ **Testing best practices** (Test data guidelines, edge cases)

**Read this if**:
- You're developing new features
- You need to understand data transformations
- You're debugging Airflow DAG issues
- You want to understand recent changes
- You're handling edge cases

---

### 3. [STREAMING_IMPLEMENTATION.md](STREAMING_IMPLEMENTATION.md) - Reference

**For**: Understanding the streaming architecture and frontend integration

**Covers**:
- ✅ Streaming API endpoint documentation
- ✅ Server-Sent Events (SSE) integration
- ✅ Frontend JavaScript examples
- ✅ Node-by-node streaming updates
- ✅ Complete architecture overview

**Read this if**:
- You're integrating the frontend
- You need to understand the streaming workflow
- You want to see code examples for SSE

---

## 🚀 Quick Links

### Getting Started
1. [Install dependencies](SETUP_GUIDE.md#quick-start)
2. [Configure .env file](SETUP_GUIDE.md#environment-configuration)
3. [Setup AWS credentials](SETUP_GUIDE.md#aws-credential-setup)
4. [Test your setup](SETUP_GUIDE.md#testing-your-setup)

### Common Tasks
- **Configure AWS Role Assumption**: [SETUP_GUIDE.md - Option 1](SETUP_GUIDE.md#option-1-iam-role-assumption--recommended)
- **Fix validation scenario errors**: [DEVELOPER_GUIDE.md - Fix 2](DEVELOPER_GUIDE.md#fix-2-validation-scenario-worker-error-november-2025)
- **Debug Airflow DAG skipping**: [DEVELOPER_GUIDE.md - Airflow Troubleshooting](DEVELOPER_GUIDE.md#airflow-dag-troubleshooting)
- **Handle no relevant documents**: [DEVELOPER_GUIDE.md - Edge Cases](DEVELOPER_GUIDE.md#no-relevant-documents-scenario-november-2025)

### Architecture
- **Workflows**: [DEVELOPER_GUIDE.md - Agent Workflows](DEVELOPER_GUIDE.md#agent-workflows)
- **Data Transformations**: [DEVELOPER_GUIDE.md - Data Transformations](DEVELOPER_GUIDE.md#data-transformations)
- **Streaming**: [STREAMING_IMPLEMENTATION.md](STREAMING_IMPLEMENTATION.md)

---

## 📝 Test Files

Located in `tests/`:

- `test_s3_access.py` - Verify S3 connectivity and credentials
- `test_rewoo_scenarios.py` - Test all 4 agent workflows
- `scenario_1_deficiencies_only.json` - Test deficiency prediction
- `scenario_2_validation_only.json` - Test document validation
- `scenario_3_s3_access.json` - Test S3 file access
- `scenario_4_full_evaluation.json` - Test complete workflow

**Run tests**:
```bash
# Test S3 access
python tests/test_s3_access.py

# Test agent scenarios
python tests/test_rewoo_scenarios.py
```

---

## 🔄 Recent Changes (November 2025)

### AWS Credential Enhancements
- Added support for **4 authentication methods** (IAM role, temp creds, static, default)
- Fixed session token handling in test scripts
- Implemented automatic credential refresh

### Bug Fixes
- ✅ Validation scenario worker error (added metadata transformer)
- ✅ S3 polling timeout (increased to 180s)
- ✅ Airflow DAG tasks skipping (document-condition matching)
- ✅ No relevant documents handling (graceful failures)

### Data Transformation Updates
- Prioritize `final_results.top_n` over `deficient_conditions`
- Category field: combined string of ALL compartments
- Support for 3 input formats in `call_conditions_ai_api`

**Full details**: [DEVELOPER_GUIDE.md - Recent Bug Fixes](DEVELOPER_GUIDE.md#recent-bug-fixes)

---

## 🆘 Need Help?

### Setup Issues
→ [SETUP_GUIDE.md - Troubleshooting](SETUP_GUIDE.md#troubleshooting)

### AWS Credential Issues
→ [SETUP_GUIDE.md - AWS Credential Setup](SETUP_GUIDE.md#aws-credential-setup)

### Airflow DAG Problems
→ [DEVELOPER_GUIDE.md - Airflow Troubleshooting](DEVELOPER_GUIDE.md#airflow-dag-troubleshooting)

### API Integration
→ [STREAMING_IMPLEMENTATION.md](STREAMING_IMPLEMENTATION.md)

---

## 📊 Status

**Agent Status**: ✅ Production Ready

**Supported Workflows**: 4
- Deficiencies Only
- Validation Only
- S3 Access Test
- Full Evaluation

**Edge Cases Handled**:
- ✅ No relevant documents
- ✅ Empty conditions
- ✅ S3 access errors
- ✅ Airflow DAG failures
- ✅ Authentication errors

**Documentation Status**: ✅ Complete and Up-to-Date

---

## 📂 File Structure

```
conditions-agent/
├── DOCS_INDEX.md                    ← You are here
├── SETUP_GUIDE.md                   ← Setup & configuration
├── DEVELOPER_GUIDE.md               ← Workflows & troubleshooting
├── STREAMING_IMPLEMENTATION.md      ← Streaming architecture
│
├── agent/                           ← ReWOO agent implementation
├── api/                             ← FastAPI endpoints
├── config/                          ← Settings & configuration
├── services/                        ← API clients (PreConditions, Conditions AI)
├── utils/                           ← Helpers (transformers, AWS credentials)
└── tests/                           ← Test scenarios & scripts
```

---

**Questions? Check the guides above or review the code comments.**

**Ready to get started?** → [SETUP_GUIDE.md](SETUP_GUIDE.md) 🚀

