"""
Application configuration module for EasyRead API.

This module handles loading and caching of application settings from YAML files.
Settings are loaded once at import time and cached for the application lifetime.
"""

import yaml
import logging
from pathlib import Path
from django.conf import settings
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Path configuration
# In Docker, config is mounted at /app/config, but BASE_DIR might be /app
# Check if config exists relative to BASE_DIR first, then fallback to parent
if (settings.BASE_DIR / 'config').exists():
    CONFIG_DIR = settings.BASE_DIR / 'config'
else:
    CONFIG_DIR = settings.BASE_DIR.parent / 'config'
SETTINGS_FILE = CONFIG_DIR / 'settings.yaml'
EASY_READ_PROMPT_FILE = CONFIG_DIR / 'easy_read.yaml'
VALIDATE_COMPLETENESS_PROMPT_FILE = CONFIG_DIR / 'validate_completeness.yaml'
REVISE_SENTENCES_PROMPT_FILE = CONFIG_DIR / 'revise_sentences.yaml'
GENERATE_IMAGE_PROMPT_FILE = CONFIG_DIR / 'generate_image.yaml'

# Default settings
DEFAULT_SETTINGS = {
    'llm_retry': {
        'max_retries': 3,
        'initial_delay': 1.0,
        'exponential_backoff': True,
        'max_delay': 10.0
    },
    'processing': {
        'timeout': 300
    },
    'logging': {
        'level': 'INFO',
        'detailed_errors': True
    }
}

# Cached settings - loaded once at import time
_settings_cache: Optional[Dict[str, Any]] = None


def _load_yaml_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """Load and parse a YAML file safely."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.warning(f"File not found: {file_path}")
        return None
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error loading {file_path}: {e}")
        return None


def _load_settings_from_file() -> Dict[str, Any]:
    """Load settings from YAML file with fallback to defaults."""
    settings_data = _load_yaml_file(SETTINGS_FILE)
    
    if settings_data is None:
        logger.warning(f"Settings file not found at {SETTINGS_FILE}, using defaults")
        return DEFAULT_SETTINGS.copy()
    
    # Merge with defaults to ensure all keys exist
    merged_settings = DEFAULT_SETTINGS.copy()
    
    # Deep merge the loaded settings with defaults
    def deep_merge(default: Dict, loaded: Dict) -> Dict:
        result = default.copy()
        for key, value in loaded.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    
    merged_settings = deep_merge(merged_settings, settings_data)
    logger.info(f"Settings loaded successfully from {SETTINGS_FILE}")
    return merged_settings


def get_settings() -> Dict[str, Any]:
    """
    Get application settings. Settings are cached after first load.
    
    Returns:
        Dict containing all application settings
    """
    global _settings_cache
    
    if _settings_cache is None:
        _settings_cache = _load_settings_from_file()
    
    return _settings_cache


def reload_settings() -> Dict[str, Any]:
    """
    Force reload settings from file. Useful for testing or configuration changes.
    
    Returns:
        Dict containing reloaded settings
    """
    global _settings_cache
    _settings_cache = None
    return get_settings()


def get_retry_config() -> Dict[str, Any]:
    """
    Get LLM retry configuration.
    
    Returns:
        Dict containing retry settings
    """
    return get_settings().get('llm_retry', DEFAULT_SETTINGS['llm_retry'])


def load_prompt_template() -> Optional[Dict[str, Any]]:
    """
    Load the Easy Read prompt template from YAML file.
    
    Returns:
        Dict containing prompt template or None if loading fails
    """
    return _load_yaml_file(EASY_READ_PROMPT_FILE)


def load_validate_completeness_prompt() -> Optional[Dict[str, Any]]:
    """Load the validate completeness prompt template."""
    return _load_yaml_file(VALIDATE_COMPLETENESS_PROMPT_FILE)


def load_revise_sentences_prompt() -> Optional[Dict[str, Any]]:
    """Load the revise sentences prompt template."""
    return _load_yaml_file(REVISE_SENTENCES_PROMPT_FILE)


def load_generate_image_prompt() -> Optional[Dict[str, Any]]:
    """Load the generate image prompt template."""
    return _load_yaml_file(GENERATE_IMAGE_PROMPT_FILE)


# Initialize settings cache at module import
get_settings()