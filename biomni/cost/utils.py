"""
Utility functions for cost tracking.
"""

import logging
import os
from typing import Optional, Any

from langchain_core.language_models.chat_models import BaseChatModel

from .token_tracker import TokenTracker
from .cost_calculator import CostCalculator
from .report import CostReport

logger = logging.getLogger(__name__)

# Cost tracking availability check
try:
    from .llm_wrapper import CostTrackingLLMWrapper
    COST_TRACKING_AVAILABLE = True
except ImportError:
    COST_TRACKING_AVAILABLE = False
    CostTrackingLLMWrapper = None  # type: ignore


def get_default_token_tracker(
    session_id: Optional[str] = None,
    log_dir: Optional[str] = None
) -> TokenTracker:
    """
    Get a default TokenTracker instance.
    
    Args:
        session_id: Optional session identifier
        log_dir: Optional log directory (uses COST_LOG_DIR env var or default)
        
    Returns:
        TokenTracker instance
        
    Raises:
        ValueError: If log_dir is invalid
    """
    if log_dir is None:
        log_dir = os.getenv("COST_LOG_DIR", "./costs/logs")
    
    # Validate log_dir is a string
    if not isinstance(log_dir, str) or not log_dir.strip():
        raise ValueError(f"log_dir must be a non-empty string, got: {log_dir}")
    
    return TokenTracker(session_id=session_id, log_dir=log_dir)


def get_default_cost_report(
    cost_calculator: Optional[CostCalculator] = None
) -> CostReport:
    """
    Get a default CostReport instance.
    
    Args:
        cost_calculator: Optional CostCalculator instance
        
    Returns:
        CostReport instance
    """
    return CostReport(cost_calculator=cost_calculator)


def is_cost_tracking_enabled() -> bool:
    """
    Check if cost tracking is enabled via environment variable.
    
    This function checks the COST_TRACKING_ENABLED environment variable.
    Only logs a message once at DEBUG level to avoid log spam.
    
    Returns:
        True if cost tracking is enabled, False otherwise
    """
    env_value = os.getenv("COST_TRACKING_ENABLED", "false").lower()
    enabled = env_value == "true"
    
    # Log at DEBUG level to avoid spam (only shown if DEBUG logging is enabled)
    if not enabled:
        logger.debug(
            f"Cost tracking is disabled. Set COST_TRACKING_ENABLED=true to enable. "
            f"Current value: {env_value}"
        )
    
    return enabled


def wrap_llm_with_cost_tracking(
    llm: BaseChatModel,
    enable_cost_tracking: bool,
    token_tracker: Optional[TokenTracker] = None,
    context: str = "unknown",
    workflow_id: Optional[str] = None,
) -> BaseChatModel:
    """
    Wrap an LLM instance with cost tracking if enabled.
    
    This is a convenience function that conditionally wraps an LLM with
    CostTrackingLLMWrapper based on the enable_cost_tracking flag.
    
    Args:
        llm: The LLM instance to wrap
        enable_cost_tracking: Whether cost tracking is enabled
        token_tracker: Optional TokenTracker instance (creates new one if not provided)
        context: Context identifier for cost tracking (e.g., "workflow_generation", "agent_main")
        workflow_id: Optional workflow identifier for cost tracking
        
    Returns:
        Wrapped LLM if cost tracking is enabled and available, otherwise original LLM
        
    Example:
        >>> from biomni.cost import wrap_llm_with_cost_tracking
        >>> llm = ChatOpenAI(model="gpt-4")
        >>> tracked_llm = wrap_llm_with_cost_tracking(
        ...     llm=llm,
        ...     enable_cost_tracking=True,
        ...     context="agent_main"
        ... )
    """
    if enable_cost_tracking and COST_TRACKING_AVAILABLE and CostTrackingLLMWrapper is not None:
        return CostTrackingLLMWrapper(
            llm=llm,
            token_tracker=token_tracker,
            context=context,
            workflow_id=workflow_id,
        )
    return llm
