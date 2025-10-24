"""
Database repository for CRUD operations.
NOTE: This is a TEMPLATE and will be finalized later
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

from config.settings import settings
from database.models import (
    Base, AgentExecution, ConditionEvaluation, 
    RMFeedback, LoanState, BusinessRule
)


class DatabaseRepository:
    """Repository for database operations."""
    
    def __init__(self, database_url: Optional[str] = None):
        """Initialize database connection."""
        url = database_url or settings.database_url
        self.engine = create_engine(
            url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            echo=False
        )
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)
    
    def create_tables(self):
        """Create all tables."""
        Base.metadata.create_all(self.engine)
    
    def get_session(self) -> Session:
        """Get a database session."""
        return self.SessionLocal()
    
    # Agent Execution Operations
    
    def create_execution(
        self,
        loan_guid: str,
        trace_id: Optional[str] = None
    ) -> AgentExecution:
        """Create a new agent execution record."""
        with self.get_session() as session:
            execution = AgentExecution(
                loan_guid=loan_guid,
                trace_id=trace_id,
                status="running"
            )
            session.add(execution)
            session.commit()
            session.refresh(execution)
            return execution
    
    def update_execution_status(
        self,
        execution_id: UUID,
        status: str,
        error_message: Optional[str] = None,
        total_tokens: Optional[int] = None,
        cost_usd: Optional[float] = None,
        latency_ms: Optional[int] = None
    ) -> AgentExecution:
        """Update execution status and metrics."""
        with self.get_session() as session:
            execution = session.get(AgentExecution, execution_id)
            if execution:
                execution.status = status
                execution.completed_at = datetime.utcnow()
                if error_message:
                    execution.error_message = error_message
                if total_tokens is not None:
                    execution.total_tokens = total_tokens
                if cost_usd is not None:
                    execution.cost_usd = cost_usd
                if latency_ms is not None:
                    execution.latency_ms = latency_ms
                session.commit()
                session.refresh(execution)
            return execution
    
    def get_execution(self, execution_id: UUID) -> Optional[AgentExecution]:
        """Get execution by ID."""
        with self.get_session() as session:
            return session.get(AgentExecution, execution_id)
    
    # Condition Evaluation Operations
    
    def create_evaluations(
        self,
        execution_id: UUID,
        evaluations: List[dict]
    ) -> List[ConditionEvaluation]:
        """Create multiple condition evaluations."""
        with self.get_session() as session:
            eval_records = []
            for eval_data in evaluations:
                evaluation = ConditionEvaluation(
                    execution_id=execution_id,
                    condition_id=eval_data["condition_id"],
                    condition_text=eval_data["condition_text"],
                    result=eval_data["result"],
                    confidence=eval_data.get("confidence"),
                    model_used=eval_data.get("model_used"),
                    reasoning=eval_data.get("reasoning"),
                    citations=eval_data.get("citations")
                )
                session.add(evaluation)
                eval_records.append(evaluation)
            session.commit()
            for record in eval_records:
                session.refresh(record)
            return eval_records
    
    def get_evaluations_by_execution(
        self,
        execution_id: UUID
    ) -> List[ConditionEvaluation]:
        """Get all evaluations for an execution."""
        with self.get_session() as session:
            stmt = select(ConditionEvaluation).where(
                ConditionEvaluation.execution_id == execution_id
            )
            return list(session.scalars(stmt).all())
    
    # RM Feedback Operations
    
    def create_feedback(
        self,
        evaluation_id: UUID,
        rm_user_id: str,
        feedback_type: str,
        corrected_result: Optional[str] = None,
        notes: Optional[str] = None
    ) -> RMFeedback:
        """Create RM feedback."""
        with self.get_session() as session:
            feedback = RMFeedback(
                evaluation_id=evaluation_id,
                rm_user_id=rm_user_id,
                feedback_type=feedback_type,
                corrected_result=corrected_result,
                notes=notes
            )
            session.add(feedback)
            session.commit()
            session.refresh(feedback)
            return feedback
    
    # Loan State Operations
    
    def upsert_loan_state(
        self,
        loan_guid: str,
        current_status: str,
        last_execution_id: UUID,
        conditions_count: int = 0,
        satisfied_count: int = 0,
        unsatisfied_count: int = 0,
        uncertain_count: int = 0
    ) -> LoanState:
        """Create or update loan state."""
        with self.get_session() as session:
            loan_state = session.get(LoanState, loan_guid)
            if loan_state:
                loan_state.current_status = current_status
                loan_state.last_execution_id = last_execution_id
                loan_state.conditions_count = conditions_count
                loan_state.satisfied_count = satisfied_count
                loan_state.unsatisfied_count = unsatisfied_count
                loan_state.uncertain_count = uncertain_count
            else:
                loan_state = LoanState(
                    loan_guid=loan_guid,
                    current_status=current_status,
                    last_execution_id=last_execution_id,
                    conditions_count=conditions_count,
                    satisfied_count=satisfied_count,
                    unsatisfied_count=unsatisfied_count,
                    uncertain_count=uncertain_count
                )
                session.add(loan_state)
            session.commit()
            session.refresh(loan_state)
            return loan_state
    
    def get_loan_state(self, loan_guid: str) -> Optional[LoanState]:
        """Get loan state by loan GUID."""
        with self.get_session() as session:
            return session.get(LoanState, loan_guid)
    
    # Business Rules Operations
    
    def get_active_rules(self, rule_type: Optional[str] = None) -> List[BusinessRule]:
        """Get active business rules, optionally filtered by type."""
        with self.get_session() as session:
            stmt = select(BusinessRule).where(BusinessRule.active == True)
            if rule_type:
                stmt = stmt.where(BusinessRule.rule_type == rule_type)
            stmt = stmt.order_by(BusinessRule.priority.desc())
            return list(session.scalars(stmt).all())
    
    def get_rule_by_name(self, rule_name: str) -> Optional[BusinessRule]:
        """Get business rule by name."""
        with self.get_session() as session:
            stmt = select(BusinessRule).where(BusinessRule.rule_name == rule_name)
            return session.scalars(stmt).first()


# Global repository instance
db_repository = DatabaseRepository()

