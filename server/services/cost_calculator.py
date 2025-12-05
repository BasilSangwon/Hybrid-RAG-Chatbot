# Cost Calculator for Gemini Models
# Pricing Source: Google Cloud Vertex AI / AI Studio Pricing (Estimates)
# Unit: USD per 1M tokens

PRICING_MAP = {
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.5-pro": {"input": 3.50, "output": 10.50},
    "gemini-1.0-pro": {"input": 0.50, "output": 1.50},
    "gemini-2.0-flash": {"input": 0.075, "output": 0.30}, # Assumed similar to 1.5 Flash
}

def calculate_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate estimated cost in USD based on model name and token usage.
    """
    # Normalize model name (handle versions like gemini-1.5-flash-001)
    base_model = "unknown"
    for key in PRICING_MAP:
        if key in model_name.lower():
            base_model = key
            break
    
    if base_model == "unknown":
        return 0.0
    
    rates = PRICING_MAP[base_model]
    input_cost = (input_tokens / 1_000_000) * rates["input"]
    output_cost = (output_tokens / 1_000_000) * rates["output"]
    
    return round(input_cost + output_cost, 6)
