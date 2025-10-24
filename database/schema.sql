-- =============================================================================
-- Conditions Agent PostgreSQL Schema
-- =============================================================================
-- NOTE: This is a TEMPLATE schema and will be finalized later
-- =============================================================================

-- Core execution tracking
-- Stores high-level information about each agent execution
CREATE TABLE IF NOT EXISTS agent_executions (
    execution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_guid VARCHAR(255) NOT NULL,
    trace_id VARCHAR(255),
    status VARCHAR(50) NOT NULL, -- 'running', 'completed', 'failed', 'timeout'
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    total_tokens INTEGER DEFAULT 0,
    cost_usd DECIMAL(10,4) DEFAULT 0.0,
    latency_ms INTEGER,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_executions_loan_guid ON agent_executions(loan_guid);
CREATE INDEX IF NOT EXISTS idx_agent_executions_trace_id ON agent_executions(trace_id);
CREATE INDEX IF NOT EXISTS idx_agent_executions_status ON agent_executions(status);

-- Condition-level results
-- Stores individual evaluation results for each condition
CREATE TABLE IF NOT EXISTS condition_evaluations (
    evaluation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id UUID NOT NULL REFERENCES agent_executions(execution_id) ON DELETE CASCADE,
    condition_id VARCHAR(255) NOT NULL,
    condition_text TEXT NOT NULL,
    result VARCHAR(50) NOT NULL, -- 'satisfied', 'unsatisfied', 'uncertain'
    confidence DECIMAL(3,2), -- 0.00 to 1.00
    model_used VARCHAR(50), -- e.g., 'gpt-5-mini', 'claude-sonnet-4.5'
    reasoning TEXT,
    citations JSONB, -- References to specific documents/sections
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_condition_evaluations_execution_id ON condition_evaluations(execution_id);
CREATE INDEX IF NOT EXISTS idx_condition_evaluations_condition_id ON condition_evaluations(condition_id);
CREATE INDEX IF NOT EXISTS idx_condition_evaluations_result ON condition_evaluations(result);

-- Human review feedback (Relationship Manager feedback)
-- Stores RM corrections and feedback for continuous improvement
CREATE TABLE IF NOT EXISTS rm_feedback (
    feedback_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id UUID NOT NULL REFERENCES condition_evaluations(evaluation_id) ON DELETE CASCADE,
    rm_user_id VARCHAR(255) NOT NULL,
    feedback_type VARCHAR(50) NOT NULL, -- 'approve', 'reject', 'correct'
    corrected_result VARCHAR(50), -- If feedback_type is 'correct'
    notes TEXT,
    submitted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rm_feedback_evaluation_id ON rm_feedback(evaluation_id);
CREATE INDEX IF NOT EXISTS idx_rm_feedback_rm_user_id ON rm_feedback(rm_user_id);
CREATE INDEX IF NOT EXISTS idx_rm_feedback_feedback_type ON rm_feedback(feedback_type);

-- Loan state persistence
-- Maintains current status of each loan through the conditions evaluation process
CREATE TABLE IF NOT EXISTS loan_state (
    loan_guid VARCHAR(255) PRIMARY KEY,
    current_status VARCHAR(50) NOT NULL, -- 'pending', 'evaluating', 'needs_review', 'approved', 'rejected'
    last_execution_id UUID REFERENCES agent_executions(execution_id),
    conditions_count INTEGER DEFAULT 0,
    satisfied_count INTEGER DEFAULT 0,
    unsatisfied_count INTEGER DEFAULT 0,
    uncertain_count INTEGER DEFAULT 0,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_loan_state_status ON loan_state(current_status);
CREATE INDEX IF NOT EXISTS idx_loan_state_updated_at ON loan_state(updated_at);

-- Business rules
-- Configurable rules for validation and guardrails
CREATE TABLE IF NOT EXISTS business_rules (
    rule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_name VARCHAR(255) NOT NULL UNIQUE,
    rule_type VARCHAR(50) NOT NULL, -- 'hallucination_check', 'confidence_threshold', 'document_validation', etc.
    rule_config JSONB NOT NULL, -- Flexible JSON configuration for each rule
    active BOOLEAN NOT NULL DEFAULT true,
    priority INTEGER DEFAULT 0, -- Higher priority rules execute first
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_business_rules_type ON business_rules(rule_type);
CREATE INDEX IF NOT EXISTS idx_business_rules_active ON business_rules(active);

-- =============================================================================
-- Trigger for automatic updated_at timestamp updates
-- =============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_agent_executions_updated_at BEFORE UPDATE ON agent_executions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_loan_state_updated_at BEFORE UPDATE ON loan_state
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_business_rules_updated_at BEFORE UPDATE ON business_rules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Sample Business Rules (for reference - to be customized)
-- =============================================================================
INSERT INTO business_rules (rule_name, rule_type, rule_config, description) VALUES
('confidence_threshold', 'confidence_threshold', '{"threshold": 0.7}', 'Minimum confidence score for auto-approval'),
('max_execution_time', 'timeout', '{"seconds": 30}', 'Maximum execution time for agent'),
('cost_limit', 'cost_limit', '{"max_usd": 5.0}', 'Maximum cost per execution'),
('citation_required', 'hallucination_check', '{"require_citations": true}', 'Require document citations for all evaluations')
ON CONFLICT (rule_name) DO NOTHING;

