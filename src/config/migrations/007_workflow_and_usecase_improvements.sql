-- Migration 007: Workflow extensions and use case system

-- Extend workflow_steps with input mapping and conditions
ALTER TABLE workflow_steps ADD COLUMN IF NOT EXISTS input_mapping JSONB DEFAULT '{}';
ALTER TABLE workflow_steps ADD COLUMN IF NOT EXISTS output_key VARCHAR(255);
ALTER TABLE workflow_steps ADD COLUMN IF NOT EXISTS condition_type VARCHAR(50) DEFAULT 'always';
ALTER TABLE workflow_steps ADD COLUMN IF NOT EXISTS condition JSONB DEFAULT '{}';

-- Workflow execution tracking
CREATE TABLE IF NOT EXISTS workflow_executions (
    id SERIAL PRIMARY KEY,
    workflow_id INTEGER NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'running',
    context JSONB DEFAULT '{}',
    error_message TEXT,
    started_at TIMESTAMP DEFAULT NOW() NOT NULL,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE TABLE IF NOT EXISTS workflow_step_executions (
    id SERIAL PRIMARY KEY,
    execution_id INTEGER NOT NULL REFERENCES workflow_executions(id) ON DELETE CASCADE,
    step_order INTEGER NOT NULL,
    operation_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    input_data JSONB DEFAULT '{}',
    output_data JSONB DEFAULT '{}',
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

-- Use cases as first-class entities
CREATE TABLE IF NOT EXISTS use_cases (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE TABLE IF NOT EXISTS use_case_workflows (
    id SERIAL PRIMARY KEY,
    use_case_id INTEGER NOT NULL REFERENCES use_cases(id) ON DELETE CASCADE,
    workflow_id INTEGER NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    UNIQUE(use_case_id, workflow_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_workflow_executions_workflow_id ON workflow_executions(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_user_id ON workflow_executions(user_id);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_status ON workflow_executions(status);
CREATE INDEX IF NOT EXISTS idx_workflow_step_executions_execution_id ON workflow_step_executions(execution_id);
CREATE INDEX IF NOT EXISTS idx_use_cases_name ON use_cases(name);
CREATE INDEX IF NOT EXISTS idx_use_cases_category ON use_cases(category);
CREATE INDEX IF NOT EXISTS idx_use_case_workflows_use_case_id ON use_case_workflows(use_case_id);
CREATE INDEX IF NOT EXISTS idx_use_case_workflows_workflow_id ON use_case_workflows(workflow_id);
