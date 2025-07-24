import re
from typing import Dict, List

from pydantic import BaseModel, Field, field_validator


class MapOpConfig(BaseModel):
    """
    Configuration for a Map operator in a data processing chain.

    Attributes:
        name (str): The name of the Map operator.
        prompt (str): Jinja prompt template for the inserted Map operator. Must refer to the input document keys as {{ input.key }}.
        output_keys (List[str]): The keys of the output of the Map operator, to be referenced in the downstream operator's prompt.
        model (str): The model to use for the Map operator.
    """

    name: str = Field(..., description="The name of the Map operator")
    prompt: str = Field(
        ...,
        description="Jinja prompt template for the inserted Map operator. Must refer to the input document keys as {{ input.key }}.",
    )
    output_keys: List[str] = Field(
        ...,
        description="The keys of the output of the Map operator, to be referenced in the downstream operator's prompt. Can be a single key or a list of keys. Can be new keys or existing keys from the map operator we are rewriting.",
    )
    model: str = Field(
        default="gpt-4o-mini", description="The model to use for the Map operator."
    )

    @classmethod
    def validate_prompt_contains_input_key(cls, value: str) -> str:
        """
        Validator to ensure the prompt contains at least one {{ input.key }} reference.

        Args:
            value (str): The prompt string.

        Returns:
            str: The validated prompt string.

        Raises:
            ValueError: If no {{ input.key }} pattern is found in the prompt.
        """
        # Matches {{ input.key }} for any key (non-whitespace, non-})
        if not re.search(r"\{\{\s*input\.[^}\s]+\s*\}\}", value):
            raise ValueError(
                "The prompt must contain at least one '{{ input.key }}' reference."
            )
        return value

    @field_validator("prompt")
    @classmethod
    def check_prompt(cls, v: str) -> str:
        return cls.validate_prompt_contains_input_key(v)


class ChainingInstantiateSchema(BaseModel):
    """
    Schema for chaining multiple Map operators in a data processing pipeline.

    Validates:
    - For each required input key, at least one MapOpConfig prompt must reference {{ input.key }}.
    - The output_keys of the final MapOpConfig must match the expected output_keys.
    """

    new_ops: List[MapOpConfig] = Field(
        ..., description="The new Map operators to insert in the chain."
    )

    @classmethod
    def validate_chain(
        cls,
        new_ops: List[MapOpConfig],
        required_input_keys: List[str],
        expected_output_keys: List[str],
    ) -> None:
        """
        Validates that for each required input key, at least one prompt in new_ops contains {{ input.key }},
        and that the final op's output_keys match expected_output_keys.

        Args:
            new_ops (List[MapOpConfig]): The list of MapOpConfig objects.
            required_input_keys (List[str]): The list of input keys that must be referenced in prompts.
            expected_output_keys (List[str]): The expected output keys for the final op.

        Raises:
            ValueError: If any required input key is not referenced in any prompt,
                        or if the final op's output_keys do not match expected_output_keys.
        """

        # Check each required input key is referenced in at least one prompt
        for key in required_input_keys:
            pattern = r"\{\{\s*input\." + re.escape(key) + r"\s*\}\}"
            if not any(re.search(pattern, op.prompt) for op in new_ops):
                raise ValueError(
                    f"Input key '{key}' must be referenced as '{{{{ input.{key} }}}}' in at least one prompt."
                )

        # Check that the final op's output_keys match expected_output_keys (order-insensitive)
        final_output_keys = list(new_ops[-1].output_keys) if new_ops else []
        if set(final_output_keys) != set(expected_output_keys):
            raise ValueError(
                f"The output_keys of the final op ({final_output_keys}) do not match the expected output_keys ({expected_output_keys})."
            )


class GleaningInstantiateSchema(BaseModel):
    """
    Schema for gleaning operations in a data processing pipeline.
    """

    validation_prompt: str = Field(
        ...,
        description="The prompt to evaluate and improve the output of the upstream operator.",
    )
    num_rounds: int = Field(
        ..., description="The maximum number of refinement iterations."
    )
    model: str = Field(default="gpt-4o-mini", description="The LLM model to use.")


