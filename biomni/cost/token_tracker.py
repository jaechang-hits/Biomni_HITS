"""
Token usage tracking for LLM calls.
"""

import logging
import os
import json
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from .models import TokenUsage

logger = logging.getLogger(__name__)

# Debug logging (conditionally enabled via COST_TRACKING_DEBUG env var)
_COST_DEBUG_ENABLED = os.getenv("COST_TRACKING_DEBUG", "false").lower() == "true"
_DEBUG_LOG_PATH = os.getenv(
    "COST_DEBUG_LOG_PATH",
    os.path.join(os.path.dirname(__file__), "..", "..", ".cursor", "debug.log")
)

def _log_debug(location: str, message: str, data: Any, hypothesis_id: str = "G"):
    """Conditionally log debug information if COST_TRACKING_DEBUG is enabled."""
    if not _COST_DEBUG_ENABLED:
        return
    try:
        from pathlib import Path
        
        # Ensure directory exists
        log_file = Path(_DEBUG_LOG_PATH)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        log_entry = {
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": hypothesis_id
        }
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except (OSError, IOError, PermissionError) as e:
        # Log to standard logger if file write fails
        logger.debug(f"Failed to write debug log: {e}")
    except Exception as e:
        # Catch-all for unexpected errors, but log them
        logger.debug(f"Unexpected error in debug logging: {e}")


