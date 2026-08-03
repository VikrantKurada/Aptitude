import tomllib
from pathlib import Path

DEFAULT_MODELS = {"claude": "claude-sonnet-5", "gemini": "gemini-2.0-flash",
                  "nvidia": "meta/llama-3.1-70b-instruct",
                  "openai": "gpt-4o-mini", "ollama": "llama3.1"}
_KEY_ENV = {"claude": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY",
            "nvidia": "NVIDIA_API_KEY", "openai": "OPENAI_API_KEY"}
DEFAULTS = {"provider": None, "model": None, "format": "claude-skill",
            "out": "./out", "max_tokens_budget": None, "cache": ".aptitude-cache"}

def api_key_for(provider: str, env: dict) -> str | None:
    return env.get(_KEY_ENV.get(provider, ""), None) or None

def default_provider(env: dict) -> str:
    return "claude" if env.get("ANTHROPIC_API_KEY") else "ollama"

def resolve_config(cli: dict, env: dict, toml_path: Path | None) -> dict:
    cfg = dict(DEFAULTS)
    if toml_path and Path(toml_path).exists():
        cfg.update({k: v for k, v in tomllib.loads(Path(toml_path).read_text()).items()})
    env_cfg = {"provider": env.get("APTITUDE_PROVIDER"), "model": env.get("APTITUDE_MODEL")}
    cfg.update({k: v for k, v in env_cfg.items() if v is not None})
    cfg.update({k: v for k, v in cli.items() if v is not None})
    return cfg
