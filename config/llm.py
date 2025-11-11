"""Centralised LLM configuration used by the ReWOO agent."""
from __future__ import annotations

from langchain_openai import ChatOpenAI

from config.settings import settings

planner_llm = ChatOpenAI(
    model=settings.planner_model,
    temperature=settings.planner_temperature,
    streaming=False,
    api_key=settings.openai_api_key,
)

solver_llm = ChatOpenAI(
    model=settings.solver_model,
    temperature=settings.solver_temperature,
    streaming=False,
    api_key=settings.openai_api_key,
)

