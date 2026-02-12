import pytest
from pydantic import ValidationError

from tiny_gateway.main import ConfigLoadError, create_application
from tiny_gateway.models.config_models import AppConfig


def test_app_config_rejects_user_with_unknown_tenant():
    config_data = {
        "tenants": [{"id": "tenant-a"}],
        "users": [
            {
                "name": "alice",
                "password": "secret",
                "tenant_id": "tenant-missing",
                "roles": ["viewer"],
            }
        ],
        "roles": {
            "viewer": [{"resource": "graph", "actions": ["read"]}]
        },
        "proxy": [],
    }

    with pytest.raises(ValidationError):
        AppConfig.from_dict(config_data)


def test_app_config_rejects_user_with_unknown_role():
    config_data = {
        "tenants": [{"id": "tenant-a"}],
        "users": [
            {
                "name": "alice",
                "password": "secret",
                "tenant_id": "tenant-a",
                "roles": ["missing-role"],
            }
        ],
        "roles": {
            "viewer": [{"resource": "graph", "actions": ["read"]}]
        },
        "proxy": [],
    }

    with pytest.raises(ValidationError):
        AppConfig.from_dict(config_data)


def test_create_application_fails_fast_on_invalid_config(monkeypatch, tmp_path):
    config_path = tmp_path / "invalid-config.yml"
    config_path.write_text(
        """
tenants:
  - id: tenant-a
users:
  - name: alice
    password: secret
    tenant_id: tenant-missing
    roles: [viewer]
roles:
  viewer:
    - resource: graph
      actions: [read]
proxy: []
""",
        encoding="utf-8",
    )

    monkeypatch.setenv("CONFIG_FILE", str(config_path))

    with pytest.raises(ConfigLoadError, match="validation failed"):
        create_application()