class TokenTracker:
    """Tracks token usage across LLM calls."""
    
    def __init__(self, session_id: Optional[str] = None, log_dir: Optional[str] = None):
        """
        Initialize token tracker.
        
        Args:
            session_id: Optional session identifier
            log_dir: Directory for logging token usage (default: ./costs/logs)
        """
        self.session_id = session_id or self._generate_session_id()
        self.token_usage_history: List[TokenUsage] = []
        self.log_dir = Path(log_dir) if log_dir else Path("./costs/logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        # Use timestamp + UUID to ensure uniqueness even with concurrent creation
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        return f"session_{timestamp}_{unique_id}"
    
    def extract_token_usage(self, response: Any, model: str, context: str = "unknown") -> Optional[Dict[str, int]]:
        """
        Extract token usage from LLM response.
        
        Args:
            response: LLM response object
            model: Model name
            context: Context of the call (e.g., "workflow_generation")
            
        Returns:
            Dictionary with input_tokens, output_tokens, total_tokens, or None if not available
        """
        _log_debug(
            "token_tracker.py:extract_token_usage:entry",
            "extract_token_usage() called",
            {"response_type": type(response).__name__, "model": model, "has_response_metadata": hasattr(response, 'response_metadata')}
        )
        
        try:
            # Try to get response_metadata
            metadata = getattr(response, 'response_metadata', None)
            
            # Safe metadata keys extraction
            metadata_keys = list(metadata.keys()) if isinstance(metadata, dict) else "not_dict"
            metadata_str = str(metadata)[:500] if metadata else None
            _log_debug(
                "token_tracker.py:extract_token_usage:metadata_check",
                "Checking response_metadata",
                {
                    "metadata": metadata_str,
                    "metadata_type": type(metadata).__name__ if metadata else None,
                    "metadata_keys": metadata_keys,
                    "model": model
                }
            )
            
            # Check for usage_metadata attribute (Gemini streaming uses this)
            if hasattr(response, 'usage_metadata'):
                usage_meta = response.usage_metadata
                if isinstance(usage_meta, dict):
                    result = {
                        "input_tokens": usage_meta.get('input_tokens', 0),
                        "output_tokens": usage_meta.get('output_tokens', 0),
                        "total_tokens": usage_meta.get('total_tokens', 0),
                    }
                    _log_debug(
                        "token_tracker.py:extract_token_usage:usage_metadata_attr",
                        "Extracted tokens from usage_metadata attribute",
                        result
                    )
                    return result
            
            if metadata is None:
                # Try to get from response object directly
                if hasattr(response, 'usage'):
                    usage = response.usage
                    # Handle both Anthropic and OpenAI formats
                    if isinstance(usage, dict):
                        # Use explicit None check to avoid treating 0 as falsy
                        input_tokens = usage.get('input_tokens') if usage.get('input_tokens') is not None else usage.get('prompt_tokens', 0)
                        output_tokens = usage.get('output_tokens') if usage.get('output_tokens') is not None else usage.get('completion_tokens', 0)
                        total_tokens = usage.get('total_tokens') if usage.get('total_tokens') is not None else (input_tokens + output_tokens)
                    else:
                        input_tokens = getattr(usage, 'input_tokens', None)
                        if input_tokens is None:
                            input_tokens = getattr(usage, 'prompt_tokens', 0)
                        output_tokens = getattr(usage, 'output_tokens', None)
                        if output_tokens is None:
                            output_tokens = getattr(usage, 'completion_tokens', 0)
                        total_tokens = getattr(usage, 'total_tokens', None)
                        if total_tokens is None:
                            total_tokens = input_tokens + output_tokens
                    
                    return {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": total_tokens,
                    }
                return None
            
            # Ensure metadata is a dict before accessing keys
            if not isinstance(metadata, dict):
                _log_debug(
                    "token_tracker.py:extract_token_usage:metadata_not_dict",
                    "Metadata is not a dictionary",
                    {"metadata_type": type(metadata).__name__}
                )
                return None
            
            # Gemini format - check for usageMetadata (native Gemini API format)
            # This appears in the last chunk of streaming responses when stream_options.include_usage is true
            if 'usageMetadata' in metadata or 'usage_metadata' in metadata:
                usage_meta = metadata.get('usageMetadata') or metadata.get('usage_metadata', {})
                if isinstance(usage_meta, dict):
                    # Gemini uses promptTokenCount and candidatesTokenCount
                    result = {
                        "input_tokens": usage_meta.get('promptTokenCount', usage_meta.get('prompt_tokens', 0)),
                        "output_tokens": usage_meta.get('candidatesTokenCount', usage_meta.get('completion_tokens', 0)),
                        "total_tokens": usage_meta.get('totalTokenCount', usage_meta.get('total_tokens', 0)),
                    }
                    _log_debug(
                        "token_tracker.py:extract_token_usage:gemini_metadata",
                        "Extracted tokens from Gemini usageMetadata",
                        result
                    )
                    return result
            
            # Anthropic format (supports both prompt_tokens/completion_tokens and input_tokens/output_tokens)
            if 'usage' in metadata:
                usage = metadata['usage']
                
                if isinstance(usage, dict):
                    # Map Anthropic's prompt_tokens/completion_tokens to input_tokens/output_tokens
                    # Use explicit None check to avoid treating 0 as falsy
                    input_tokens = usage.get('input_tokens') if usage.get('input_tokens') is not None else usage.get('prompt_tokens', 0)
                    output_tokens = usage.get('output_tokens') if usage.get('output_tokens') is not None else usage.get('completion_tokens', 0)
                    total_tokens = usage.get('total_tokens') if usage.get('total_tokens') is not None else (input_tokens + output_tokens)
                    
                    result = {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": total_tokens,
                    }
                    _log_debug(
                        "token_tracker.py:extract_token_usage:anthropic_dict",
                        "Extracted tokens from Anthropic dict",
                        result
                    )
                    return result
                elif hasattr(usage, 'input_tokens') or hasattr(usage, 'prompt_tokens'):
                    # Handle object with attributes
                    input_tokens = getattr(usage, 'input_tokens', None)
                    if input_tokens is None:
                        input_tokens = getattr(usage, 'prompt_tokens', 0)
                    output_tokens = getattr(usage, 'output_tokens', None)
                    if output_tokens is None:
                        output_tokens = getattr(usage, 'completion_tokens', 0)
                    total_tokens = getattr(usage, 'total_tokens', None)
                    if total_tokens is None:
                        total_tokens = input_tokens + output_tokens
                    
                    result = {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": total_tokens,
                    }
                    _log_debug(
                        "token_tracker.py:extract_token_usage:anthropic_attr",
                        "Extracted tokens from Anthropic attributes",
                        result
                    )
                    return result
            
            # OpenAI format (also used by Gemini via OpenAI-compatible API)
            if 'token_usage' in metadata:
                token_usage = metadata['token_usage']
                if isinstance(token_usage, dict):
                    result = {
                        "input_tokens": token_usage.get('prompt_tokens', 0),
                        "output_tokens": token_usage.get('completion_tokens', 0),
                        "total_tokens": token_usage.get('total_tokens', 0),
                    }
                    _log_debug(
                        "token_tracker.py:extract_token_usage:openai_dict",
                        "Extracted tokens from OpenAI dict",
                        result
                    )
                    return result
                elif hasattr(token_usage, 'prompt_tokens'):
                    result = {
                        "input_tokens": token_usage.prompt_tokens,
                        "output_tokens": token_usage.completion_tokens,
                        "total_tokens": token_usage.total_tokens,
                    }
                    _log_debug(
                        "token_tracker.py:extract_token_usage:openai_attr",
                        "Extracted tokens from OpenAI attributes",
                        result
                    )
                    return result
            
            # Bedrock format - check multiple possible locations and formats
            # Format 1: Direct token count fields in metadata
            if 'input_token_count' in metadata or 'output_token_count' in metadata:
                result = {
                    "input_tokens": metadata.get('input_token_count', 0),
                    "output_tokens": metadata.get('output_token_count', 0),
                    "total_tokens": metadata.get('total_token_count', metadata.get('input_token_count', 0) + metadata.get('output_token_count', 0)),
                }
                _log_debug(
                    "token_tracker.py:extract_token_usage:bedrock_token_count",
                    "Extracted tokens from Bedrock token_count fields",
                    result
                )
                return result
            
            # Format 2: usage object or tokenCount in metadata
            if 'usage' in metadata or 'tokenCount' in metadata:
                usage_data = metadata.get('usage') or metadata.get('tokenCount', {})
                if isinstance(usage_data, dict):
                    result = {
                        "input_tokens": (
                            usage_data.get('inputTokens') or 
                            usage_data.get('input_tokens') or 
                            usage_data.get('input_token_count') or 
                            usage_data.get('prompt_tokens', 0)
                        ),
                        "output_tokens": (
                            usage_data.get('outputTokens') or 
                            usage_data.get('output_tokens') or 
                            usage_data.get('output_token_count') or 
                            usage_data.get('completion_tokens', 0)
                        ),
                        "total_tokens": (
                            usage_data.get('totalTokens') or 
                            usage_data.get('total_tokens') or 
                            usage_data.get('total_token_count', 0)
                        ),
                    }
                    _log_debug(
                        "token_tracker.py:extract_token_usage:bedrock_usage",
                        "Extracted tokens from Bedrock usage object",
                        result
                    )
                    return result
            
        except Exception as e:
            _log_debug(
                "token_tracker.py:extract_token_usage:error",
                "Error extracting token usage",
                {"error": str(e), "error_type": type(e).__name__}
            )
            # Log error but don't fail
            logger.warning(f"Failed to extract token usage: {e}", exc_info=True)
            return None
        
        _log_debug(
            "token_tracker.py:extract_token_usage:no_match",
            "No token usage format matched",
            {"metadata_keys": list(metadata.keys()) if isinstance(metadata, dict) else "not_dict"}
        )
        
        return None
    
    def track_llm_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        context: str = "unknown",
        workflow_id: Optional[str] = None
    ) -> TokenUsage:
        """
        Track an LLM call with token usage.
        
        Args:
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            context: Context of the call
            workflow_id: Optional workflow identifier
            
        Returns:
            TokenUsage object
        """
        _log_debug(
            "token_tracker.py:track_llm_call:entry",
            "track_llm_call() called",
            {
                "session_id": self.session_id,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "current_history_count": len(self.token_usage_history)
            },
            "I"
        )
        
        total_tokens = input_tokens + output_tokens
        token_usage = TokenUsage(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            timestamp=datetime.now(),
            context=context,
            session_id=self.session_id,
            workflow_id=workflow_id,
        )
        
        self.token_usage_history.append(token_usage)
        
        _log_debug(
            "token_tracker.py:track_llm_call:after_append",
            "Token usage appended to history",
            {
                "session_id": self.session_id,
                "history_count": len(self.token_usage_history),
                "tracker_id": id(self)
            },
            "I"
        )
        
        return token_usage
    
    def get_session_tokens(self) -> Dict[str, int]:
        """
        Get total token usage for the current session.
        
        Returns:
            Dictionary with total input_tokens, output_tokens, total_tokens
        """
        # Optimize: single pass through history
        total_input = 0
        total_output = 0
        total = 0
        
        for usage in self.token_usage_history:
            total_input += usage.input_tokens
            total_output += usage.output_tokens
            total += usage.total_tokens
        
        return {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "total_tokens": total,
        }
    
    def get_tokens_by_model(self) -> Dict[str, Dict[str, int]]:
        """
        Get token usage grouped by model.
        
        Returns:
            Dictionary mapping model names to token usage
        """
        model_tokens: Dict[str, Dict[str, int]] = {}
        
        for usage in self.token_usage_history:
            # Cache dictionary access for performance
            model_data = model_tokens.get(usage.model)
            if model_data is None:
                model_data = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                }
                model_tokens[usage.model] = model_data
            
            model_data["input_tokens"] += usage.input_tokens
            model_data["output_tokens"] += usage.output_tokens
            model_data["total_tokens"] += usage.total_tokens
        
        return model_tokens
    
    def reset_session(self, new_session_id: Optional[str] = None):
        """Reset the tracker for a new session."""
        if new_session_id:
            self.session_id = new_session_id
        else:
            self.session_id = self._generate_session_id()
        self.token_usage_history = []
    
    def save_to_file(self, filepath: Optional[str] = None):
        """
        Save token usage history to a JSON file.
        
        Args:
            filepath: Optional file path (default: log_dir/session_id_tokens.json)
        """
        if not filepath:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = self.log_dir / f"{self.session_id}_{timestamp}_tokens.json"
        else:
            filepath = Path(filepath)
        
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "token_usage": [usage.to_dict() for usage in self.token_usage_history],
            "summary": self.get_session_tokens(),
            "by_model": self.get_tokens_by_model(),
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        return str(filepath)
