"""Transformation utilities for converting between API formats."""
from typing import Dict, Any, List
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
            - deficient_conditions: List of predicted deficient conditions
            - compartments: Categories of conditions
            - top_n: Top priority conditions
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
    
    # Extract deficient conditions from PreConditions output
    deficient_conditions = cloud_output.get('deficient_conditions', [])
    logger.info(f"Found {len(deficient_conditions)} deficient conditions to evaluate")
    
    # Transform each condition to Airflow format
    conditions = []
    for idx, cond in enumerate(deficient_conditions, 1):
        # Extract condition details
        condition_id = cond.get('condition_id', f'cond_{idx}')
        condition_name = cond.get('condition_name', '')
        compartment = cond.get('compartment', 'General')
        actionable_instruction = cond.get('actionable_instruction', condition_name)
        
        airflow_condition = {
            "condition": {
                "id": idx,  # Sequential ID for Airflow
                "name": condition_name,
                "data": {
                    "Title": condition_name,
                    "Category": compartment,
                    "Description": actionable_instruction
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

