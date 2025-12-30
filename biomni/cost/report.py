"""
Cost reporting functionality.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from .models import TokenUsage
from .cost_calculator import CostCalculator
from .token_tracker import TokenTracker

logger = logging.getLogger(__name__)

# Constants
_MAX_FILENAME_LENGTH = 255
_FILENAME_SAFE_PATTERN = re.compile(r'[^a-zA-Z0-9._-]')


class CostReport:
    """Generates cost reports for sessions and workflows."""
    
    def __init__(self, cost_calculator: Optional[CostCalculator] = None):
        """
        Initialize cost report generator.
        
        Args:
            cost_calculator: Optional CostCalculator instance
        """
        self.cost_calculator = cost_calculator or CostCalculator()
    
    def generate_session_report(
        self,
        token_tracker: TokenTracker,
        session_id: Optional[str] = None,
        include_cost_records: bool = True
    ) -> Dict:
        """
        Generate cost report for a session.
        
        Args:
            token_tracker: TokenTracker instance with token usage history
            session_id: Optional session identifier (uses tracker's session_id if not provided)
            include_cost_records: Whether to include detailed cost_records in result.
                                 Set to False for better performance with large datasets.
            
        Returns:
            Dictionary with cost report containing:
            - session_id: Session identifier
            - total_cost: Total cost for the session
            - currency: Currency code
            - total_calls: Number of LLM calls
            - by_model: Cost breakdown by model
            - by_context: Cost breakdown by context
            - cost_records: List of detailed cost records (if include_cost_records=True)
            - summary: Summary statistics
        """
        # Validate input
        if not isinstance(token_tracker, TokenTracker):
            raise TypeError(f"token_tracker must be a TokenTracker instance, got {type(token_tracker).__name__}")
        
        session_id = session_id or token_tracker.session_id
        token_usages = token_tracker.token_usage_history
        
        if not token_usages:
            return {
                "session_id": session_id,
                "total_cost": 0.0,
                "currency": "USD",
                "total_calls": 0,
                "by_model": {},
                "by_context": {},
                "cost_records": [] if include_cost_records else None,
                "summary": {
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "total_tokens": 0,
                    "average_cost_per_call": 0.0,
                },
            }
        
        cost_data = self.cost_calculator.calculate_session_cost(
            token_usages, session_id, include_cost_records=include_cost_records
        )
        
        # Summary is now calculated in cost_calculator to avoid duplicate iteration
        # If summary is missing (for backward compatibility), calculate it
        if "summary" not in cost_data:
            total_input = 0
            total_output = 0
            total_tokens = 0
            
            for usage in token_usages:
                total_input += usage.input_tokens
                total_output += usage.output_tokens
                total_tokens += usage.total_tokens
            
            cost_data["summary"] = {
                "total_input_tokens": total_input,
                "total_output_tokens": total_output,
                "total_tokens": total_tokens,
                "average_cost_per_call": cost_data["total_cost"] / len(token_usages) if token_usages else 0.0,
            }
        
        return cost_data
    
    def generate_workflow_report(
        self,
        token_tracker: TokenTracker,
        workflow_id: str,
        include_cost_records: bool = True
    ) -> Dict:
        """
        Generate cost report for a specific workflow.
        
        Args:
            token_tracker: TokenTracker instance
            workflow_id: Workflow identifier
            include_cost_records: Whether to include detailed cost_records in result.
                                 Set to False for better performance with large datasets.
            
        Returns:
            Dictionary with workflow cost report containing:
            - workflow_id: Workflow identifier
            - session_id: Session identifier (if available)
            - total_cost: Total cost for the workflow
            - currency: Currency code
            - total_calls: Number of LLM calls
            - by_model: Cost breakdown by model
            - by_context: Cost breakdown by context
            - cost_records: List of detailed cost records (if include_cost_records=True)
        """
        # Validate input
        if not isinstance(token_tracker, TokenTracker):
            raise TypeError(f"token_tracker must be a TokenTracker instance, got {type(token_tracker).__name__}")
        if not isinstance(workflow_id, str) or not workflow_id:
            raise ValueError("workflow_id must be a non-empty string")
        
        # Filter token usages by workflow_id
        workflow_usages = [
            usage for usage in token_tracker.token_usage_history
            if usage.workflow_id == workflow_id
        ]
        
        if not workflow_usages:
            return {
                "workflow_id": workflow_id,
                "total_cost": 0.0,
                "currency": "USD",
                "total_calls": 0,
                "by_model": {},
                "by_context": {},
                "cost_records": [] if include_cost_records else None,
            }
        
        cost_data = self.cost_calculator.calculate_session_cost(
            workflow_usages, workflow_id, include_cost_records=include_cost_records
        )
        cost_data["workflow_id"] = workflow_id
        
        return cost_data
    
    def format_cost_summary(self, cost_data: Dict) -> str:
        """
        Format cost data as a human-readable string.
        
        Args:
            cost_data: Cost data dictionary
            
        Returns:
            Formatted string
        """
        lines = []
        lines.append("=" * 60)
        lines.append("COST SUMMARY")
        lines.append("=" * 60)
        
        if "session_id" in cost_data:
            lines.append(f"Session ID: {cost_data['session_id']}")
        if "workflow_id" in cost_data:
            lines.append(f"Workflow ID: {cost_data['workflow_id']}")
        
        lines.append(f"\nTotal Cost: ${cost_data.get('total_cost', 0.0):.4f} {cost_data.get('currency', 'USD')}")
        lines.append(f"Total Calls: {cost_data.get('total_calls', 0)}")
        
        if "summary" in cost_data:
            summary = cost_data["summary"]
            lines.append(f"\nTotal Tokens: {summary.get('total_tokens', 0):,}")
            lines.append(f"  Input: {summary.get('total_input_tokens', 0):,}")
            lines.append(f"  Output: {summary.get('total_output_tokens', 0):,}")
            lines.append(f"Average Cost per Call: ${summary.get('average_cost_per_call', 0.0):.4f}")
        
        # By model breakdown - use safe dictionary access
        if "by_model" in cost_data and cost_data["by_model"]:
            lines.append("\n" + "-" * 60)
            lines.append("Cost by Model:")
            lines.append("-" * 60)
            for model, data in cost_data["by_model"].items():
                if not isinstance(data, dict):
                    continue
                lines.append(f"\n{model}:")
                lines.append(f"  Cost: ${data.get('cost', 0.0):.4f}")
                lines.append(f"  Calls: {data.get('call_count', 0)}")
                lines.append(
                    f"  Tokens: {data.get('total_tokens', 0):,} "
                    f"(Input: {data.get('input_tokens', 0):,}, "
                    f"Output: {data.get('output_tokens', 0):,})"
                )
        
        # By context breakdown - use safe dictionary access
        if "by_context" in cost_data and cost_data["by_context"]:
            lines.append("\n" + "-" * 60)
            lines.append("Cost by Context:")
            lines.append("-" * 60)
            for context, data in cost_data["by_context"].items():
                if not isinstance(data, dict):
                    continue
                lines.append(f"\n{context}:")
                lines.append(f"  Cost: ${data.get('cost', 0.0):.4f}")
                lines.append(f"  Calls: {data.get('call_count', 0)}")
                lines.append(
                    f"  Tokens: {data.get('total_tokens', 0):,} "
                    f"(Input: {data.get('input_tokens', 0):,}, "
                    f"Output: {data.get('output_tokens', 0):,})"
                )
        
        lines.append("\n" + "=" * 60)
        
        return "\n".join(lines)
    
    @staticmethod
    def _sanitize_filename(filename: str, max_length: int = _MAX_FILENAME_LENGTH) -> str:
        """
        Sanitize filename to prevent path traversal and other security issues.
        
        Args:
            filename: Original filename
            max_length: Maximum filename length
            
        Returns:
            Sanitized filename safe for filesystem use
        """
        # Remove or replace unsafe characters
        sanitized = _FILENAME_SAFE_PATTERN.sub('_', filename)
        # Limit length
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        # Ensure it's not empty
        if not sanitized or sanitized == '_':
            sanitized = "unknown"
        return sanitized
    
    def save_report(
        self,
        cost_data: Dict,
        filepath: Optional[str] = None,
        log_dir: Optional[str] = None
    ) -> str:
        """
        Save cost report to a JSON file.
        
        Args:
            cost_data: Cost data dictionary
            filepath: Optional file path
            log_dir: Optional log directory (default: ./costs/logs)
            
        Returns:
            Path to saved file
            
        Raises:
            OSError: If file cannot be written (permissions, disk full, etc.)
            ValueError: If cost_data is invalid
        """
        if not isinstance(cost_data, dict):
            raise ValueError(f"cost_data must be a dictionary, got {type(cost_data).__name__}")
        
        if not filepath:
            log_dir_path = Path(log_dir) if log_dir else Path("./costs/logs")
            try:
                log_dir_path.mkdir(parents=True, exist_ok=True)
            except (OSError, PermissionError) as e:
                logger.error(f"Failed to create log directory {log_dir_path}: {e}")
                raise
            
            # Sanitize session_id to prevent path traversal attacks
            session_id = cost_data.get("session_id", "unknown")
            sanitized_session_id = self._sanitize_filename(str(session_id))
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = log_dir_path / f"{sanitized_session_id}_{timestamp}_cost.json"
        else:
            filepath = Path(filepath)
        
        # Ensure parent directory exists
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            logger.error(f"Failed to create directory for {filepath}: {e}")
            raise
        
        # Add metadata - place metadata first to avoid key conflicts
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "report_type": "cost_report",
        }
        # Add cost_data, allowing it to override metadata if needed (but timestamp/report_type are set first)
        report_data.update(cost_data)
        # Ensure timestamp and report_type are not overridden
        report_data["timestamp"] = datetime.now().isoformat()
        report_data["report_type"] = "cost_report"
        
        # Write file with error handling
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
        except (OSError, IOError, PermissionError) as e:
            logger.error(f"Failed to write cost report to {filepath}: {e}")
            raise
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize cost report data: {e}")
            raise
        
        return str(filepath)
    