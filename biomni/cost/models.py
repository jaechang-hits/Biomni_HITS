"""
Data models for cost tracking.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class TokenUsage:
    """
    Represents token usage for a single LLM call.
    
    This dataclass validates token counts and ensures data consistency.
    If total_tokens is provided, it must match input_tokens + output_tokens.
    If not provided, it will be auto-calculated.
    """
    
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    timestamp: datetime
    context: str  # e.g., "workflow_generation", "agent_reasoning", "tool_query"
    session_id: Optional[str] = None
    workflow_id: Optional[str] = None
    
    def __post_init__(self):
        """Validate token counts and ensure data consistency."""
        # Validate model name
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError(f"model must be a non-empty string, got: {self.model}")
        
        # Validate token counts are non-negative integers
        if not isinstance(self.input_tokens, int) or self.input_tokens < 0:
            raise ValueError(
                f"input_tokens must be a non-negative integer, got: {self.input_tokens}"
            )
        if not isinstance(self.output_tokens, int) or self.output_tokens < 0:
            raise ValueError(
                f"output_tokens must be a non-negative integer, got: {self.output_tokens}"
            )
        if not isinstance(self.total_tokens, int) or self.total_tokens < 0:
            raise ValueError(
                f"total_tokens must be a non-negative integer, got: {self.total_tokens}"
            )
        
        # Validate total_tokens matches input_tokens + output_tokens
        calculated_total = self.input_tokens + self.output_tokens
        if self.total_tokens != calculated_total:
            # Auto-correct total_tokens to ensure consistency
            object.__setattr__(self, 'total_tokens', calculated_total)
        
        # Validate context
        if not isinstance(self.context, str) or not self.context.strip():
            raise ValueError(f"context must be a non-empty string, got: {self.context}")
        
        # Validate timestamp
        if not isinstance(self.timestamp, datetime):
            raise ValueError(f"timestamp must be a datetime object, got: {type(self.timestamp)}")
    
    def to_dict(self, exclude_none: bool = False) -> Dict[str, Any]:
        """
        Convert to dictionary for serialization.
        
        Args:
            exclude_none: If True, exclude None values from the dictionary
            
        Returns:
            Dictionary representation of TokenUsage
        """
        result = {
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context,
        }
        
        # Add optional fields
        if self.session_id is not None or not exclude_none:
            result["session_id"] = self.session_id
        if self.workflow_id is not None or not exclude_none:
            result["workflow_id"] = self.workflow_id
        
        # Remove None values if requested
        if exclude_none:
            result = {k: v for k, v in result.items() if v is not None}
        
        return result


@dataclass
class CostRecord:
    """
    Represents cost information for token usage.
    
    This dataclass validates cost and currency data.
    """
    
    token_usage: TokenUsage
    cost: float
    currency: str = "USD"
    
    def __post_init__(self):
        """Validate cost and currency."""
        # Validate token_usage
        if not isinstance(self.token_usage, TokenUsage):
            raise TypeError(
                f"token_usage must be a TokenUsage instance, got: {type(self.token_usage)}"
            )
        
        # Validate cost is non-negative
        if not isinstance(self.cost, (int, float)) or self.cost < 0:
            raise ValueError(f"cost must be a non-negative number, got: {self.cost}")
        
        # Validate currency
        if not isinstance(self.currency, str) or not self.currency.strip():
            raise ValueError(f"currency must be a non-empty string, got: {self.currency}")
        
        # Normalize currency to uppercase
        object.__setattr__(self, 'currency', self.currency.upper())
    
    def to_dict(self, exclude_none: bool = False) -> Dict[str, Any]:
        """
        Convert to dictionary for serialization.
        
        Args:
            exclude_none: If True, exclude None values from nested dictionaries
            
        Returns:
            Dictionary representation of CostRecord
        """
        return {
            "token_usage": self.token_usage.to_dict(exclude_none=exclude_none),
            "cost": self.cost,
            "currency": self.currency,
        }
