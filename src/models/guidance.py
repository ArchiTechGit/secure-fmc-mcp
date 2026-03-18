"""Guidance system models for API assistance and workflows."""

from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.config.database import Base

if TYPE_CHECKING:
    from typing import Any


class APIGuidance(Base):
    """Model for API-level guidance and recommendations."""

    __tablename__ = "api_guidance"
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True, index=True)
    api_name = Column(String(50), unique=True, nullable=False, index=True)
    display_name = Column(String(100), nullable=False)
    description = Column(Text)
    when_to_use = Column(Text)
    when_not_to_use = Column(Text)
    examples = Column(JSONB, default=list)
    priority = Column(Integer, default=0, index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<APIGuidance(api_name='{self.api_name}', display_name='{self.display_name}')>"

    def to_dict(self) -> dict:
        """Convert API guidance to dictionary.

        Returns:
            Dictionary representation of API guidance
        """
        return {
            "id": self.id,
            "api_name": self.api_name,
            "display_name": self.display_name,
            "description": self.description,
            "when_to_use": self.when_to_use,
            "when_not_to_use": self.when_not_to_use,
            "examples": self.examples if self.examples else [],
            "priority": self.priority,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CategoryGuidance(Base):
    """Model for category/tag-level guidance."""

    __tablename__ = "category_guidance"
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True, index=True)
    api_name = Column(String(50), nullable=False, index=True)
    category_name = Column(String(255), nullable=False, index=True)
    display_name = Column(String(255))
    description = Column(Text)
    when_to_use = Column(Text)
    related_categories = Column(JSONB, default=list)
    priority = Column(Integer, default=0, index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Unique constraint
    __table_args__ = (
        UniqueConstraint("api_name", "category_name", name="uq_api_category"),
    )

    def __repr__(self) -> str:
        return f"<CategoryGuidance(api_name='{self.api_name}', category='{self.category_name}')>"

    def to_dict(self) -> dict:
        """Convert category guidance to dictionary.

        Returns:
            Dictionary representation of category guidance
        """
        return {
            "id": self.id,
            "api_name": self.api_name,
            "category_name": self.category_name,
            "display_name": self.display_name,
            "description": self.description,
            "when_to_use": self.when_to_use,
            "related_categories": self.related_categories if self.related_categories else [],
            "priority": self.priority,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Workflow(Base):
    """Model for workflow definitions."""

    __tablename__ = "workflows"
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text)
    problem_statement = Column(Text)
    use_case_tags = Column(JSONB, default=list)
    is_active = Column(Boolean, default=True, index=True)
    priority = Column(Integer, default=0, index=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    steps = relationship(
        "WorkflowStep",
        back_populates="workflow",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="WorkflowStep.step_order"
    )

    def __repr__(self) -> str:
        return f"<Workflow(name='{self.name}', display_name='{self.display_name}')>"

    def to_dict(self, include_steps: bool = True) -> dict:
        """Convert workflow to dictionary.

        Args:
            include_steps: Whether to include workflow steps

        Returns:
            Dictionary representation of workflow
        """
        data = {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "problem_statement": self.problem_statement,
            "use_case_tags": self.use_case_tags if self.use_case_tags else [],
            "is_active": self.is_active,
            "priority": self.priority,
            "steps_count": len(self.steps) if self.steps else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_steps and self.steps:
            data["steps"] = [step.to_dict() for step in self.steps]
        return data


class WorkflowStep(Base):
    """Model for steps within workflows."""

    __tablename__ = "workflow_steps"
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(
        Integer,
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    step_order = Column(Integer, nullable=False, index=True)
    operation_name = Column(String(255), nullable=False)
    description = Column(Text)
    expected_output = Column(Text)
    optional = Column(Boolean, default=False)
    fallback_operation = Column(String(255))
    input_mapping = Column(JSONB, default=dict)   # {"param": "{{step_1.output.field}}"}
    output_key = Column(String(255))              # Key to store step output
    condition_type = Column(String(50), default="always")  # "always", "if_equals", "if_not_empty", "if_error"
    condition = Column(JSONB, default=dict)       # Condition details
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    workflow = relationship("Workflow", back_populates="steps")

    # Unique constraint
    __table_args__ = (
        UniqueConstraint("workflow_id", "step_order", name="uq_workflow_step_order"),
    )

    def __repr__(self) -> str:
        return f"<WorkflowStep(workflow_id={self.workflow_id}, order={self.step_order}, operation='{self.operation_name}')>"

    def to_dict(self) -> dict:
        """Convert workflow step to dictionary.

        Returns:
            Dictionary representation of workflow step
        """
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "step_order": self.step_order,
            "operation_name": self.operation_name,
            "description": self.description,
            "expected_output": self.expected_output,
            "optional": self.optional,
            "fallback_operation": self.fallback_operation,
            "input_mapping": self.input_mapping if self.input_mapping else {},
            "output_key": self.output_key,
            "condition_type": self.condition_type or "always",
            "condition": self.condition if self.condition else {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ToolDescriptionOverride(Base):
    """Model for enhanced tool descriptions and usage hints."""

    __tablename__ = "tool_description_overrides"
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True, index=True)
    operation_name = Column(String(255), unique=True, nullable=False, index=True)
    enhanced_description = Column(Text)
    usage_hint = Column(Text)
    related_tools = Column(JSONB, default=list)
    common_parameters = Column(JSONB, default=list)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<ToolDescriptionOverride(operation_name='{self.operation_name}')>"

    def to_dict(self) -> dict:
        """Convert tool description override to dictionary.

        Returns:
            Dictionary representation of tool description override
        """
        return {
            "id": self.id,
            "operation_name": self.operation_name,
            "enhanced_description": self.enhanced_description,
            "usage_hint": self.usage_hint,
            "related_tools": self.related_tools if self.related_tools else [],
            "common_parameters": self.common_parameters if self.common_parameters else [],
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class SystemPromptSection(Base):
    """Model for system prompt sections."""

    __tablename__ = "system_prompt_sections"
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True, index=True)
    section_name = Column(String(100), unique=True, nullable=False, index=True)
    section_order = Column(Integer, default=0, index=True)
    title = Column(String(255))
    content = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<SystemPromptSection(section_name='{self.section_name}', order={self.section_order})>"

    def to_dict(self) -> dict:
        """Convert system prompt section to dictionary.

        Returns:
            Dictionary representation of system prompt section
        """
        return {
            "id": self.id,
            "section_name": self.section_name,
            "section_order": self.section_order,
            "title": self.title,
            "content": self.content,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class WorkflowExecution(Base):
    """Model for tracking workflow execution runs."""

    __tablename__ = "workflow_executions"
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    status = Column(String(50), default="running", nullable=False)  # running, completed, failed, cancelled
    context = Column(JSONB, default=dict)  # Execution context/variables
    error_message = Column(Text)
    started_at = Column(DateTime, default=func.now(), nullable=False)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    workflow = relationship("Workflow")
    step_executions = relationship(
        "WorkflowStepExecution",
        back_populates="execution",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="WorkflowStepExecution.step_order"
    )

    def to_dict(self, include_steps: bool = True) -> dict:
        data = {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "user_id": self.user_id,
            "status": self.status,
            "context": self.context if self.context else {},
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_steps and self.step_executions:
            data["step_executions"] = [se.to_dict() for se in self.step_executions]
        return data


class WorkflowStepExecution(Base):
    """Model for tracking individual step executions within a workflow run."""

    __tablename__ = "workflow_step_executions"
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    step_order = Column(Integer, nullable=False)
    operation_name = Column(String(255), nullable=False)
    status = Column(String(50), default="pending", nullable=False)  # pending, running, completed, failed, skipped
    input_data = Column(JSONB, default=dict)
    output_data = Column(JSONB, default=dict)
    error_message = Column(Text)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    execution = relationship("WorkflowExecution", back_populates="step_executions")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "execution_id": self.execution_id,
            "step_order": self.step_order,
            "operation_name": self.operation_name,
            "status": self.status,
            "input_data": self.input_data if self.input_data else {},
            "output_data": self.output_data if self.output_data else {},
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class UseCase(Base):
    """Model for use cases as first-class entities."""

    __tablename__ = "use_cases"
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(100), index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    workflows = relationship(
        "Workflow",
        secondary="use_case_workflows",
        lazy="selectin"
    )

    def to_dict(self, include_workflows: bool = True) -> dict:
        data = {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "category": self.category,
            "is_active": self.is_active,
            "workflows_count": len(self.workflows) if self.workflows else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_workflows and self.workflows:
            data["workflows"] = [
                {"id": w.id, "name": w.name, "display_name": w.display_name}
                for w in self.workflows
            ]
        return data


class UseCaseWorkflow(Base):
    """Association table for use cases to workflows (M:M)."""

    __tablename__ = "use_case_workflows"
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True, index=True)
    use_case_id = Column(Integer, ForeignKey("use_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("use_case_id", "workflow_id", name="uq_use_case_workflow"),
    )
