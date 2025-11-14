"""Transformation utilities for converting between API formats."""
from typing import Dict, Any, List, Optional
from uuid import uuid4
from datetime import datetime

from utils.logging_config import get_logger

logger = get_logger(__name__)


def transform_preconditions_to_conditions_ai(
    cloud_output: Dict[str, Any],
    s3_pdf_path: str
) -> Dict[str, Any]:
    """
    Transform PreConditions output to Conditions AI (Airflow v5) input format.
    
    This function bridges the PreConditions API output with the Airflow v5
    check_condition_v5 DAG input format.
    
    Args:
        cloud_output: Output from PreConditions API containing:
            - final_results.top_n: Scored and prioritized deficiencies (PREFERRED)
            - deficient_conditions: Raw deficient conditions (fallback)
            - compartments: Categories of conditions
        s3_pdf_path: S3 path to the uploaded document (bucket + key format or full path)
    
    Returns:
        Conditions AI input in Airflow v5 format:
        {
            "conf": {
                "conditions": [...],
                "s3_pdf_paths": [...],
                "output_destination": "..."
            }
        }
    """
    logger.info("Transforming PreConditions output to Conditions AI input format")
    
    # Extract compartments from PreConditions output and combine into single Category string
    compartments = cloud_output.get('compartments', [])
    combined_category = "; ".join(compartments) if compartments else "General"
    logger.info(f"Using combined category: {combined_category}")
    
    # Extract deficient conditions from PreConditions output
    # Prefer final_results.top_n (has scoring and prioritization)
    # Fall back to deficient_conditions for backwards compatibility
    final_results = cloud_output.get('final_results', {})
    top_n_conditions = final_results.get('top_n', [])
    
    if top_n_conditions:
        logger.info(f"Using final_results.top_n with {len(top_n_conditions)} scored deficiencies")
        deficient_conditions = top_n_conditions
    else:
        deficient_conditions = cloud_output.get('deficient_conditions', [])
        logger.info(f"Using deficient_conditions with {len(deficient_conditions)} conditions (fallback)")
    
    # Transform each condition to Airflow format
    conditions = []
    for idx, cond in enumerate(deficient_conditions, 1):
        # Extract condition details
        # For top_n format: use condition_id and actionable_instruction directly
        # (they're at the top level of each item in top_n)
        condition_id = cond.get('condition_id', f'cond_{idx}')
        actionable_instruction = cond.get('actionable_instruction', '')
        
        # If actionable_instruction not at top level, check original_deficiency (fallback)
        if not actionable_instruction and 'original_deficiency' in cond:
            original = cond['original_deficiency']
            actionable_instruction = original.get('actionable_instruction', '')
        
        # For raw deficient_conditions format (fallback)
        if not actionable_instruction:
            actionable_instruction = cond.get('condition_name', condition_id)
        
        airflow_condition = {
            "condition": {
                "id": idx,  # Sequential ID for Airflow
                "name": condition_id,  # condition_id from PreConditions
                "data": {
                    "Title": condition_id,  # Same as name
                    "Category": combined_category,  # All compartments combined
                    "Description": actionable_instruction  # Actionable instruction
                }
            }
        }
        conditions.append(airflow_condition)
    
    # Parse S3 path
    # Handle both formats: "s3://bucket/key" or just "bucket/key"
    if s3_pdf_path.startswith('s3://'):
        # Remove s3:// prefix
        s3_path_parts = s3_pdf_path[5:].split('/', 1)
        if len(s3_path_parts) == 2:
            bucket, key = s3_path_parts
        else:
            raise ValueError(f"Invalid S3 path format: {s3_pdf_path}")
    elif '/' in s3_pdf_path:
        # Assume format is bucket/key
        s3_path_parts = s3_pdf_path.split('/', 1)
        bucket, key = s3_path_parts
    else:
        raise ValueError(f"Invalid S3 path format: {s3_pdf_path}. Expected 's3://bucket/key' or 'bucket/key'")
    
    s3_pdf_paths = [{
        "bucket": bucket,
        "key": key
    }]
    
    # Generate unique output destination
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_destination = f"{bucket}/conditions_output/result_{timestamp}_{uuid4().hex[:8]}.json"
    
    # Build final Airflow input
    airflow_input = {
        "conf": {
            "conditions": conditions,
            "s3_pdf_paths": s3_pdf_paths,
            "output_destination": output_destination
        }
    }
    
    logger.info(
        f"Transformation complete: {len(conditions)} conditions, "
        f"S3 path: {bucket}/{key}, "
        f"Output: {output_destination}"
    )
    
    return airflow_input


