"""
LLM wrapper for automatic token usage tracking.
"""

import logging
import os
import json
from typing import Any, Optional, Iterator, List
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage

from .token_tracker import TokenTracker

logger = logging.getLogger(__name__)

# Debug logging (conditionally enabled via COST_TRACKING_DEBUG env var)
_COST_DEBUG_ENABLED = os.getenv("COST_TRACKING_DEBUG", "false").lower() == "true"
_DEBUG_LOG_PATH = os.getenv("COST_DEBUG_LOG_PATH", os.path.join(os.path.dirname(__file__), "..", "..", ".cursor", "debug.log"))

def _log_debug(location: str, message: str, data: Any, hypothesis_id: str = "A"):
    """Conditionally log debug information if COST_TRACKING_DEBUG is enabled."""
    if not _COST_DEBUG_ENABLED:
        return
    try:
        import time
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


class CostTrackingLLMWrapper(BaseChatModel):
    """
    Wrapper around BaseChatModel that automatically tracks token usage.
    
    This wrapper intercepts invoke() and stream() calls to extract and track
    token usage information.
    """
    
    def __init__(
        self,
        llm: BaseChatModel,
        token_tracker: Optional[TokenTracker] = None,
        context: str = "unknown",
        workflow_id: Optional[str] = None,
    ):
        """
        Initialize the wrapper.
        
        Args:
            llm: The underlying LLM instance to wrap
            token_tracker: Optional TokenTracker instance (creates new one if not provided)
            context: Context identifier for tracking (e.g., "workflow_generation")
            workflow_id: Optional workflow identifier
        """
        _log_debug("llm_wrapper.py:__init__:entry", "Initializing CostTrackingLLMWrapper", {"llm_type": type(llm).__name__, "has_token_tracker": token_tracker is not None}, "A")
        _log_debug("llm_wrapper.py:__init__:before_super", "Before super().__init__()", {"base_class": BaseChatModel.__name__}, "A")
        
        try:
            super().__init__()
            _log_debug("llm_wrapper.py:__init__:after_super", "After super().__init__()", {"success": True}, "A")
        except Exception as e:
            _log_debug("llm_wrapper.py:__init__:super_error", "super().__init__() failed", {"error": str(e), "error_type": type(e).__name__}, "A")
            raise
        
        _log_debug("llm_wrapper.py:__init__:before_llm_assign", "Before self.llm assignment", {"llm_type": type(llm).__name__}, "B")
        
        # Use object.__setattr__ to bypass Pydantic's field validation
        try:
            object.__setattr__(self, 'llm', llm)
            _log_debug("llm_wrapper.py:__init__:after_llm_assign", "After self.llm assignment (object.__setattr__)", {"success": True}, "B")
        except Exception as e:
            _log_debug("llm_wrapper.py:__init__:llm_assign_error", "self.llm assignment failed", {"error": str(e), "error_type": type(e).__name__}, "B")
            raise
        
        _log_debug("llm_wrapper.py:__init__:before_tracker_assign", "Before token_tracker assignment", {}, "C")
        
        try:
            object.__setattr__(self, 'token_tracker', token_tracker or TokenTracker())
            _log_debug("llm_wrapper.py:__init__:after_tracker_assign", "After token_tracker assignment", {"success": True}, "C")
        except Exception as e:
            _log_debug("llm_wrapper.py:__init__:tracker_assign_error", "token_tracker assignment failed", {"error": str(e)}, "C")
            raise
        
        _log_debug("llm_wrapper.py:__init__:before_other_assign", "Before other attribute assignments", {}, "D")
        
        try:
            object.__setattr__(self, 'context', context)
            object.__setattr__(self, 'workflow_id', workflow_id)
            # Copy important attributes from wrapped LLM
            # Try multiple possible attribute names for model identifier
            model_name = (
                getattr(llm, 'model_name', None) or 
                getattr(llm, 'model', None) or 
                getattr(llm, 'model_id', None) or  # ChatBedrock uses model_id
                getattr(llm, 'modelId', None) or   # Alternative camelCase
                "unknown"
            )
            object.__setattr__(self, 'model_name', model_name)
            _log_debug("llm_wrapper.py:__init__:after_other_assign", "After other attribute assignments", {"context": context, "model_name": model_name}, "D")
        except Exception as e:
            _log_debug("llm_wrapper.py:__init__:other_assign_error", "Other attribute assignment failed", {"error": str(e)}, "D")
            raise
        
        _log_debug("llm_wrapper.py:__init__:complete", "Initialization complete", {"success": True}, "ALL")
    
    @property
    def _llm_type(self) -> str:
        """Return the LLM type."""
        return f"cost_tracking_{getattr(self.llm, '_llm_type', 'unknown')}"
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> Any:
        """Generate a response (internal method)."""
        # Delegate to wrapped LLM
        result = self.llm._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
        
        # Track token usage
        self._track_token_usage(result)
        
        return result
    
    def invoke(
        self,
        input: Any,
        config: Optional[Any] = None,
        **kwargs: Any,
    ) -> BaseMessage:
        """
        Invoke the LLM and track token usage.
        
        Args:
            input: Input messages or prompt
            config: Optional configuration
            **kwargs: Additional arguments
            
        Returns:
            LLM response message
        """
        _log_debug("llm_wrapper.py:invoke:entry", "invoke() called", {"has_token_tracker": hasattr(self, 'token_tracker')}, "E")
        
        # Call the wrapped LLM
        response = self.llm.invoke(input, config=config, **kwargs)
        
        _log_debug("llm_wrapper.py:invoke:after_llm_call", "After LLM invoke", {"response_type": type(response).__name__, "has_response_metadata": hasattr(response, 'response_metadata')}, "E")
        
        # Track token usage
        self._track_token_usage(response)
        
        return response
    
    def stream(
        self,
        input: Any,
        config: Optional[Any] = None,
        **kwargs: Any,
    ) -> Iterator[BaseMessage]:
        """
        Stream responses from the LLM.
        
        Note: Token tracking for streaming attempts to extract from chunks.
        Some providers include token usage in the last chunk, others may not.
        
        Args:
            input: Input messages or prompt
            config: Optional configuration
            **kwargs: Additional arguments
            
        Yields:
            Streaming response chunks
        """
        _log_debug("llm_wrapper.py:stream:entry", "stream() called", {"has_token_tracker": hasattr(self, 'token_tracker'), "input_type": type(input).__name__}, "H")
        
        # For streaming, track token usage without storing all chunks in memory
        token_usage_found = False
        token_usage_chunk = None
        last_chunks = []  # Store only last few chunks for fallback token extraction
        max_last_chunks = 5
        
        # For Gemini models, try to add stream_options to kwargs (but don't modify LLM object)
        model_name = getattr(self, 'model_name', '').lower()
        if "gemini" in model_name:
            kwargs = kwargs.copy() if kwargs else {}
            if 'stream_options' not in kwargs:
                kwargs['stream_options'] = {"include_usage": True}
            _log_debug("llm_wrapper.py:stream:gemini_stream_options", "Added stream_options for Gemini", {
                "stream_options_kwargs": kwargs.get('stream_options'),
                "llm_type": type(self.llm).__name__
            }, "H")
        
        chunk_count = 0
        for chunk in self.llm.stream(input, config=config, **kwargs):
            chunk_count += 1
            yield chunk
            
            # Keep only last N chunks for potential token extraction
            last_chunks.append(chunk)
            if len(last_chunks) > max_last_chunks:
                last_chunks.pop(0)
            
            # Check if this chunk has token usage info
            # Optimize: check once and cache results
            chunk_has_usage = False
            usage_location = None
            
            # Location 1: response_metadata
            if hasattr(chunk, 'response_metadata'):
                metadata = chunk.response_metadata
                _log_debug("llm_wrapper.py:stream:chunk_metadata", "Chunk metadata check", {
                    "chunk_idx": chunk_count,
                    "has_metadata": bool(metadata),
                    "metadata_keys": list(metadata.keys()) if isinstance(metadata, dict) else "not_dict"
                }, "H")
                if metadata and isinstance(metadata, dict):
                    usage_keys = ['usage', 'token_usage', 'usageMetadata', 'usage_metadata']
                    if any(key in metadata for key in usage_keys):
                        chunk_has_usage = True
                        usage_location = "response_metadata"
            
            # Location 2: Direct attributes on chunk
            if not chunk_has_usage:
                for attr_name in ['usage', 'token_usage', 'usageMetadata', 'usage_metadata']:
                    if hasattr(chunk, attr_name):
                        usage_attr = getattr(chunk, attr_name)
                        _log_debug("llm_wrapper.py:stream:chunk_usage_attr", "Found usage attribute on chunk", {
                            "chunk_idx": chunk_count,
                            "attr_name": attr_name
                        }, "H")
                        if usage_attr:
                            chunk_has_usage = True
                            usage_location = f"chunk.{attr_name}"
                            break
            
            # Location 3: Check chunk's __dict__ for any usage-related keys
            if not chunk_has_usage and hasattr(chunk, '__dict__'):
                chunk_dict = chunk.__dict__
                for key in chunk_dict.keys():
                    if ('usage' in key.lower() or 'token' in key.lower()) and chunk_dict[key]:
                        _log_debug("llm_wrapper.py:stream:chunk_dict_usage", "Found usage-related key in chunk.__dict__", {
                            "chunk_idx": chunk_count,
                            "key": key
                        }, "H")
                        chunk_has_usage = True
                        usage_location = f"chunk.__dict__['{key}']"
                        break
            
            if chunk_has_usage:
                token_usage_chunk = chunk
                token_usage_found = True
                _log_debug("llm_wrapper.py:stream:found_token_chunk", "Found token usage in chunk", {
                    "chunk_idx": chunk_count,
                    "location": usage_location
                }, "H")
        
        _log_debug("llm_wrapper.py:stream:after_streaming", "After streaming", {
            "chunk_count": chunk_count,
            "token_usage_found": token_usage_found
        }, "H")
        
        # Track token usage if found during streaming
        if token_usage_found and token_usage_chunk:
            _log_debug("llm_wrapper.py:stream:tracking_found_chunk", "Tracking token usage from chunk", {
                "chunk_type": type(token_usage_chunk).__name__
            }, "H")
            self._track_token_usage(token_usage_chunk)
        elif last_chunks:
            # If no token usage found in chunks, try last chunks to find any metadata
            for chunk in reversed(last_chunks):
                if hasattr(chunk, 'response_metadata'):
                    metadata = chunk.response_metadata
                    _log_debug("llm_wrapper.py:stream:checking_chunk", "Checking chunk for token info", {
                        "chunk_type": type(chunk).__name__,
                        "has_metadata": bool(metadata),
                        "metadata_keys": list(metadata.keys()) if isinstance(metadata, dict) else "not_dict"
                    }, "H")
                    # Check for any token-related keys
                    if metadata and isinstance(metadata, dict):
                        usage_keys = ['usage', 'token_usage', 'token_count', 'tokens', 'usageMetadata', 'usage_metadata']
                        if any(key in metadata for key in usage_keys):
                            _log_debug("llm_wrapper.py:stream:found_metadata_in_chunk", "Found metadata in chunk", {
                                "chunk_type": type(chunk).__name__,
                                "metadata_keys": list(metadata.keys())
                            }, "H")
                            self._track_token_usage(chunk)
                            break
            else:
                # No token usage found in any chunk
                chunk_metadatas = []
                for idx, chunk in enumerate(last_chunks):
                    if hasattr(chunk, 'response_metadata'):
                        metadata = chunk.response_metadata
                        chunk_metadatas.append({
                            "idx": idx,
                            "keys": list(metadata.keys()) if isinstance(metadata, dict) else "not_dict",
                            "preview": str(metadata)[:200] if metadata else None
                        })
                _log_debug("llm_wrapper.py:stream:no_token_info", "No token usage info found in any chunk", {
                    "chunk_count": chunk_count,
                    "last_chunks_metadata": chunk_metadatas
                }, "H")
    
    def _track_token_usage(self, response: Any):
        """
        Extract and track token usage from LLM response.
        
        Args:
            response: LLM response object
        """
        _log_debug("llm_wrapper.py:_track_token_usage:entry", "_track_token_usage() called", {
            "has_token_tracker": hasattr(self, 'token_tracker'),
            "model_name": getattr(self, 'model_name', 'unknown')
        }, "F")
        
        try:
            if not hasattr(self, 'token_tracker'):
                _log_debug("llm_wrapper.py:_track_token_usage:no_tracker", "No token_tracker attribute", {}, "F")
                return
            
            _log_debug("llm_wrapper.py:_track_token_usage:before_extract", "Before extract_token_usage", {
                "response_type": type(response).__name__
            }, "F")
            
            # Extract token usage using the tracker's method
            token_data = self.token_tracker.extract_token_usage(
                response,
                model=getattr(self, 'model_name', 'unknown'),
                context=getattr(self, 'context', 'unknown')
            )
            
            _log_debug("llm_wrapper.py:_track_token_usage:after_extract", "After extract_token_usage", {
                "token_data": token_data,
                "has_data": token_data is not None
            }, "F")
            
            # Track if we have any tokens (input or output)
            if token_data and (token_data.get("input_tokens", 0) > 0 or token_data.get("output_tokens", 0) > 0):
                _log_debug("llm_wrapper.py:_track_token_usage:before_track", "Before track_llm_call", {
                    "input_tokens": token_data.get("input_tokens", 0),
                    "output_tokens": token_data.get("output_tokens", 0)
                }, "F")
                
                # Track the call
                self.token_tracker.track_llm_call(
                    model=getattr(self, 'model_name', 'unknown'),
                    input_tokens=token_data.get("input_tokens", 0),
                    output_tokens=token_data.get("output_tokens", 0),
                    context=getattr(self, 'context', 'unknown'),
                    workflow_id=getattr(self, 'workflow_id', None),
                )
                
                _log_debug("llm_wrapper.py:_track_token_usage:after_track", "After track_llm_call", {
                    "history_count": len(self.token_tracker.token_usage_history)
                }, "F")
            else:
                _log_debug("llm_wrapper.py:_track_token_usage:no_tokens", "No tokens to track", {
                    "token_data": token_data
                }, "F")
        except Exception as e:
            _log_debug("llm_wrapper.py:_track_token_usage:error", "Error in _track_token_usage", {
                "error": str(e),
                "error_type": type(e).__name__
            }, "F")
            # Don't fail if tracking fails, but log it properly
            logger.warning(f"Failed to track token usage: {e}", exc_info=True)
    
    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to wrapped LLM."""
        return getattr(self.llm, name)
