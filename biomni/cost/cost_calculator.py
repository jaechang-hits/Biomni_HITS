"""
Cost calculation for LLM token usage.
"""

import logging
from typing import Dict, Optional, List, Any
from .models import TokenUsage, CostRecord
from .pricing import get_model_pricing

logger = logging.getLogger(__name__)

# Constants
_TOKENS_PER_1K = 1000.0
_COST_PRECISION = 6  # Decimal places for cost rounding


class CostCalculator:
    """Calculates costs based on token usage."""
    
    def __init__(self, default_currency: str = "USD"):
        """
        Initialize cost calculator.
        
        Args:
            default_currency: Default currency for cost calculations
        """
        self.default_currency = default_currency
    
    @staticmethod
    def _create_empty_group_dict() -> Dict[str, Any]:
        """
        Create an empty dictionary for grouping statistics.
        
        Returns:
            Dictionary with initialized grouping fields
        """
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cost": 0.0,
            "call_count": 0,
        }
    
    @staticmethod
    def _create_empty_session_result(
        session_id: Optional[str],
        currency: str,
        include_cost_records: bool = True
    ) -> Dict[str, Any]:
        """
        Create an empty session cost result dictionary.
        
        Args:
            session_id: Optional session identifier
            currency: Currency code
            include_cost_records: Whether to include cost_records field
            
        Returns:
            Dictionary with empty session cost structure
        """
        result = {
            "session_id": session_id,
            "total_cost": 0.0,
            "currency": currency,
            "total_calls": 0,
            "by_model": {},
            "by_context": {},
        }
        if include_cost_records:
            result["cost_records"] = []
        return result
    
    def calculate_llm_cost(self, token_usage: TokenUsage) -> CostRecord:
        """
        Calculate cost for a single token usage record.
        
        Args:
            token_usage: TokenUsage object
            
        Returns:
            CostRecord with calculated cost
            
        Raises:
            ValueError: If token counts are negative or pricing is invalid
        """
        # Validate input
        if token_usage.input_tokens < 0 or token_usage.output_tokens < 0:
            raise ValueError(
                f"Token counts must be non-negative. "
                f"Got input_tokens={token_usage.input_tokens}, "
                f"output_tokens={token_usage.output_tokens}"
            )
        
        pricing = get_model_pricing(token_usage.model)
        
        if not pricing:
            logger.warning(
                f"No pricing found for model '{token_usage.model}'. Cost set to 0."
            )
            return CostRecord(
                token_usage=token_usage,
                cost=0.0,
                currency=self.default_currency,
            )
        
        # Validate pricing structure
        required_keys = ["input_price_per_1k_tokens", "output_price_per_1k_tokens"]
        missing_keys = [key for key in required_keys if key not in pricing]
        if missing_keys:
            logger.error(
                f"Pricing for model '{token_usage.model}' missing required keys: {missing_keys}. "
                f"Cost set to 0."
            )
            return CostRecord(
                token_usage=token_usage,
                cost=0.0,
                currency=self.default_currency,
            )
        
        # Validate pricing values are non-negative
        # Use get() for safety even though we validated keys above
        input_price = pricing.get("input_price_per_1k_tokens", 0)
        output_price = pricing.get("output_price_per_1k_tokens", 0)
        
        if input_price < 0 or output_price < 0:
            logger.error(
                f"Invalid pricing for model '{token_usage.model}': "
                f"prices must be non-negative. Got input={input_price}, output={output_price}. "
                f"Cost set to 0."
            )
            return CostRecord(
                token_usage=token_usage,
                cost=0.0,
                currency=self.default_currency,
            )
        
        # Calculate costs
        # Use explicit float conversion to handle potential type issues
        try:
            input_cost = float(token_usage.input_tokens) / _TOKENS_PER_1K * float(input_price)
            output_cost = float(token_usage.output_tokens) / _TOKENS_PER_1K * float(output_price)
            total_cost = input_cost + output_cost
            # Round to avoid floating point precision issues
            total_cost = round(total_cost, _COST_PRECISION)
        except (TypeError, OverflowError, ValueError) as e:
            logger.error(
                f"Error calculating cost for model '{token_usage.model}': {e}. "
                f"Cost set to 0."
            )
            return CostRecord(
                token_usage=token_usage,
                cost=0.0,
                currency=self.default_currency,
            )
        
        currency = pricing.get("currency", self.default_currency)
        
        return CostRecord(
            token_usage=token_usage,
            cost=total_cost,
            currency=currency,
        )
    
    def calculate_session_cost(
        self,
        token_usages: List[TokenUsage],
        session_id: Optional[str] = None,
        include_cost_records: bool = True
    ) -> Dict[str, Any]:
        """
        Calculate total cost for a session (list of token usages).
        
        Args:
            token_usages: List of TokenUsage objects
            session_id: Optional session identifier
            include_cost_records: Whether to include detailed cost_records in result.
                                 Set to False for better performance with large datasets.
            
        Returns:
            Dictionary with cost breakdown containing:
            - session_id: Session identifier
            - total_cost: Total cost for the session
            - currency: Currency code
            - total_calls: Number of LLM calls
            - by_model: Cost breakdown by model
            - by_context: Cost breakdown by context
            - cost_records: List of detailed cost records (if include_cost_records=True)
        """
        # Early return for empty input
        if not token_usages:
            return self._create_empty_session_result(
                session_id, self.default_currency, include_cost_records
            )
        
        # Validate input early
        if not isinstance(token_usages, list):
            raise TypeError(f"token_usages must be a list, got {type(token_usages).__name__}")
        
        # Calculate costs with error handling for individual records
        cost_records: List[CostRecord] = []
        failed_count = 0
        
        for usage in token_usages:
            # Validate usage object
            if not isinstance(usage, TokenUsage):
                logger.warning(
                    f"Skipping invalid usage object: expected TokenUsage, got {type(usage).__name__}"
                )
                failed_count += 1
                continue
            
            try:
                record = self.calculate_llm_cost(usage)
                cost_records.append(record)
            except (ValueError, TypeError, AttributeError) as e:
                # Catch specific exceptions that can occur during cost calculation
                logger.error(
                    f"Failed to calculate cost for usage: {usage.model} "
                    f"(input={usage.input_tokens}, output={usage.output_tokens}): {e}"
                )
                failed_count += 1
                # Continue processing other records
            except Exception as e:
                # Catch any other unexpected exceptions but log with more detail
                logger.error(
                    f"Unexpected error calculating cost for usage: {usage.model} "
                    f"(input={usage.input_tokens}, output={usage.output_tokens}): {e}",
                    exc_info=True
                )
                failed_count += 1
                # Continue processing other records
        
        # Log summary if there were failures
        if failed_count > 0:
            logger.warning(
                f"Failed to calculate cost for {failed_count} out of {len(token_usages)} usage records"
            )
        
        if not cost_records:
            return self._create_empty_session_result(
                session_id, self.default_currency, include_cost_records
            )
        
        total_cost = sum(record.cost for record in cost_records)
        
        # Group by model and context in a single pass for better performance
        # Also calculate summary totals to avoid duplicate iteration
        by_model: Dict[str, Dict[str, Any]] = {}
        by_context: Dict[str, Dict[str, Any]] = {}
        currencies = set()
        
        # Summary totals (calculated during grouping to avoid extra iteration)
        total_input_tokens = 0
        total_output_tokens = 0
        total_tokens = 0
        
        for record in cost_records:
            currencies.add(record.currency)
            usage = record.token_usage
            
            # Accumulate summary totals
            total_input_tokens += usage.input_tokens
            total_output_tokens += usage.output_tokens
            total_tokens += usage.total_tokens
            
            # Group by model - cache dictionary access for performance
            model = usage.model
            if model not in by_model:
                by_model[model] = self._create_empty_group_dict()
            
            model_data = by_model[model]
            model_data["input_tokens"] += usage.input_tokens
            model_data["output_tokens"] += usage.output_tokens
            model_data["total_tokens"] += usage.total_tokens
            model_data["cost"] += record.cost
            model_data["call_count"] += 1
            
            # Group by context - cache dictionary access for performance
            context = usage.context
            if context not in by_context:
                by_context[context] = self._create_empty_group_dict()
            
            context_data = by_context[context]
            context_data["input_tokens"] += usage.input_tokens
            context_data["output_tokens"] += usage.output_tokens
            context_data["total_tokens"] += usage.total_tokens
            context_data["cost"] += record.cost
            context_data["call_count"] += 1
        
        # Determine currency - warn if mixed
        # Safe access: cost_records is guaranteed to be non-empty here (checked above)
        if len(currencies) > 1:
            logger.warning(
                f"Session {session_id} has mixed currencies: {currencies}. "
                f"Using first currency: {cost_records[0].currency}"
            )
        currency = cost_records[0].currency
        
        # Build result dictionary
        result: Dict[str, Any] = {
            "session_id": session_id,
            "total_cost": round(total_cost, _COST_PRECISION),  # Round total for consistency
            "currency": currency,
            "total_calls": len(cost_records),
            "by_model": by_model,
            "by_context": by_context,
            # Include summary to avoid duplicate calculation in report.py
            "summary": {
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "total_tokens": total_tokens,
                "average_cost_per_call": round(total_cost / len(cost_records), _COST_PRECISION) if cost_records else 0.0,
            },
        }
        
        # Only include cost_records if requested (saves memory for large datasets)
        if include_cost_records:
            result["cost_records"] = [record.to_dict() for record in cost_records]
        
        return result
    
