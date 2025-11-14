"""Tool wrappers used by the ReWOO agent worker."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.preconditions import preconditions_client
from services.conditions_ai import conditions_ai_client
from utils.transformers import (
    transform_preconditions_to_conditions_ai,
    transform_metadata_to_conditions_ai
)


class ConditionsAgentTools:
    """Tools that the ReWOO worker can execute."""

    def __init__(self, default_documents: Optional[List[str]] = None):
        self.default_documents = default_documents or []

    async def call_preconditions_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Call the PreConditions LangGraph deployment."""
        metadata = payload.get("metadata") or payload
        return await preconditions_client.predict_conditions(metadata)

    async def call_conditions_ai_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call the Conditions AI workflow.

        The payload can contain:
        - `transformed_input`: Already formatted for the DAG (ready to use)
        - `preconditions_output`: PreConditions API output to be transformed
        - `metadata`: Raw conditions to be transformed (validation-only scenarios)
        """
        # Option 1: Already transformed input
        transformed_input = payload.get("transformed_input")
        if transformed_input:
            return await conditions_ai_client.evaluate(transformed_input)

        # Option 2: Transform from preconditions output
        preconditions_output = payload.get("preconditions_output")
        if preconditions_output:
            documents = payload.get("documents") or self.default_documents
            if not documents:
                raise ValueError("call_conditions_ai_api requires at least one document path.")

            primary_doc = documents[0]
            transformed = transform_preconditions_to_conditions_ai(
                cloud_output=preconditions_output,
                s3_pdf_path=primary_doc,
            )
            return await conditions_ai_client.evaluate(transformed)

        # Option 3: Transform from raw metadata (validation-only scenario)
        metadata = payload.get("metadata")
        if metadata:
            documents = payload.get("documents") or self.default_documents
            if not documents:
                raise ValueError("call_conditions_ai_api requires at least one document path.")
            
            output_destination = payload.get("output_destination")
            transformed = transform_metadata_to_conditions_ai(
                metadata=metadata,
                s3_pdf_paths=documents,
                output_destination=output_destination
            )
            return await conditions_ai_client.evaluate(transformed)

        # No valid input provided
        raise ValueError(
            "call_conditions_ai_api requires one of: "
            "transformed_input, preconditions_output, or metadata"
        )

    async def retrieve_s3_document(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Placeholder S3 retrieval tool.

        The initial version does not fetch remote content to keep the build focused.
        Instead, it echoes the requested path so future iterations can plug in the
        actual S3 retrieval logic.
        """
        path = payload.get("s3_path") or payload.get("path")
        return {
            "path": path,
            "status": "not_implemented",
            "message": "S3 retrieval placeholder. Implement as needed.",
        }

    async def query_database(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Placeholder database query tool."""
        return {
            "query": payload,
            "status": "not_implemented",
            "message": "Database query placeholder. Implement as needed.",
        }