def transform_metadata_to_conditions_ai(
    metadata: Dict[str, Any],
    s3_pdf_paths: List[str],
    output_destination: Optional[str] = None
) -> Dict[str, Any]:
    """
    Transform raw metadata conditions directly to Conditions AI format.
    
    This is used for validation-only scenarios where conditions are provided
    directly without calling the PreConditions API first.
    
    Args:
        metadata: Contains a 'conditions' list with condition details
        s3_pdf_paths: List of S3 paths to documents (e.g., ["s3://bucket/key.pdf"])
        output_destination: Optional S3 output path, will be auto-generated if not provided
    
    Returns:
        Conditions AI input in Airflow v5 format
    """
    logger.info("Transforming metadata conditions to Conditions AI input format")
    
    # Extract conditions from metadata
    raw_conditions = metadata.get('conditions', [])
    if not raw_conditions:
        raise ValueError("metadata must contain a 'conditions' list")
    
    logger.info(f"Found {len(raw_conditions)} conditions in metadata")
    
    # Transform each condition to Airflow format
    conditions = []
    for idx, cond in enumerate(raw_conditions, 1):
        condition_name = cond.get('condition_name', cond.get('name', ''))
        description = cond.get('description', condition_name)
        category = cond.get('category', 'General')
        
        airflow_condition = {
            "condition": {
                "id": idx,
                "name": condition_name,
                "data": {
                    "Title": condition_name,
                    "Category": category,
                    "Description": description
                }
            }
        }
        conditions.append(airflow_condition)
    
    # Parse S3 paths to bucket/key format
    parsed_paths = []
    for s3_path in s3_pdf_paths:
        # Handle both formats: "s3://bucket/key" or just "bucket/key"
        if s3_path.startswith('s3://'):
            s3_path = s3_path[5:]  # Remove s3:// prefix
        
        if '/' in s3_path:
            parts = s3_path.split('/', 1)
            bucket, key = parts
            parsed_paths.append({
                "bucket": bucket,
                "key": key
            })
        else:
            raise ValueError(f"Invalid S3 path format: {s3_path}")
    
    # Generate output destination if not provided
    if not output_destination:
        first_bucket = parsed_paths[0]["bucket"]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_destination = f"{first_bucket}/conditions_output/result_{timestamp}_{uuid4().hex[:8]}.json"
    
    # Build final Airflow input
    airflow_input = {
        "conf": {
            "conditions": conditions,
            "s3_pdf_paths": parsed_paths,
            "output_destination": output_destination
        }
    }
    
    logger.info(
        f"Transformation complete: {len(conditions)} conditions, "
        f"{len(parsed_paths)} documents, "
        f"Output: {output_destination}"
    )
    
    return airflow_input


def extract_fulfilled_and_not_fulfilled(
    conditions_s3_output: Dict[str, Any]
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Extract and separate fulfilled vs not fulfilled conditions from Conditions AI output.
    
    Args:
        conditions_s3_output: Output from Conditions AI (from S3) containing:
            - processed_conditions: List of condition evaluation results
    
    Returns:
        Tuple of (fulfilled_conditions, not_fulfilled_conditions)
    """
    logger.info("Classifying conditions as fulfilled vs not fulfilled")
    
    processed_conditions = conditions_s3_output.get('processed_conditions', [])
    
    fulfilled = []
    not_fulfilled = []
    
    for cond in processed_conditions:
        document_status = cond.get('document_status', '').lower()
        
        if document_status == 'fulfilled':
            fulfilled.append(cond)
        elif document_status in ['not fulfilled', 'not_fulfilled', 'unfulfilled']:
            not_fulfilled.append(cond)
        else:
            # Uncertain or other status - treat as not fulfilled (needs review)
            not_fulfilled.append(cond)
    
    logger.info(
        f"Classification complete: {len(fulfilled)} fulfilled, "
        f"{len(not_fulfilled)} not fulfilled"
    )
    
    return fulfilled, not_fulfilled


def format_condition_for_frontend(
    condition: Dict[str, Any],
    is_fulfilled: bool
) -> Dict[str, Any]:
    """
    Format a condition evaluation for frontend display.
    
    Args:
        condition: Condition from Conditions AI output
        is_fulfilled: Whether the condition was fulfilled
    
    Returns:
        Formatted condition with UI-friendly fields
    """
    analysis_metadata = condition.get('analysis_metadata', {})
    confidence = analysis_metadata.get('result_confidence', 0.0)
    
    # Determine confidence color
    if confidence >= 0.8:
        confidence_color = 'green'
    elif confidence >= 0.5:
        confidence_color = 'yellow'
    else:
        confidence_color = 'red'
    
    return {
        'condition_id': condition.get('condition_id'),
        'title': condition.get('title'),
        'description': condition.get('description'),
        'category': condition.get('category'),
        'status': 'fulfilled' if is_fulfilled else 'not_fulfilled',
        'document_status': condition.get('document_status'),
        'confidence': confidence,
        'confidence_color': confidence_color,
        'ai_reasoning': condition.get('document_analysis', ''),
        'ai_thinking': condition.get('document_analysis_thinking', ''),
        'citations': {
            'document_id': condition.get('result_document_id'),
            'is_relevant': condition.get('is_relevant')
        },
        'model_used': analysis_metadata.get('model_used'),
        'tokens_used': analysis_metadata.get('tokens_used', {}),
        'cost_usd': analysis_metadata.get('cost_usd', 0.0),
        'latency_ms': analysis_metadata.get('latency_ms', 0)
    }

