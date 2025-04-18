```python
# src/core/config_manager.py
import configparser
import os
import sys
from pathlib import Path

# Default configuration values
DEFAULT_CONFIG = {
    'API': {
        'OPENAI_API_KEY': '', # Default is empty, rely on env var
        'DEFAULT_MODEL': 'gpt-3.5-turbo'
    },
    'Paths': {
        # These are less relevant now with resource_path and QFileDialog defaults
    },
    'Defaults': {
        'NODE_COLOR': 'skyblue',
        'MAX_EXECUTION_DEPTH': '25',
        'PREFER_RELATIVE_PATHS': 'True'
    },
    'Execution': {
        # Add execution defaults if needed
    }
}

def get_base_path():
    """ Get base path for bundled executable or running script """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running as bundled executable (PyInstaller)
        return os.path.dirname(sys.executable)
    else:
        # Running as script - find project root relative to this file
        # Assuming this file is in src/core, go up 3 levels
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

def load_config(default_config_filename='settings.ini'):
    """
    Loads configuration, prioritizing user file next to exe/script,
    then bundled file, then hardcoded defaults.
    """
    config = configparser.ConfigParser()
    config.read_dict(DEFAULT_CONFIG) # Load hardcoded defaults first

    base_path = get_base_path()
    config_filename = default_config_filename

    # Paths to check for the config file
    user_config_path = os.path.join(base_path, config_filename)
    # Path relative to base_path where PyInstaller puts bundled config ('config' dir)
    bundled_config_path_rel = os.path.join('config', config_filename)
    bundled_config_path_abs = os.path.join(base_path, bundled_config_path_rel)

    config_found_path = None

    # 1. Check for user config next to executable/script
    if os.path.exists(user_config_path):
         config_found_path = user_config_path
         print(f"Loading user config from: {user_config_path}")
    # 2. Check for bundled config (only if running bundled)
    elif getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS') and os.path.exists(bundled_config_path_abs):
         config_found_path = bundled_config_path_abs
         print(f"Loading bundled config from: {bundled_config_path_abs}")
    # 3. Alternative: Check project root when running as script (if different from base_path logic)
    # elif not getattr(sys, 'frozen', False):
    #    script_root_config = os.path.join(get_base_path(), 'config', config_filename) # Assumes config dir at root
    #    if os.path.exists(script_root_config):
    #         config_found_path = script_root_config
    #         print(f"Loading development config from: {script_root_config}")


    if config_found_path:
         try:
              # Read file, overriding defaults
              config.read(config_found_path, encoding='utf-8')
         except Exception as e:
              print(f"Warning: Failed to read config file at {config_found_path}: {e}. Using defaults.")
    else:
         print(f"Warning: Config file '{config_filename}' not found in expected locations. Using defaults.")
         # Consider creating a default user config file here if desired

    return config

# Example of accessing config within other modules:
# from src.core.config_manager import load_config
# CONFIG = load_config()
# api_key = os.getenv('OPENAI_API_KEY') or CONFIG.get('API', 'OPENAI_API_KEY', fallback=None)
# max_depth = CONFIG.getint('Defaults', 'MAX_EXECUTION_DEPTH', fallback=20)
# prefer_relative = CONFIG.getboolean('Defaults', 'PREFER_RELATIVE_PATHS', fallback=True)
``` 
