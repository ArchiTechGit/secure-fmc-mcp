"""Service for managing API guidance, workflows, and system prompts.

This service provides methods for managing the API Guidance System, which enhances
Claude's ability to work with Cisco FMC APIs through customizable guidance,
workflows, tool descriptions, and system prompts.
"""

import logging
from typing import Dict, List, Optional

from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from src.config.database import get_db
from src.models.guidance import (
    APIGuidance,
    CategoryGuidance,
    Workflow,
    WorkflowStep,
    ToolDescriptionOverride,
    SystemPromptSection,
)

logger = logging.getLogger(__name__)


class GuidanceService:
    """Service for managing API guidance and system prompts."""

    def __init__(self):
        """Initialize guidance service."""
        self.db = get_db()

    # ==================== API Guidance Methods ====================

    async def get_api_guidance(self, api_name: str) -> Optional[APIGuidance]:
        """Get API guidance by API name.

        Args:
            api_name: Name of the API (e.g., 'manage', 'analyze')

        Returns:
            APIGuidance instance or None if not found
        """
        async with self.db.session() as session:
            result = await session.execute(
                select(APIGuidance)
                .where(APIGuidance.api_name == api_name)
            )
            return result.scalar_one_or_none()

    async def list_api_guidance(self, active_only: bool = True) -> List[APIGuidance]:
        """List all API guidance entries.

        Args:
            active_only: If True, only return active guidance

        Returns:
            List of APIGuidance instances
        """
        async with self.db.session() as session:
            query = select(APIGuidance)

            if active_only:
                query = query.where(APIGuidance.is_active == True)

            query = query.order_by(APIGuidance.priority, APIGuidance.api_name)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def upsert_api_guidance(self, api_name: str, **kwargs) -> APIGuidance:
        """Create or update API guidance.

        Args:
            api_name: Name of the API
            **kwargs: Fields to set (display_name, description, general_guidance, etc.)

        Returns:
            Created or updated APIGuidance instance
        """
        async with self.db.session() as session:
            # Check if guidance exists
            result = await session.execute(
                select(APIGuidance).where(APIGuidance.api_name == api_name)
            )
            guidance = result.scalar_one_or_none()

            if guidance:
                # Update existing
                for key, value in kwargs.items():
                    if hasattr(guidance, key):
                        setattr(guidance, key, value)
                logger.info(f"Updated API guidance: {api_name}")
            else:
                # Create new
                guidance = APIGuidance(api_name=api_name, **kwargs)
                session.add(guidance)
                logger.info(f"Created API guidance: {api_name}")

            await session.commit()
            await session.refresh(guidance)
            return guidance

    async def delete_api_guidance(self, api_name: str) -> bool:
        """Delete API guidance.

        Args:
            api_name: Name of the API

        Returns:
            True if deleted, False if not found
        """
        async with self.db.session() as session:
            result = await session.execute(
                delete(APIGuidance).where(APIGuidance.api_name == api_name)
            )
            await session.commit()

            if result.rowcount > 0:
                logger.info(f"Deleted API guidance: {api_name}")
                return True
            return False

    # ==================== Category Guidance Methods ====================

    async def get_category_guidance(
        self, api_name: str, category_name: str
    ) -> Optional[CategoryGuidance]:
        """Get category guidance by API and category name.

        Args:
            api_name: Name of the API
            category_name: Name of the category

        Returns:
            CategoryGuidance instance or None if not found
        """
        async with self.db.session() as session:
            result = await session.execute(
                select(CategoryGuidance)
                .join(APIGuidance)
                .where(
                    APIGuidance.api_name == api_name,
                    CategoryGuidance.category_name == category_name,
                )
            )
            return result.scalar_one_or_none()

    async def list_category_guidance(
        self, api_name: Optional[str] = None, active_only: bool = True
    ) -> List[CategoryGuidance]:
        """List category guidance entries.

        Args:
            api_name: Filter by API name (optional)
            active_only: If True, only return active guidance

        Returns:
            List of CategoryGuidance instances
        """
        async with self.db.session() as session:
            query = select(CategoryGuidance)

            if api_name:
                query = query.where(CategoryGuidance.api_name == api_name)

            if active_only:
                query = query.where(CategoryGuidance.is_active == True)

            query = query.order_by(CategoryGuidance.category_name)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def upsert_category_guidance(
        self, api_name: str, category_name: str, **kwargs
    ) -> CategoryGuidance:
        """Create or update category guidance.

        Args:
            api_name: Name of the API
            category_name: Name of the category
            **kwargs: Fields to set (display_name, description, usage_tips, etc.)

        Returns:
            Created or updated CategoryGuidance instance

        Raises:
            ValueError: If API guidance doesn't exist
        """
        async with self.db.session() as session:
            # Get API guidance ID
            api_result = await session.execute(
                select(APIGuidance).where(APIGuidance.api_name == api_name)
            )
            api_guidance = api_result.scalar_one_or_none()
            if not api_guidance:
                raise ValueError(f"API guidance '{api_name}' not found. Create it first.")

            # Check if category guidance exists
            result = await session.execute(
                select(CategoryGuidance).where(
                    CategoryGuidance.api_guidance_id == api_guidance.id,
                    CategoryGuidance.category_name == category_name,
                )
            )
            guidance = result.scalar_one_or_none()

            if guidance:
                # Update existing
                for key, value in kwargs.items():
                    if hasattr(guidance, key):
                        setattr(guidance, key, value)
                logger.info(f"Updated category guidance: {api_name}.{category_name}")
            else:
                # Create new
                guidance = CategoryGuidance(
                    api_guidance_id=api_guidance.id,
                    category_name=category_name,
                    **kwargs,
                )
                session.add(guidance)
                logger.info(f"Created category guidance: {api_name}.{category_name}")

            await session.commit()
            await session.refresh(guidance)
            return guidance

    async def delete_category_guidance(self, id: int) -> bool:
        """Delete category guidance by ID.

        Args:
            id: Category guidance ID

        Returns:
            True if deleted, False if not found
        """
        async with self.db.session() as session:
            result = await session.execute(
                delete(CategoryGuidance).where(CategoryGuidance.id == id)
            )
            await session.commit()

            if result.rowcount > 0:
                logger.info(f"Deleted category guidance ID: {id}")
                return True
            return False

    # ==================== Workflow Methods ====================

    async def create_workflow(self, name: str, display_name: str, **kwargs) -> Workflow:
        """Create a new workflow.

        Args:
            name: Unique workflow identifier
            display_name: Human-readable name
            **kwargs: Additional fields (description, use_case, prerequisites, etc.)

        Returns:
            Created Workflow instance

        Raises:
            ValueError: If workflow with name already exists
        """
        async with self.db.session() as session:
            # Check if workflow exists
            result = await session.execute(
                select(Workflow).where(Workflow.name == name)
            )
            if result.scalar_one_or_none():
                raise ValueError(f"Workflow '{name}' already exists")

            workflow = Workflow(name=name, display_name=display_name, **kwargs)
            session.add(workflow)
            await session.commit()
            await session.refresh(workflow)

            logger.info(f"Created workflow: {name}")
            return workflow

    async def get_workflow(self, workflow_id: int) -> Optional[Workflow]:
        """Get workflow by ID with steps loaded.

        Args:
            workflow_id: Workflow ID

        Returns:
            Workflow instance or None if not found
        """
        async with self.db.session() as session:
            result = await session.execute(
                select(Workflow)
                .options(selectinload(Workflow.steps))
                .where(Workflow.id == workflow_id)
            )
            return result.scalar_one_or_none()

    async def list_workflows(
        self, active_only: bool = True, use_case_tag: Optional[str] = None
    ) -> List[Workflow]:
        """List workflows.

        Args:
            active_only: If True, only return active workflows
            use_case_tag: Filter by use case tag (optional)

        Returns:
            List of Workflow instances
        """
        async with self.db.session() as session:
            query = select(Workflow).options(selectinload(Workflow.steps))

            if active_only:
                query = query.where(Workflow.is_active == True)

            if use_case_tag:
                # Filter by JSON array contains
                query = query.where(Workflow.use_case_tags.contains([use_case_tag]))

            query = query.order_by(Workflow.display_name)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def update_workflow(self, workflow_id: int, **kwargs) -> Optional[Workflow]:
        """Update workflow properties.

        Args:
            workflow_id: Workflow ID
            **kwargs: Fields to update

        Returns:
            Updated Workflow instance or None if not found
        """
        async with self.db.session() as session:
            result = await session.execute(
                select(Workflow).where(Workflow.id == workflow_id)
            )
            workflow = result.scalar_one_or_none()

            if not workflow:
                return None

            for key, value in kwargs.items():
                if hasattr(workflow, key) and key not in ("id", "name", "created_at"):
                    setattr(workflow, key, value)

            await session.commit()
            await session.refresh(workflow)

            logger.info(f"Updated workflow: {workflow.name}")
            return workflow

    async def delete_workflow(self, workflow_id: int) -> bool:
        """Delete workflow and its steps.

        Args:
            workflow_id: Workflow ID

        Returns:
            True if deleted, False if not found
        """
        async with self.db.session() as session:
            result = await session.execute(
                delete(Workflow).where(Workflow.id == workflow_id)
            )
            await session.commit()

            if result.rowcount > 0:
                logger.info(f"Deleted workflow ID: {workflow_id}")
                return True
            return False

    async def set_workflow_steps(
        self, workflow_id: int, steps: List[Dict]
    ) -> Optional[Workflow]:
        """Set workflow steps (replaces existing steps).

        Args:
            workflow_id: Workflow ID
            steps: List of step dictionaries with keys:
                - step_order (int)
                - step_name (str)
                - description (str)
                - operation_name (str, optional)
                - parameters (dict, optional)
                - expected_result (str, optional)
                - validation (str, optional)
                - notes (str, optional)

        Returns:
            Updated Workflow instance or None if workflow not found
        """
        async with self.db.session() as session:
            # Verify workflow exists
            result = await session.execute(
                select(Workflow).where(Workflow.id == workflow_id)
            )
            workflow = result.scalar_one_or_none()
            if not workflow:
                return None

            # Delete existing steps
            await session.execute(
                delete(WorkflowStep).where(WorkflowStep.workflow_id == workflow_id)
            )

            # Create new steps
            for step_data in steps:
                step = WorkflowStep(workflow_id=workflow_id, **step_data)
                session.add(step)

            await session.commit()

            logger.info(f"Set {len(steps)} steps for workflow ID: {workflow_id}")

            # Return workflow with steps
            return await self.get_workflow(workflow_id)

    # ==================== Tool Override Methods ====================

    async def get_tool_override(
        self, operation_name: str
    ) -> Optional[ToolDescriptionOverride]:
        """Get tool description override by operation name.

        Args:
            operation_name: Name of the operation/tool

        Returns:
            ToolDescriptionOverride instance or None if not found
        """
        async with self.db.session() as session:
            result = await session.execute(
                select(ToolDescriptionOverride).where(
                    ToolDescriptionOverride.operation_name == operation_name
                )
            )
            return result.scalar_one_or_none()

    async def get_all_tool_overrides(self) -> Dict[str, ToolDescriptionOverride]:
        """Get all active tool overrides as a dictionary.

        Returns:
            Dictionary mapping operation_name to ToolDescriptionOverride
        """
        async with self.db.session() as session:
            result = await session.execute(
                select(ToolDescriptionOverride).where(
                    ToolDescriptionOverride.is_active == True
                )
            )
            overrides = result.scalars().all()
            return {override.operation_name: override for override in overrides}

    async def list_tool_overrides(self, active_only: bool = True) -> List[ToolDescriptionOverride]:
        """List tool description overrides.

        Args:
            active_only: If True, only return active overrides

        Returns:
            List of ToolDescriptionOverride instances
        """
        async with self.db.session() as session:
            query = select(ToolDescriptionOverride)

            if active_only:
                query = query.where(ToolDescriptionOverride.is_active == True)

            query = query.order_by(ToolDescriptionOverride.operation_name)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def upsert_tool_override(
        self, operation_name: str, **kwargs
    ) -> ToolDescriptionOverride:
        """Create or update tool description override.

        Args:
            operation_name: Name of the operation/tool
            **kwargs: Fields to set (custom_description, usage_guidance, etc.)

        Returns:
            Created or updated ToolDescriptionOverride instance
        """
        async with self.db.session() as session:
            # Check if override exists
            result = await session.execute(
                select(ToolDescriptionOverride).where(
                    ToolDescriptionOverride.operation_name == operation_name
                )
            )
            override = result.scalar_one_or_none()

            if override:
                # Update existing
                for key, value in kwargs.items():
                    if hasattr(override, key):
                        setattr(override, key, value)
                logger.info(f"Updated tool override: {operation_name}")
            else:
                # Create new
                override = ToolDescriptionOverride(
                    operation_name=operation_name, **kwargs
                )
                session.add(override)
                logger.info(f"Created tool override: {operation_name}")

            await session.commit()
            await session.refresh(override)
            return override

    async def delete_tool_override(self, operation_name: str) -> bool:
        """Delete tool description override.

        Args:
            operation_name: Name of the operation/tool

        Returns:
            True if deleted, False if not found
        """
        async with self.db.session() as session:
            result = await session.execute(
                delete(ToolDescriptionOverride).where(
                    ToolDescriptionOverride.operation_name == operation_name
                )
            )
            await session.commit()

            if result.rowcount > 0:
                logger.info(f"Deleted tool override: {operation_name}")
                return True
            return False

    # ==================== System Prompt Methods ====================

    async def get_system_prompt_sections(
        self, active_only: bool = True
    ) -> List[SystemPromptSection]:
        """Get all system prompt sections ordered by section_order.

        Args:
            active_only: If True, only return active sections

        Returns:
            List of SystemPromptSection instances
        """
        async with self.db.session() as session:
            query = select(SystemPromptSection)

            if active_only:
                query = query.where(SystemPromptSection.is_active == True)

            query = query.order_by(SystemPromptSection.section_order, SystemPromptSection.section_name)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def upsert_system_prompt_section(
        self, section_name: str, **kwargs
    ) -> SystemPromptSection:
        """Create or update system prompt section.

        Args:
            section_name: Unique section identifier
            **kwargs: Fields to set (display_name, content, section_order, etc.)

        Returns:
            Created or updated SystemPromptSection instance
        """
        async with self.db.session() as session:
            # Check if section exists
            result = await session.execute(
                select(SystemPromptSection).where(
                    SystemPromptSection.section_name == section_name
                )
            )
            section = result.scalar_one_or_none()

            if section:
                # Update existing
                for key, value in kwargs.items():
                    if hasattr(section, key):
                        setattr(section, key, value)
                logger.info(f"Updated system prompt section: {section_name}")
            else:
                # Create new
                section = SystemPromptSection(section_name=section_name, **kwargs)
                session.add(section)
                logger.info(f"Created system prompt section: {section_name}")

            await session.commit()
            await session.refresh(section)
            return section

    async def delete_system_prompt_section(self, section_name: str) -> bool:
        """Delete system prompt section.

        Args:
            section_name: Section identifier

        Returns:
            True if deleted, False if not found
        """
        async with self.db.session() as session:
            result = await session.execute(
                delete(SystemPromptSection).where(
                    SystemPromptSection.section_name == section_name
                )
            )
            await session.commit()

            if result.rowcount > 0:
                logger.info(f"Deleted system prompt section: {section_name}")
                return True
            return False

    # ==================== Composite Methods ====================

    async def generate_system_prompt(self) -> str:
        """Generate complete system prompt from all active sources.

        Combines:
        - System prompt sections (ordered by section_order)
        - API guidance formatted as reference
        - Workflow summaries

        Returns:
            Complete system prompt text
        """
        prompt_parts = []

        # 1. System prompt sections
        sections = await self.get_system_prompt_sections(active_only=True)
        for section in sections:
            prompt_parts.append(f"# {section.title or section.section_name}\n\n{section.content}\n")

        # 2. API guidance
        api_guidance_list = await self.list_api_guidance(active_only=True)
        if api_guidance_list:
            prompt_parts.append("\n# API Reference and Best Practices\n")
            for api_guidance in api_guidance_list:
                prompt_parts.append(f"\n## {api_guidance.display_name}\n")
                if api_guidance.description:
                    prompt_parts.append(f"{api_guidance.description}\n")
                if api_guidance.when_to_use:
                    prompt_parts.append(f"\n**When to Use:**\n{api_guidance.when_to_use}\n")
                if api_guidance.when_not_to_use:
                    prompt_parts.append(f"\n**When NOT to Use:**\n{api_guidance.when_not_to_use}\n")

        # 3. Workflow summaries
        workflows = await self.list_workflows(active_only=True)
        if workflows:
            prompt_parts.append("\n# Available Workflows\n")
            for workflow in workflows:
                prompt_parts.append(f"\n## {workflow.display_name}\n")
                if workflow.description:
                    prompt_parts.append(f"{workflow.description}\n")
                if workflow.problem_statement:
                    prompt_parts.append(f"\n**Problem Statement:** {workflow.problem_statement}\n")
                if workflow.steps:
                    prompt_parts.append(f"\n**Steps ({len(workflow.steps)}):**\n")
                    for step in workflow.steps:
                        prompt_parts.append(f"{step.step_order}. {step.operation_name}: {step.description or ''}\n")

        logger.info("Generated system prompt with all active guidance")
        return "\n".join(prompt_parts)

    async def build_enhanced_tool_description(self, operation: Dict) -> str:
        """Build enhanced description for a tool operation.

        Checks if there's a custom override for this operation and combines it
        with the original description.

        Args:
            operation: Dictionary with operation details including 'operationId'

        Returns:
            Enhanced description string
        """
        operation_name = operation.get("operationId", "")
        original_description = operation.get("description", "")

        # Check for override
        override = await self.get_tool_override(operation_name)

        if override and override.is_active:
            parts = [override.custom_description]

            if override.usage_guidance:
                parts.append(f"\n**Usage Guidance:** {override.usage_guidance}")

            if override.warnings:
                parts.append(f"\n**Warning:** {override.warnings}")

            if override.examples:
                parts.append("\n**Examples:**")
                for example in override.examples:
                    if isinstance(example, dict):
                        parts.append(f"- {example.get('description', '')}")
                    else:
                        parts.append(f"- {example}")

            logger.debug(f"Using enhanced description for: {operation_name}")
            return "\n".join(parts)

        # No override, return original
        return original_description

    # ==================== Batch Description Generation ====================

    async def generate_descriptions_from_spec(self, api_name: str) -> Dict[str, int]:
        """Generate tool description overrides from OpenAPI spec.

        Extracts rich descriptions from the loaded OpenAPI spec including
        full description text, parameter details, and request body fields.

        Args:
            api_name: Name of the API to generate descriptions for (or 'all')

        Returns:
            Dict with counts: {"created": N, "updated": N, "skipped": N}
        """
        from src.core.api_loader import APILoader
        from src.core.api_registry import APIRegistry

        loader = APILoader()
        counts = {"created": 0, "updated": 0, "skipped": 0}

        # Determine which APIs to process
        if api_name == "all":
            apis = APIRegistry.get_enabled_apis()
        else:
            api_def = APIRegistry.get_api(api_name)
            if not api_def:
                raise ValueError(f"Unknown API: {api_name}")
            apis = [api_def]

        for api_def in apis:
            spec = loader.load_openapi_spec(api_def.spec_file)
            if not spec:
                continue

            paths = spec.get("paths", {})
            for path, methods in paths.items():
                for method, operation in methods.items():
                    if method in ("parameters", "summary", "description"):
                        continue

                    operation_id = operation.get("operationId")
                    if not operation_id:
                        continue

                    tool_name = f"{api_def.name}_{operation_id}"
                    summary = operation.get("summary", "")
                    description = operation.get("description", "")

                    # Build rich description from spec
                    parts = []
                    if description:
                        parts.append(description)
                    elif summary:
                        parts.append(summary)

                    # Add parameter details
                    params = operation.get("parameters", [])
                    if params:
                        param_details = []
                        for p in params:
                            p_name = p.get("name", "")
                            p_desc = p.get("description", "")
                            p_required = p.get("required", False)
                            req_marker = " (required)" if p_required else ""
                            if p_desc:
                                param_details.append(f"  - {p_name}{req_marker}: {p_desc}")
                            else:
                                param_details.append(f"  - {p_name}{req_marker}")
                        if param_details:
                            parts.append("Parameters:\n" + "\n".join(param_details))

                    # Add request body info
                    request_body = operation.get("requestBody", {})
                    if request_body:
                        rb_desc = request_body.get("description", "")
                        if rb_desc:
                            parts.append(f"Request Body: {rb_desc}")
                        # Try to extract schema properties
                        content = request_body.get("content", {})
                        json_content = content.get("application/json", {})
                        schema = json_content.get("schema", {})
                        properties = schema.get("properties", {})
                        if properties:
                            prop_details = []
                            required_props = schema.get("required", [])
                            for prop_name, prop_schema in list(properties.items())[:10]:
                                prop_desc = prop_schema.get("description", "")
                                req_marker = " (required)" if prop_name in required_props else ""
                                if prop_desc:
                                    prop_details.append(f"  - {prop_name}{req_marker}: {prop_desc}")
                                else:
                                    prop_details.append(f"  - {prop_name}{req_marker}")
                            if prop_details:
                                parts.append("Body Fields:\n" + "\n".join(prop_details))

                    enhanced_description = "\n\n".join(parts) if parts else None

                    if not enhanced_description:
                        counts["skipped"] += 1
                        continue

                    # Upsert the override
                    try:
                        existing = await self.get_tool_override(tool_name)
                        if existing and existing.enhanced_description:
                            counts["skipped"] += 1
                            continue

                        await self.upsert_tool_override(
                            operation_name=tool_name,
                            enhanced_description=enhanced_description,
                        )
                        if existing:
                            counts["updated"] += 1
                        else:
                            counts["created"] += 1
                    except Exception as e:
                        logger.warning(f"Failed to upsert override for {tool_name}: {e}")
                        counts["skipped"] += 1

        logger.info(f"Generated descriptions: {counts}")
        return counts

    # ==================== Workflow Validation ====================

    async def validate_workflow(self, workflow_id: int) -> Dict[str, any]:
        """Validate a workflow definition.

        Checks:
        - All operation names exist in API endpoints with correct prefix
        - Input mapping references valid earlier steps
        - Step order is sequential

        Returns:
            Dict with "valid" (bool) and "errors" (list of strings)
        """
        workflow = await self.get_workflow(workflow_id)
        if not workflow:
            return {"valid": False, "errors": ["Workflow not found"]}

        errors = []

        if not workflow.steps:
            errors.append("Workflow has no steps")
            return {"valid": False, "errors": errors}

        # Get all valid operation names from API endpoints
        from src.models.api_endpoint import APIEndpoint
        async with self.db.session() as session:
            result = await session.execute(select(APIEndpoint))
            endpoints = result.scalars().all()
            valid_ops = {f"{ep.api_name}_{ep.operation_id}" for ep in endpoints}

        step_output_keys: Dict[str, str] = {}
        prev_order = 0

        for step in workflow.steps:
            # Check step order
            if step.step_order <= prev_order and prev_order > 0:
                errors.append(f"Step {step.step_order}: order should be greater than {prev_order}")
            prev_order = step.step_order

            # Check operation exists
            if step.operation_name not in valid_ops:
                # Check if it's missing the prefix
                matching = [op for op in valid_ops if op.endswith(f"_{step.operation_name}")]
                if matching:
                    errors.append(
                        f"Step {step.step_order}: operation '{step.operation_name}' needs prefix. "
                        f"Did you mean: {', '.join(matching[:3])}?"
                    )
                else:
                    errors.append(f"Step {step.step_order}: operation '{step.operation_name}' not found")

            # Check fallback operation
            if step.fallback_operation and step.fallback_operation not in valid_ops:
                errors.append(f"Step {step.step_order}: fallback operation '{step.fallback_operation}' not found")

            # Track output keys
            if step.output_key:
                step_output_keys[f"step_{step.step_order}"] = step.output_key

            # Validate input mapping references
            if step.input_mapping:
                import re
                for param, mapping_value in step.input_mapping.items():
                    if isinstance(mapping_value, str):
                        refs = re.findall(r'\{\{(step_\d+)\.', mapping_value)
                        for ref in refs:
                            ref_order = int(ref.split("_")[1])
                            if ref_order >= step.step_order:
                                errors.append(
                                    f"Step {step.step_order}: input_mapping references "
                                    f"'{ref}' which is not an earlier step"
                                )

        return {"valid": len(errors) == 0, "errors": errors}

    # ==================== Workflow Execution Tracking ====================

    async def create_workflow_execution(
        self, workflow_id: int, user_id: Optional[int] = None, context: Optional[Dict] = None
    ) -> "WorkflowExecution":
        """Start a new workflow execution."""
        from src.models.guidance import WorkflowExecution
        async with self.db.session() as session:
            execution = WorkflowExecution(
                workflow_id=workflow_id,
                user_id=user_id,
                status="running",
                context=context or {},
            )
            session.add(execution)
            await session.commit()
            await session.refresh(execution)
            return execution

    async def get_workflow_execution(self, execution_id: int) -> Optional["WorkflowExecution"]:
        """Get workflow execution by ID."""
        from src.models.guidance import WorkflowExecution
        async with self.db.session() as session:
            result = await session.execute(
                select(WorkflowExecution)
                .options(selectinload(WorkflowExecution.step_executions))
                .where(WorkflowExecution.id == execution_id)
            )
            return result.scalar_one_or_none()

    async def list_workflow_executions(
        self, workflow_id: Optional[int] = None, limit: int = 50
    ) -> List["WorkflowExecution"]:
        """List workflow executions."""
        from src.models.guidance import WorkflowExecution
        async with self.db.session() as session:
            query = select(WorkflowExecution).options(
                selectinload(WorkflowExecution.step_executions)
            )
            if workflow_id:
                query = query.where(WorkflowExecution.workflow_id == workflow_id)
            query = query.order_by(WorkflowExecution.created_at.desc()).limit(limit)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def update_workflow_execution(
        self, execution_id: int, status: str, error_message: Optional[str] = None
    ) -> Optional["WorkflowExecution"]:
        """Update workflow execution status."""
        from src.models.guidance import WorkflowExecution
        from sqlalchemy.sql import func as sql_func
        async with self.db.session() as session:
            result = await session.execute(
                select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
            )
            execution = result.scalar_one_or_none()
            if not execution:
                return None
            execution.status = status
            if error_message:
                execution.error_message = error_message
            if status in ("completed", "failed", "cancelled"):
                from datetime import datetime
                execution.completed_at = datetime.utcnow()
            await session.commit()
            await session.refresh(execution)
            return execution

    async def create_step_execution(
        self, execution_id: int, step_order: int, operation_name: str,
        input_data: Optional[Dict] = None
    ) -> "WorkflowStepExecution":
        """Record a step execution."""
        from src.models.guidance import WorkflowStepExecution
        from datetime import datetime
        async with self.db.session() as session:
            step_exec = WorkflowStepExecution(
                execution_id=execution_id,
                step_order=step_order,
                operation_name=operation_name,
                status="running",
                input_data=input_data or {},
                started_at=datetime.utcnow(),
            )
            session.add(step_exec)
            await session.commit()
            await session.refresh(step_exec)
            return step_exec

    async def update_step_execution(
        self, step_exec_id: int, status: str,
        output_data: Optional[Dict] = None, error_message: Optional[str] = None
    ) -> Optional["WorkflowStepExecution"]:
        """Update a step execution."""
        from src.models.guidance import WorkflowStepExecution
        from datetime import datetime
        async with self.db.session() as session:
            result = await session.execute(
                select(WorkflowStepExecution).where(WorkflowStepExecution.id == step_exec_id)
            )
            step_exec = result.scalar_one_or_none()
            if not step_exec:
                return None
            step_exec.status = status
            if output_data:
                step_exec.output_data = output_data
            if error_message:
                step_exec.error_message = error_message
            if status in ("completed", "failed", "skipped"):
                step_exec.completed_at = datetime.utcnow()
            await session.commit()
            await session.refresh(step_exec)
            return step_exec

    # ==================== Use Case Methods ====================

    async def create_use_case(self, name: str, display_name: str, **kwargs) -> "UseCase":
        """Create a new use case."""
        from src.models.guidance import UseCase
        async with self.db.session() as session:
            result = await session.execute(select(UseCase).where(UseCase.name == name))
            if result.scalar_one_or_none():
                raise ValueError(f"Use case '{name}' already exists")
            use_case = UseCase(name=name, display_name=display_name, **kwargs)
            session.add(use_case)
            await session.commit()
            await session.refresh(use_case)
            return use_case

    async def get_use_case(self, use_case_id: int) -> Optional["UseCase"]:
        """Get use case by ID."""
        from src.models.guidance import UseCase
        async with self.db.session() as session:
            result = await session.execute(
                select(UseCase).where(UseCase.id == use_case_id)
            )
            return result.scalar_one_or_none()

    async def list_use_cases(self, category: Optional[str] = None, active_only: bool = True) -> List["UseCase"]:
        """List use cases."""
        from src.models.guidance import UseCase
        async with self.db.session() as session:
            query = select(UseCase)
            if active_only:
                query = query.where(UseCase.is_active == True)
            if category:
                query = query.where(UseCase.category == category)
            query = query.order_by(UseCase.display_name)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def update_use_case(self, use_case_id: int, **kwargs) -> Optional["UseCase"]:
        """Update use case."""
        from src.models.guidance import UseCase
        async with self.db.session() as session:
            result = await session.execute(
                select(UseCase).where(UseCase.id == use_case_id)
            )
            use_case = result.scalar_one_or_none()
            if not use_case:
                return None
            for k, v in kwargs.items():
                if hasattr(use_case, k) and k not in ("id", "name", "created_at"):
                    setattr(use_case, k, v)
            await session.commit()
            await session.refresh(use_case)
            return use_case

    async def delete_use_case(self, use_case_id: int) -> bool:
        """Delete use case."""
        from src.models.guidance import UseCase
        async with self.db.session() as session:
            result = await session.execute(
                delete(UseCase).where(UseCase.id == use_case_id)
            )
            await session.commit()
            return result.rowcount > 0

    async def set_use_case_workflows(self, use_case_id: int, workflow_ids: List[int]) -> Optional["UseCase"]:
        """Set workflows for a use case."""
        from src.models.guidance import UseCase, UseCaseWorkflow
        async with self.db.session() as session:
            result = await session.execute(select(UseCase).where(UseCase.id == use_case_id))
            if not result.scalar_one_or_none():
                return None
            await session.execute(
                delete(UseCaseWorkflow).where(UseCaseWorkflow.use_case_id == use_case_id)
            )
            for wf_id in workflow_ids:
                session.add(UseCaseWorkflow(use_case_id=use_case_id, workflow_id=wf_id))
            await session.commit()
        return await self.get_use_case(use_case_id)