class ChangeModelInstantiateSchema(BaseModel):
    """
    Schema for changing model choice in a data processing pipeline.
    """

    model: str = Field(default="gpt-4o-mini", description="The new LLM model to use.")

    @classmethod
    def validate_model_in_list(cls, model: str, list_of_model: List[str]) -> None:
        """
        Validates that the model is in the allowed list_of_model.

        Args:
            model (str): The model name to check.

        Raises:
            ValueError: If the model is not in the allowed list.
        """

        if model not in list_of_model:
            raise ValueError(
                f"Model '{model}' is not in the allowed list: {list_of_model}"
            )


class DocSummarizationInstantiateSchema(BaseModel):
    """
    Schema for document summarization operations in a data processing pipeline.
    """

    name: str = Field(..., description="The name of the Map summarization operator")
    document_key: str = Field(
        ...,
        description="The key in the input document that contains long content to be summarized",
    )
    prompt: str = Field(
        ...,
        description="Jinja prompt template for summarizing the document. Must reference {{ input.<document_key> }} and preserve information needed by downstream operators.",
    )
    model: str = Field(
        default="gpt-4o-mini", description="The model to use for summarization."
    )

    @field_validator("prompt")
    @classmethod
    def check_prompt_references_document_key(cls, v: str, info) -> str:
        # First check that it contains at least one input reference
        MapOpConfig.validate_prompt_contains_input_key(v)

        # Then check that it specifically references the document_key
        if hasattr(info, "data") and "document_key" in info.data:
            document_key = info.data["document_key"]
            pattern = r"\{\{\s*input\." + re.escape(document_key) + r"\s*\}\}"
            if not re.search(pattern, v):
                raise ValueError(
                    f"The prompt must reference the document_key as '{{{{ input.{document_key} }}}}'"
                )

        return v


class SubtaskConfig(BaseModel):
    """
    Configuration for a single subtask in the parallel map phase.
    """

    name: str = Field(..., description="The name of this subtask")
    prompt: str = Field(
        ...,
        description="Jinja template for this subtask. MUST use {{ input.ORIGINAL_KEY }} to reference the same input key as the original map operation. Example: 'Extract basic info from {{ input.document }}'",
    )
    output_keys: List[str] = Field(
        ..., description="The output keys this subtask generates"
    )

    @field_validator("prompt")
    @classmethod
    def check_prompt(cls, v: str) -> str:
        return MapOpConfig.validate_prompt_contains_input_key(v)


class IsolatingSubtasksInstantiateSchema(BaseModel):
    """
    Schema for isolating subtasks operations in a data processing pipeline.
    Rewrites a Map into Parallel Map -> Map pattern for better subtask isolation.
    """

    subtasks: List[SubtaskConfig] = Field(
        ..., description="List of subtasks for the parallel map"
    )
    aggregation_prompt: str = Field(
        default="",
        description="Jinja template to combine all subtask outputs into final result. MUST reference subtask outputs as {{ input.subtask_1_output }}, {{ input.subtask_2_output }}, etc. If empty, no aggregation step will be created. Example: 'Combine the basic info {{ input.subtask_1_output }} with details {{ input.subtask_2_output }}'",
    )

    @field_validator("aggregation_prompt")
    @classmethod
    def check_aggregation_prompt(cls, v: str) -> str:
        # Skip validation if empty (no aggregation needed)
        if not v.strip():
            return v
        return MapOpConfig.validate_prompt_contains_input_key(v)

    def validate_subtasks_coverage(self, original_output_keys: List[str]) -> None:
        """
        Validates that subtasks collectively cover all original output keys.
        """
        subtask_keys = set()
        for subtask in self.subtasks:
            subtask_keys.update(subtask.output_keys)

        original_keys_set = set(original_output_keys)
        if subtask_keys != original_keys_set:
            missing = original_keys_set - subtask_keys
            extra = subtask_keys - original_keys_set
            error_parts = []
            if missing:
                error_parts.append(f"Missing keys: {list(missing)}")
            if extra:
                error_parts.append(f"Extra keys: {list(extra)}")
            raise ValueError(
                f"Subtasks must cover exactly the original output keys. {'; '.join(error_parts)}"
            )

    def validate_aggregation_references_all_subtasks(self) -> None:
        """
        Validates that the aggregation prompt references outputs from all subtasks.
        Uses the actual output keys generated by the LLM for each subtask.
        Only validates if aggregation_prompt is not empty.
        """
        if not self.aggregation_prompt.strip():
            return  # Skip validation if no aggregation prompt

        missing_references = []
        for i, subtask in enumerate(self.subtasks):
            for output_key in subtask.output_keys:
                pattern = r"\{\{\s*input\." + re.escape(output_key) + r"\s*\}\}"
                if not re.search(pattern, self.aggregation_prompt):
                    missing_references.append(output_key)

        if missing_references:
            raise ValueError(
                f"Aggregation prompt must reference all subtask output keys. "
                f"Missing references: {missing_references}. "
                f"Expected patterns like: {{{{ input.{missing_references[0]} }}}}"
            )


