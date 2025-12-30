"""
Pricing configuration for LLM models.

Last updated: December 2025
Prices are per 1K tokens in USD.

Reference sources:
- Anthropic: https://www.anthropic.com/pricing
- OpenAI: https://openai.com/pricing
- AWS Bedrock: https://aws.amazon.com/bedrock/pricing/
- Google Gemini: https://ai.google.dev/pricing
"""

from typing import Dict, Optional

# Pricing table for LLM models (per 1K tokens)
# Prices are in USD and should be updated regularly
PRICING_TABLE: Dict[str, Dict[str, float]] = {
    # Anthropic Claude models
    "claude-3-5-sonnet-20241022": {
        "input_price_per_1k_tokens": 0.003,
        "output_price_per_1k_tokens": 0.015,
        "currency": "USD",
    },
    "claude-3-5-haiku-20241022": {
        "input_price_per_1k_tokens": 0.00025,
        "output_price_per_1k_tokens": 0.00125,
        "currency": "USD",
    },
    "claude-3-opus-20240229": {
        "input_price_per_1k_tokens": 0.015,
        "output_price_per_1k_tokens": 0.075,
        "currency": "USD",
    },
    "claude-3-sonnet-20240229": {
        "input_price_per_1k_tokens": 0.003,
        "output_price_per_1k_tokens": 0.015,
        "currency": "USD",
    },
    "claude-3-haiku-20240307": {
        "input_price_per_1k_tokens": 0.00025,
        "output_price_per_1k_tokens": 0.00125,
        "currency": "USD",
    },
    
    # OpenAI GPT models
    "gpt-4": {
        "input_price_per_1k_tokens": 0.03,
        "output_price_per_1k_tokens": 0.06,
        "currency": "USD",
    },
    "gpt-4-turbo": {
        "input_price_per_1k_tokens": 0.01,
        "output_price_per_1k_tokens": 0.03,
        "currency": "USD",
    },
    "gpt-4o": {
        "input_price_per_1k_tokens": 0.005,
        "output_price_per_1k_tokens": 0.015,
        "currency": "USD",
    },
    "gpt-3.5-turbo": {
        "input_price_per_1k_tokens": 0.0005,
        "output_price_per_1k_tokens": 0.0015,
        "currency": "USD",
    },
    
    # AWS Bedrock models (Anthropic via Bedrock)
    "us.anthropic.claude-3-5-sonnet-20241022-v1:0": {
        "input_price_per_1k_tokens": 0.003,
        "output_price_per_1k_tokens": 0.015,
        "currency": "USD",
    },
    "us.anthropic.claude-3-5-haiku-20241022-v1:0": {
        "input_price_per_1k_tokens": 0.00025,
        "output_price_per_1k_tokens": 0.00125,
        "currency": "USD",
    },
    "anthropic.claude-3-5-sonnet-20241022-v2:0": {
        "input_price_per_1k_tokens": 0.003,
        "output_price_per_1k_tokens": 0.015,
        "currency": "USD",
    },
    # Claude 4.5 models (updated December 2025)
    # AWS Bedrock pricing: https://aws.amazon.com/ko/bedrock/pricing/
    # Claude Sonnet 4.5: $3.30/1M input, $16.50/1M output (per 1K: $0.0033 input, $0.0165 output)
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0": {
        "input_price_per_1k_tokens": 0.0033,
        "output_price_per_1k_tokens": 0.0165,
        "currency": "USD",
    },
    # Claude Sonnet 4.5 - Long Context: $6.60/1M input, $24.75/1M output (per 1K: $0.0066 input, $0.02475 output)
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0-long": {
        "input_price_per_1k_tokens": 0.0066,
        "output_price_per_1k_tokens": 0.02475,
        "currency": "USD",
    },
    # Claude Haiku 4.5: $1.10/1M input, $5.50/1M output (per 1K: $0.0011 input, $0.0055 output)
    "us.anthropic.claude-haiku-4-5-20251001-v1:0": {
        "input_price_per_1k_tokens": 0.0011,
        "output_price_per_1k_tokens": 0.0055,
        "currency": "USD",
    },
    # Claude Opus 4.5: $5.50/1M input, $27.50/1M output (per 1K: $0.0055 input, $0.0275 output)
    # Released November 24, 2025
    "us.anthropic.claude-opus-4-5": {
        "input_price_per_1k_tokens": 0.0055,
        "output_price_per_1k_tokens": 0.0275,
        "currency": "USD",
    },
    # Claude 3.7 Sonnet: $3/1M input, $15/1M output (per 1K: $0.003 input, $0.015 output)
    "us.anthropic.claude-3-7-sonnet": {
        "input_price_per_1k_tokens": 0.003,
        "output_price_per_1k_tokens": 0.015,
        "currency": "USD",
    },
    
    # Google Gemini models
    "gemini-pro": {
        "input_price_per_1k_tokens": 0.0005,
        "output_price_per_1k_tokens": 0.0015,
        "currency": "USD",
    },
    "gemini-1.5-pro": {
        "input_price_per_1k_tokens": 0.00125,
        "output_price_per_1k_tokens": 0.005,
        "currency": "USD",
    },
    "gemini-1.5-flash": {
        "input_price_per_1k_tokens": 0.000075,
        "output_price_per_1k_tokens": 0.0003,
        "currency": "USD",
    },
    "gemini-3-pro-preview": {
        # Gemini 3 Pro Preview pricing (as of Dec 2025)
        # Standard mode pricing:
        # - Input: $2.00/1M tokens (prompt <= 200K tokens), $4.00/1M (prompt > 200K tokens)
        # - Output: $12.00/1M tokens (prompt <= 200K tokens), $18.00/1M (prompt > 200K tokens)
        # Using <= 200K tokens pricing as default
        # Reference: https://ai.google.dev/gemini-api/docs/pricing?hl=ko
        "input_price_per_1k_tokens": 0.002,  # $2.00/1M = $0.002/1K (prompt <= 200K)
        "output_price_per_1k_tokens": 0.012,  # $12.00/1M = $0.012/1K (prompt <= 200K)
        "currency": "USD",
        # Note: For prompts > 200K tokens, prices are:
        # - Input: $0.004/1K ($4.00/1M)
        # - Output: $0.018/1K ($18.00/1M)
    },
}


