"""
SQLAlchemy ORM models for Conditions Agent.
NOTE: This is a TEMPLATE and will be finalized later
"""
from datetime import datetime
from typing import Optional
from uuid import uuid4
from sqlalchemy import (
    Column, String, Integer, DateTime, Text, Boolean, 
    DECIMAL, ForeignKey, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class AgentExecution(Base):
    """Agent execution tracking."""
    __tablename__ = "agent_executions"
    
    execution_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    loan_guid = Column(String(255), nullable=False, index=True)
    trace_id = Column(String(255), index=True)
    status = Column(String(50), nullable=False, index=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime)
    total_tokens = Column(Integer, default=0)
    cost_usd = Column(DECIMAL(10, 4), default=0.0)
    latency_ms = Column(Integer)
    error_message = Column(Text)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    evaluations = relationship("ConditionEvaluation", back_populates="execution", cascade="all, delete-orphan")


class ConditionEvaluation(Base):
    """Condition-level evaluation results."""
    __tablename__ = "condition_evaluations"
    
    evaluation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    execution_id = Column(UUID(as_uuid=True), ForeignKey("agent_executions.execution_id", ondelete="CASCADE"), nullable=False, index=True)
    condition_id = Column(String(255), nullable=False, index=True)
    condition_text = Column(Text, nullable=False)
    result = Column(String(50), nullable=False, index=True)
    confidence = Column(DECIMAL(3, 2))
    model_used = Column(String(50))
    reasoning = Column(Text)
    citations = Column(JSON)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    execution = relationship("AgentExecution", back_populates="evaluations")
    feedback = relationship("RMFeedback", back_populates="evaluation", cascade="all, delete-orphan")


class RMFeedback(Base):
    """Relationship Manager feedback."""
    __tablename__ = "rm_feedback"
    
    feedback_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    evaluation_id = Column(UUID(as_uuid=True), ForeignKey("condition_evaluations.evaluation_id", ondelete="CASCADE"), nullable=False, index=True)
    rm_user_id = Column(String(255), nullable=False, index=True)
    feedback_type = Column(String(50), nullable=False, index=True)
    corrected_result = Column(String(50))
    notes = Column(Text)
    submitted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    evaluation = relationship("ConditionEvaluation", back_populates="feedback")


class LoanState(Base):
    """Loan state persistence."""
    __tablename__ = "loan_state"
    
    loan_guid = Column(String(255), primary_key=True)
    current_status = Column(String(50), nullable=False, index=True)
    last_execution_id = Column(UUID(as_uuid=True), ForeignKey("agent_executions.execution_id"))
    conditions_count = Column(Integer, default=0)
    satisfied_count = Column(Integer, default=0)
    unsatisfied_count = Column(Integer, default=0)
    uncertain_count = Column(Integer, default=0)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)


class BusinessRule(Base):
    """Business rules configuration."""
    __tablename__ = "business_rules"
    
    rule_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    rule_name = Column(String(255), nullable=False, unique=True)
    rule_type = Column(String(50), nullable=False, index=True)
    rule_config = Column(JSON, nullable=False)
    active = Column(Boolean, nullable=False, default=True, index=True)
    priority = Column(Integer, default=0)
    description = Column(Text)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

