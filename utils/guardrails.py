"""Guardrails and validation for Conditions Agent."""
from typing import List, Dict, Any, Tuple
from datetime import datetime

from config.settings import settings
from database.repository import db_repository
from services.conditions_ai import ConditionEvaluationResult
from services.rack_and_stack import DocumentData
from utils.logging_config import get_logger

logger = get_logger(__name__)


class GuardrailsValidator:
    """Validator for applying guardrails to evaluation results."""
    
    def __init__(self):
        """Initialize guardrails validator."""
        self.confidence_threshold = settings.confidence_threshold
        self.max_cost_usd = settings.cost_budget_usd_per_execution
        self.business_rules = self._load_business_rules()
    
    def _load_business_rules(self) -> Dict[str, Any]:
        """Load active business rules from database."""
        try:
            rules = db_repository.get_active_rules()
            rules_dict = {}
            for rule in rules:
                rules_dict[rule.rule_name] = rule.rule_config
            logger.info(f"Loaded {len(rules_dict)} active business rules")
            return rules_dict
        except Exception as e:
            logger.warning(f"Could not load business rules from DB: {e}. Using defaults.")
            return {
                "confidence_threshold": {"threshold": 0.7},
                "citation_required": {"require_citations": True}
            }
    
    def validate_evaluations(
        self,
        evaluations: List[ConditionEvaluationResult],
        documents: List[DocumentData],
        cost_usd: float
    ) -> Tuple[List[ConditionEvaluationResult], bool, List[str]]:
        """
        Apply guardrails to evaluation results.
        
        Args:
            evaluations: List of evaluation results from Conditions AI
            documents: List of uploaded documents
            cost_usd: Total cost of the evaluation
            
        Returns:
            Tuple of (validated_evaluations, requires_human_review, issues)
        """
        validated_evaluations = []
        requires_human_review = False
        issues = []
        
        # Check cost limit
        if cost_usd > self.max_cost_usd:
            issues.append(f"Cost ${cost_usd:.2f} exceeds budget ${self.max_cost_usd:.2f}")
            logger.warning(f"Cost limit exceeded: ${cost_usd:.2f} > ${self.max_cost_usd:.2f}")
        
        # Validate each evaluation
        for evaluation in evaluations:
            validation_issues = []
            
            # Check confidence threshold
            if evaluation.confidence < self.confidence_threshold:
                validation_issues.append(f"Low confidence: {evaluation.confidence:.2f}")
                requires_human_review = True
            
            # Check for hallucination (citations)
            if self._check_hallucination(evaluation, documents):
                validation_issues.append("Potential hallucination detected")
                requires_human_review = True
            
            # Apply business rules
            rule_violations = self._check_business_rules(evaluation, documents)
            if rule_violations:
                validation_issues.extend(rule_violations)
                requires_human_review = True
            
            # Log issues
            if validation_issues:
                issues.append(f"Condition {evaluation.condition_id}: {', '.join(validation_issues)}")
                logger.info(f"Validation issues for {evaluation.condition_id}: {validation_issues}")
            
            validated_evaluations.append(evaluation)
        
        return validated_evaluations, requires_human_review, issues
    
    def _check_hallucination(
        self,
        evaluation: ConditionEvaluationResult,
        documents: List[DocumentData]
    ) -> bool:
        """
        Check for potential hallucinations in evaluation.
        
        Args:
            evaluation: Evaluation result to check
            documents: Available documents
            
        Returns:
            True if potential hallucination detected
        """
        # Check if citations are required
        citation_rule = self.business_rules.get("citation_required", {})
        if not citation_rule.get("require_citations", True):
            return False
        
        # If result is satisfied but no citations provided
        if evaluation.result == "satisfied" and not evaluation.citations:
            logger.warning(f"No citations for satisfied condition {evaluation.condition_id}")
            return True
        
        # Check if cited documents exist
        if evaluation.citations:
            available_doc_ids = {doc.document_id for doc in documents}
            for citation in evaluation.citations:
                if citation not in available_doc_ids:
                    logger.warning(f"Citation {citation} not found in available documents")
                    return True
        
        return False
    
    def _check_business_rules(
        self,
        evaluation: ConditionEvaluationResult,
        documents: List[DocumentData]
    ) -> List[str]:
        """
        Check evaluation against business rules.
        
        Args:
            evaluation: Evaluation result to check
            documents: Available documents
            
        Returns:
            List of rule violations
        """
        violations = []
        
        # Example business rule checks
        # These would be customized based on actual requirements
        
        # Rule: High-priority conditions must have high confidence
        if hasattr(evaluation, 'priority'):
            if evaluation.priority == "high" and evaluation.confidence < 0.85:
                violations.append(f"High-priority condition has low confidence: {evaluation.confidence:.2f}")
        
        # Rule: Uncertain results should provide reasoning
        if evaluation.result == "uncertain" and not evaluation.reasoning:
            violations.append("Uncertain result without reasoning")
        
        # Add more business rule checks as needed
        
        return violations
    
    def check_timeout(self, start_time: datetime) -> bool:
        """
        Check if execution has exceeded timeout.
        
        Args:
            start_time: Execution start time
            
        Returns:
            True if timeout exceeded
        """
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        max_timeout = settings.max_execution_timeout_seconds
        
        if elapsed > max_timeout:
            logger.warning(f"Execution timeout: {elapsed:.1f}s > {max_timeout}s")
            return True
        
        return False


# Global guardrails validator instance
guardrails_validator = GuardrailsValidator()

