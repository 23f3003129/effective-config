from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any
import os

import yaml
from dotenv import load_dotenv

# 1. Base defaults
def get_base_defaults() -> Dict[str, Any]:
    return {
        "port": 8000,
        "workers": 1,
        "debug": False,
        "log_level": "info",
        "api_key": "default-secret-000",
    }

# 2. Type coercion helper
def coerce_value(key: str, value: str):
    if key in ["port", "workers"]:
        return int(value)
    if key == "debug":
        lower = value.lower()
        return lower in ["true", "1", "yes", "on"]
    return str(value)

# 3. Load YAML layer
def load_yaml_config(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}
    result = {}
    for k, v in data.items():
        result[k] = coerce_value(k, str(v))
    return result

# 4. Load .env layer (with alias NUM_WORKERS -> workers)
def load_dotenv_config(path: str = ".env") -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    load_dotenv(path)
    result = {}

    app_debug = os.getenv("APP_DEBUG")
    if app_debug is not None:
        result["debug"] = coerce_value("debug", app_debug)

    app_api_key = os.getenv("APP_API_KEY")
    if app_api_key is not None:
        result["api_key"] = coerce_value("api_key", app_api_key)

    num_workers = os.getenv("NUM_WORKERS")
    if num_workers is not None:
        result["workers"] = coerce_value("workers", num_workers)

    return result

# 5. Load OS env APP_* layer
def load_os_env_config() -> Dict[str, Any]:
    result = {}
    for key, value in os.environ.items():
        if not key.startswith("APP_"):
            continue
        # Strip APP_ prefix
        short = key[4:].lower()  # e.g., APP_PORT -> "port"
        if short == "port":
            result["port"] = coerce_value("port", value)
        elif short == "log_level":
            result["log_level"] = coerce_value("log_level", value)
        elif short == "api_key":
            result["api_key"] = coerce_value("api_key", value)
        elif short == "debug":
            result["debug"] = coerce_value("debug", value)
        elif short == "workers":
            result["workers"] = coerce_value("workers", value)
        # ignore unknown APP_* keys for now
    return result

# 6. Merge all layers (without CLI overrides yet)
def compute_base_effective_config() -> Dict[str, Any]:
    config = get_base_defaults()

    yaml_cfg = load_yaml_config("config.development.yaml")
    config.update(yaml_cfg)

    dotenv_cfg = load_dotenv_config(".env")
    config.update(dotenv_cfg)

    os_cfg = load_os_env_config()
    config.update(os_cfg)

    return config

# Initialize FastAPI
app = FastAPI()

# 7. CORS setup: allow all origins so grader page can call it
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or restrict to specific origin if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 8. Endpoint with CLI overrides via ?set=key=value
@app.get("/effective-config")
def get_effective_config(set: List[str] = Query(default=[])):
    # Start from merged config (4 layers)
    config = compute_base_effective_config()

    # Apply CLI overrides from query params
    for item in set:
        # Expect "key=value"
        if "=" not in item:
            continue
        k, v = item.split("=", 1)  # split only on first "="
        k = k.strip()
        v = v.strip()
        if not k:
            continue
        # Coerce based on key
        config[k] = coerce_value(k, v)

    # Prepare response with masked api_key
    response_config = config.copy()
    if "api_key" in response_config:
        response_config["api_key"] = "****"

    return response_config