



"""Configuration for Ambulance Green Corridor AI with Custom Cerebras Model"""

import os
from portia import Config
from src.models.cerebras_model import CerebrasModel

def setup_cerebras_config():
    """Set up Portia configuration with custom Cerebras model"""
    
    # Verify Cerebras API key exists
    cerebras_api_key = os.environ.get("CEREBRAS_API_KEY")
    if not cerebras_api_key:
        raise ValueError("CEREBRAS_API_KEY not found in environment variables")
    
    # Create custom Cerebras model instance
    cerebras_model = CerebrasModel()
    
    # Set up Portia config with custom model
    config = Config(
        default_model=cerebras_model,  # Use our custom model instance directly
        log_level="INFO"
    )
    
    print("🧠 Cerebras custom model configured successfully!")
    print(f"✅ Using model: {cerebras_model.model_name}")
    
    return config, cerebras_model

def get_emergency_prompt_settings():
    """Get emergency-specific prompt settings"""
    return {
        "temperature": 0.1,  # Low temperature for consistent emergency responses
        "max_tokens": 2048,
        "emergency_context": """You are an expert emergency response AI for ambulance green corridor management.
        Your responses must be accurate, fast, and focused on saving lives.
        Always prioritize patient safety and emergency protocols."""
    }

def validate_environment():
    """Validate all required environment variables are present"""
    required_vars = [
        "CEREBRAS_API_KEY",
        "TAVILY_API_KEY", 
        "GOOGLE_MAPS_API_KEY"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    print("✅ All required environment variables found!")
    return True