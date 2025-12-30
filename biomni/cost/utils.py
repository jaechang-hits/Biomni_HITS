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


def get_token_tracker_from_agent() -> Optional[Any]:
    """
    Attempt to get token_tracker from the main agent's LLM in chainlit.run.
    
    This function safely attempts to access the agent's token_tracker
    while handling circular import issues gracefully.
    
    Returns:
        TokenTracker instance if available, None otherwise
        
    Example:
        >>> from biomni.cost import get_token_tracker_from_agent
        >>> tracker = get_token_tracker_from_agent()
        >>> if tracker:
        ...     print(f"Found tracker for session: {tracker.session_id}")
    """
    if not is_cost_tracking_enabled() or not COST_TRACKING_AVAILABLE or CostTrackingLLMWrapper is None:
        return None
    
    try:
        # Try to get token_tracker from agent instance (if available)
        # This may fail due to circular import, but we catch it gracefully
        try:
            from chainlit.run import agent
            if hasattr(agent, 'llm') and isinstance(agent.llm, CostTrackingLLMWrapper):
                token_tracker = getattr(agent.llm, 'token_tracker', None)
                if token_tracker is None:
                    logger.debug("CostTrackingLLMWrapper found but token_tracker is None")
                return token_tracker
        except (ImportError, AttributeError, RuntimeError) as e:
            # Circular import or agent not initialized yet - skip silently
            logger.debug(f"Could not access agent's token_tracker: {type(e).__name__}")
    except Exception as e:
        # Catch any other unexpected errors
        logger.debug(f"Unexpected error getting token_tracker: {e}")
    
    return None


def get_token_tracker_from_llm(llm: Any) -> Optional[Any]:
    """
    Extract token_tracker from LLM instance if it's wrapped with cost tracking.
    
    Args:
        llm: The LLM instance to check
        
    Returns:
        TokenTracker instance if available, None otherwise
        
    Example:
        >>> from biomni.cost import get_token_tracker_from_llm
        >>> tracker = get_token_tracker_from_llm(my_llm)
        >>> if tracker:
        ...     print(f"Found tracker for session: {tracker.session_id}")
    """
    if not COST_TRACKING_AVAILABLE or CostTrackingLLMWrapper is None:
        return None
    
    try:
        if isinstance(llm, CostTrackingLLMWrapper):
            token_tracker = getattr(llm, 'token_tracker', None)
            if token_tracker is None:
                logger.debug("CostTrackingLLMWrapper found but token_tracker is None")
            return token_tracker
    except (AttributeError, TypeError) as e:
        logger.debug(f"Failed to extract token_tracker from LLM: {e}")
    
    return None
