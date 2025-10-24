# Quick Start Guide

Get the Conditions Agent running in under 5 minutes.

## Prerequisites

- Python 3.11+
- Docker & Docker Compose
- LangSmith account (get API key from https://smith.langchain.com/)

## Option 1: Docker Compose (Recommended)

### 1. Set up environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your LangSmith API key
# LANGSMITH_API_KEY=your_key_here
```

### 2. Start all services

```bash
docker-compose up
```

This will start:
- PostgreSQL database on port 5432
- Conditions Agent API on port 8000

### 3. Test the API

Open another terminal:

```bash
# Run the example script
python example_usage.py
```

Or test with curl:

```bash
# Health check
curl http://localhost:8000/health

# Evaluate conditions
curl -X POST http://localhost:8000/api/v1/evaluate-conditions \
  -H "Content-Type: application/json" \
  -d '{
    "loan_guid": "loan_123",
    "condition_doc_ids": ["doc_001", "doc_002", "doc_003"]
  }'
```

## Option 2: Local Development

### 1. Set up Python environment

```bash
# Create virtual environment
python -m venv venv

# Activate (Linux/Mac)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Set up PostgreSQL

```bash
# Start PostgreSQL with Docker
docker-compose up -d postgres

# Wait a few seconds for it to be ready
```

### 3. Configure environment

```bash
# Copy and edit .env
cp .env.example .env
# Add your LangSmith API key
```

### 4. Run the API

```bash
uvicorn api.main:app --reload --port 8000
```

### 5. Run example

In another terminal:

```bash
python example_usage.py
```

## Quick Scripts

### Linux/Mac

```bash
chmod +x run_local.sh
./run_local.sh
```

### Windows

```bash
run_local.bat
```

## What's Running?

After startup, you'll have:

1. **API Server**: http://localhost:8000
   - Health: http://localhost:8000/health
   - Docs: http://localhost:8000/docs
   - Redoc: http://localhost:8000/redoc

2. **PostgreSQL**: localhost:5432
   - Database: conditions_agent
   - User: conditions_user
   - Password: conditions_pass

3. **LangSmith Traces**: https://smith.langchain.com/

## Next Steps

1. **View Traces**: Check LangSmith dashboard for execution traces
2. **Explore API**: Visit http://localhost:8000/docs for interactive API docs
3. **Customize Mocks**: Edit `services/*.py` to change mock responses
4. **Add Business Rules**: Insert rules into `business_rules` table
5. **Integrate Real APIs**: Update service clients with actual endpoints

## Troubleshooting

### Port Already in Use

If port 8000 or 5432 is already in use:

```bash
# Change API port in docker-compose.yml or use:
uvicorn api.main:app --port 8001

# Change PostgreSQL port in docker-compose.yml
```

### Database Connection Failed

```bash
# Check if PostgreSQL is running
docker ps

# View PostgreSQL logs
docker logs conditions-agent-db

# Restart PostgreSQL
docker-compose restart postgres
```

### Missing Dependencies

```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### LangSmith Not Showing Traces

Check `.env` has:
```bash
LANGSMITH_TRACING_V2=true
LANGSMITH_API_KEY=your_actual_key
LANGSMITH_PROJECT=conditions-agent
```

## Stopping Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (fresh start)
docker-compose down -v
```

## Example Output

When you run `python example_usage.py`, you should see:

```
================================================================================
CONDITIONS AGENT - EXAMPLE USAGE
================================================================================

1. Checking API health...
Status: 200
{'langsmith_enabled': True, 'status': 'healthy', 'version': '1.0.0'}

2. Evaluating conditions for loan...

Request:
{'condition_doc_ids': ['doc_001', 'doc_002', 'doc_003'],
 'loan_guid': 'loan_example_001'}

Status: 200

--- EVALUATION RESULTS ---
Execution ID: 550e8400-e29b-41d4-a716-446655440000
Status: completed
Requires Human Review: False
Trace URL: https://smith.langchain.com/o/conditions-agent/runs/...

--- METADATA ---
Total Tokens: 2500
Cost: $0.1500
Latency: 1850ms
Model Breakdown: {'gpt-5-mini': 2, 'claude-sonnet-4.5': 2}

--- CONDITION EVALUATIONS (4) ---

1. Condition: Provide proof of income for the last 2 years
   ID: cond_001
   Result: SATISFIED
   Confidence: 95.00%
   Model: gpt-5-mini
   Reasoning: W-2 form for 2024 provided showing annual wages of $85,000
   Citations: doc_001

...
```

## Need Help?

- Check the main [README.md](README.md) for detailed documentation
- Review API docs at http://localhost:8000/docs
- Check LangSmith traces for debugging
- Contact the team on Slack: #conditions-agent