class DocCompressionInstantiateSchema(BaseModel):
    """
    Schema for document compression operations in a data processing pipeline.
    Inserts an Extract operator before the target operation to compress long documents.
    """

    name: str = Field(..., description="The name of the Extract compression operator")
    document_key: str = Field(
        ...,
        description="The key in the input document that contains long content to be compressed",
    )
    prompt: str = Field(
        ...,
        description="Plain text instructions for what to extract from the document. NOT a Jinja template - the Extract operator will automatically assemble the document content.",
    )
    model: str = Field(
        default="gpt-4o-mini", description="The model to use for extraction."
    )


class DeterministicDocCompressionInstantiateSchema(BaseModel):
    """
    Schema for deterministic document compression operations in a data processing pipeline.
    Inserts a Code Map operator before the target operation to compress long documents using deterministic logic.
    """

    name: str = Field(..., description="The name of the Code Map compression operator")
    code: str = Field(
        ...,
        description="Python code defining a 'code_map' function that takes input_doc and returns a dictionary with compressed document field(s). Must include all necessary imports within the function.",
    )

    @field_validator("code")
    @classmethod
    def check_code_has_function(cls, v: str) -> str:
        if "def code_map(" not in v:
            raise ValueError(
                "Code must define a function named 'code_map' that takes input_doc as parameter"
            )
        if "return {" not in v and "return dict(" not in v:
            raise ValueError("Code must return a dictionary")
        return v

    def validate_code_returns_target_keys(self, target_ops_configs: List[Dict]) -> None:
        """
        Validates that the code returns dictionary keys that match document fields referenced in target operations.
        """
        import re

        # Extract all {{ input.key }} references from target operation prompts
        referenced_keys = set()
        for op_config in target_ops_configs:
            prompt = op_config.get("prompt", "")
            # Find all {{ input.key }} patterns
            matches = re.findall(r"\{\{\s*input\.([^}\s]+)\s*\}\}", prompt)
            referenced_keys.update(matches)

        if not referenced_keys:
            raise ValueError("No input document keys found in target operation prompts")

        # Check if the code appears to return the referenced keys
        # This is a basic check - we look for the keys in return statements
        for key in referenced_keys:
            if f"'{key}'" not in self.code and f'"{key}"' not in self.code:
                raise ValueError(
                    f"Code must return dictionary key '{key}' which is referenced in target operation prompts as '{{{{ input.{key} }}}}'"
                )

    def validate_against_target_ops(self, target_ops_configs: List[Dict]) -> None:
        """
        Validates that the configuration is appropriate for the target operations.
        """
        self.validate_code_returns_target_keys(target_ops_configs)


class OperatorFusionInstantiateSchema(BaseModel):
    """Schema for fusing two sequential operations."""

    fused_prompt: str = Field(
        ..., description="Combined prompt that performs both operations' tasks"
    )
    model: str = Field(
        default="gpt-4o-mini", description="Model to use for the fused operation"
    )
