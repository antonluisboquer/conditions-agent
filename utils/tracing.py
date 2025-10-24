"""LangSmith tracing integration."""
import os
from typing import Optional, Dict, Any
from functools import wraps
from langsmith import traceable, Client
from langsmith.run_helpers import get_current_run_tree

from config.settings import settings
from utils.logging_config import get_logger

logger = get_logger(__name__)


class TracingManager:
    """Manager for LangSmith tracing."""
    
    def __init__(self):
        """Initialize tracing manager."""
        self._setup_langsmith()
        self.client = Client()
    
    def _setup_langsmith(self):
        """Set up LangSmith environment variables."""
        os.environ["LANGCHAIN_TRACING_V2"] = str(settings.langsmith_tracing_v2).lower()
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
        logger.info(f"LangSmith tracing enabled for project: {settings.langsmith_project}")
    
    def get_trace_url(self, run_id: Optional[str] = None) -> Optional[str]:
        """
        Get LangSmith trace URL for a run.
        
        Args:
            run_id: Optional run ID. If not provided, uses current run.
            
        Returns:
            URL to view the trace in LangSmith
        """
        try:
            if run_id:
                return f"https://smith.langchain.com/o/{settings.langsmith_project}/runs/{run_id}"
            
            # Try to get current run
            run_tree = get_current_run_tree()
            if run_tree and run_tree.id:
                return f"https://smith.langchain.com/o/{settings.langsmith_project}/runs/{run_tree.id}"
        except Exception as e:
            logger.warning(f"Could not generate trace URL: {e}")
        
        return None
    
    def add_tags(self, tags: Dict[str, Any]):
        """
        Add tags to the current trace.
        
        Args:
            tags: Dictionary of tags to add
        """
        try:
            run_tree = get_current_run_tree()
            if run_tree:
                for key, value in tags.items():
                    run_tree.add_tags([f"{key}:{value}"])
        except Exception as e:
            logger.warning(f"Could not add tags to trace: {e}")
    
    def log_metrics(self, metrics: Dict[str, Any]):
        """
        Log metrics to the current trace.
        
        Args:
            metrics: Dictionary of metrics to log
        """
        try:
            run_tree = get_current_run_tree()
            if run_tree:
                run_tree.add_metadata(metrics)
        except Exception as e:
            logger.warning(f"Could not log metrics to trace: {e}")


# Global tracing manager instance
tracing_manager = TracingManager()


def trace_agent_execution(name: str = None):
    """
    Decorator to trace agent execution with LangSmith.
    
    Args:
        name: Optional custom name for the trace
    """
    def decorator(func):
        @traceable(name=name or func.__name__)
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Add basic tags
            tracing_manager.add_tags({
                "agent_name": "conditions-agent",
                "function": func.__name__
            })
            
            # Extract loan_guid if available
            if kwargs.get("loan_guid"):
                tracing_manager.add_tags({"loan_guid": kwargs["loan_guid"]})
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
                raise
        
        @traceable(name=name or func.__name__)
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Add basic tags
            tracing_manager.add_tags({
                "agent_name": "conditions-agent",
                "function": func.__name__
            })
            
            # Extract loan_guid if available
            if kwargs.get("loan_guid"):
                tracing_manager.add_tags({"loan_guid": kwargs["loan_guid"]})
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
                raise
        
        # Return appropriate wrapper based on whether function is async
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

