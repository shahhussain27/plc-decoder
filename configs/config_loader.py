"""
ConfigLoader – loads and validates JSON PLC format config files.
"""

import json
from pathlib import Path
from typing import Optional
from utils.logger import AppLogger

log = AppLogger()

TEMPLATES_DIR = Path(__file__).parent / "plc_templates"

REQUIRED_KEYS = {"format_name", "fields", "packet_definition"}


def load_config(config_path: str | Path) -> dict:
    """Load a JSON config file and return the parsed dict."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        config = json.load(f)
    _validate_config(config, path.name)
    return config


def load_template(template_name: str) -> dict:
    """Load a named template from the plc_templates directory."""
    path = TEMPLATES_DIR / f"{template_name}.json"
    return load_config(path)


def save_config(config: dict, output_path: str | Path):
    """Save config dict to a JSON file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    log.info("Config saved: %s", path)


def _validate_config(config: dict, name: str):
    """Basic structural validation of a config dict."""
    missing = REQUIRED_KEYS - set(config.keys())
    if missing:
        log.warning("Config '%s' is missing keys: %s", name, missing)
    fields = config.get("fields", [])
    if not isinstance(fields, list):
        raise ValueError(f"'fields' must be a list in config '{name}'")
    for i, fdef in enumerate(fields):
        if "name" not in fdef or "word_offset" not in fdef:
            log.warning("Config '%s': field[%d] missing 'name' or 'word_offset'.", name, i)
