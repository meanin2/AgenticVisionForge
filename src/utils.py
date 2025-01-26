import os
import re
from pathlib import Path
from dotenv import load_dotenv

def load_env_vars():
    """Load environment variables from .env file."""
    env_path = Path('.env')
    if env_path.exists():
        load_dotenv(env_path)

def replace_env_vars(config):
    """Recursively replace environment variables in config values."""
    if isinstance(config, dict):
        return {k: replace_env_vars(v) for k, v in config.items()}
    elif isinstance(config, list):
        return [replace_env_vars(v) for v in config]
    elif isinstance(config, str):
        # Look for ${VAR_NAME} pattern
        pattern = r'\${([^}]+)}'
        matches = re.findall(pattern, config)
        if matches:
            result = config
            for var_name in matches:
                env_value = os.getenv(var_name)
                if env_value is None:
                    raise ValueError(f"Environment variable {var_name} not found")
                result = result.replace(f"${{{var_name}}}", env_value)
            return result
        return config
    return config 