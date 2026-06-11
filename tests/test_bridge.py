from __future__ import annotations

import pytest
import yaml

from agent_factory.bridge import load_bridge_config


def _base_spec() -> dict:
    return {
        "twin": {
            "name": "filip",
            "owner": "fszale@gmail.com",
            "kernel": {"source": "github.com/fszale/agent-kernel", "version": "v1.0.0"},
            "roles": ["principal-operator"],
            "models": {"default": {"provider": "stub", "model": "stub-fast"}},
            "autonomy": {
                "mode": "propose-then-confirm",
                "auto_allow": ["search"],
                "always_gate": ["send"],
            },
        }
    }


def _write(tmp_path, spec) -> str:
    p = tmp_path / "twin.yaml"
    p.write_text(yaml.safe_dump(spec), encoding="utf-8")
    return str(p)


def test_loads_valid_bridge(tmp_path):
    cfg = load_bridge_config(_write(tmp_path, _base_spec()))
    assert cfg.twin.name == "filip"
    assert cfg.twin.kernel.version == "v1.0.0"
    assert cfg.twin.autonomy.mode == "propose-then-confirm"


def test_version_must_be_pinned_tag(tmp_path):
    spec = _base_spec()
    spec["twin"]["kernel"]["version"] = "main"
    with pytest.raises(ValueError):
        load_bridge_config(_write(tmp_path, spec))


def test_name_pattern_enforced(tmp_path):
    spec = _base_spec()
    spec["twin"]["name"] = "Filip Twin"
    with pytest.raises(ValueError):
        load_bridge_config(_write(tmp_path, spec))


def test_full_autonomy_requires_guardrails(tmp_path):
    spec = _base_spec()
    spec["twin"]["autonomy"]["full_autonomy"] = {"enabled": True}
    with pytest.raises(ValueError):
        load_bridge_config(_write(tmp_path, spec))


def test_full_autonomy_mode_requires_optin(tmp_path):
    spec = _base_spec()
    spec["twin"]["autonomy"]["mode"] = "full-autonomy"
    with pytest.raises(ValueError):
        load_bridge_config(_write(tmp_path, spec))
