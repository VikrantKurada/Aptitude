# tests/test_config.py
from aptitude.config import resolve_config, default_provider, api_key_for

def test_cli_overrides_env_and_toml(tmp_path):
    toml = tmp_path / "aptitude.toml"
    toml.write_text('provider = "gemini"\nmodel = "g-toml"\n')
    cfg = resolve_config(cli={"model": "cli-model"},
                         env={"APTITUDE_PROVIDER": "nvidia"},
                         toml_path=toml)
    assert cfg["model"] == "cli-model"        # CLI wins
    assert cfg["provider"] == "nvidia"        # env beats toml

def test_default_provider_prefers_claude_key():
    assert default_provider({"ANTHROPIC_API_KEY": "x"}) == "claude"
    assert default_provider({}) == "ollama"

def test_api_key_lookup():
    assert api_key_for("nvidia", {"NVIDIA_API_KEY": "k"}) == "k"
    assert api_key_for("ollama", {}) is None

def test_format_resolves_with_precedence(tmp_path):
    toml = tmp_path / "aptitude.toml"
    toml.write_text('format = "generic-prompt"\n')
    assert resolve_config({}, {}, toml)["format"] == "generic-prompt"          # from toml
    assert resolve_config({}, {"APTITUDE_FORMAT": "zip"}, toml)["format"] == "zip"  # env beats toml
    assert resolve_config({"format": "all"}, {"APTITUDE_FORMAT": "zip"}, toml)["format"] == "all"  # cli wins

def test_format_defaults_to_claude_skill():
    assert resolve_config({}, {}, None)["format"] == "claude-skill"
