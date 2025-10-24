#!/bin/bash
# Quick start script for local development

echo "=========================================="
echo "Conditions Agent - Local Development Setup"
echo "=========================================="

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "⚠️  Please update .env with your LangSmith API key and other settings"
    exit 1
fi

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Starting PostgreSQL with Docker..."
docker-compose up -d postgres

echo "Waiting for PostgreSQL to be ready..."
sleep 5

echo "Starting API server..."
uvicorn api.main:app --reload --port 8000

