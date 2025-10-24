@echo off
REM Quick start script for local development on Windows

echo ==========================================
echo Conditions Agent - Local Development Setup
echo ==========================================

REM Check if .env exists
if not exist .env (
    echo Creating .env from .env.example...
    copy .env.example .env
    echo WARNING: Please update .env with your LangSmith API key and other settings
    exit /b 1
)

REM Check if venv exists
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing dependencies...
pip install -r requirements.txt

echo Starting PostgreSQL with Docker...
docker-compose up -d postgres

echo Waiting for PostgreSQL to be ready...
timeout /t 5 /nobreak >nul

echo Starting API server...
uvicorn api.main:app --reload --port 8000