def get_model_pricing(model: str) -> Optional[Dict[str, float]]:
    """
    Get pricing information for a specific model.
    
    Args:
        model: Model name/identifier
        
    Returns:
        Dictionary with pricing information, or None if not found
    """
    # Try exact match first
    if model in PRICING_TABLE:
        return PRICING_TABLE[model]
    
    # Try partial matches (for models with version suffixes)
    # Match patterns like "us.anthropic.claude-sonnet-4-5-20250929-v1:0" to "us.anthropic.claude-3-5-sonnet-20241022-v1:0"
    for key, value in PRICING_TABLE.items():
        if model.startswith(key) or key in model:
            return value
    
    # Try to match Bedrock model names by extracting base model name
    # e.g., "us.anthropic.claude-sonnet-4-5-20250929-v1:0" -> match "claude-3-5-sonnet" or "claude-sonnet"
    if "anthropic.claude" in model or "us.anthropic.claude" in model:
        # Extract model family (sonnet, haiku, opus)
        if "sonnet" in model.lower():
            # Try to match any sonnet variant
            for key, value in PRICING_TABLE.items():
                if "sonnet" in key.lower() and "anthropic" in key.lower():
                    return value
        elif "haiku" in model.lower():
            # Try to match any haiku variant
            for key, value in PRICING_TABLE.items():
                if "haiku" in key.lower() and "anthropic" in key.lower():
                    return value
        elif "opus" in model.lower():
            # Try to match any opus variant
            for key, value in PRICING_TABLE.items():
                if "opus" in key.lower() and "anthropic" in key.lower():
                    return value
    
    return None


def update_pricing(model: str, input_price: float, output_price: float, currency: str = "USD"):
    """
    Update pricing for a model.
    
    Args:
        model: Model name
        input_price: Price per 1K input tokens
        output_price: Price per 1K output tokens
        currency: Currency code (default: USD)
    """
    PRICING_TABLE[model] = {
        "input_price_per_1k_tokens": input_price,
        "output_price_per_1k_tokens": output_price,
        "currency": currency,
    }
