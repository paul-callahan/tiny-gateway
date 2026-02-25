import pytest
from pydantic import ValidationError

from tiny_gateway.main import ConfigLoadError, create_application
from tiny_gateway.models.config_models import AppConfig, ProxyConfig


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


def test_app_config_rejects_duplicate_user_names():
    config_data = {
        "tenants": [{"id": "tenant-a"}],
        "users": [
            {"name": "alice", "password": "secret1", "tenant_id": "tenant-a", "roles": ["viewer"]},
            {"name": "alice", "password": "secret2", "tenant_id": "tenant-a", "roles": ["viewer"]},
        ],
        "roles": {"viewer": [{"resource": "graph", "actions": ["read"]}]},
        "proxy": [],
    }

    with pytest.raises(ValidationError, match="duplicate user name 'alice'"):
        AppConfig.from_dict(config_data)


def test_proxy_config_rejects_empty_endpoint():
    with pytest.raises(ValidationError, match="endpoint must not be empty"):
        ProxyConfig(endpoint="", target="http://localhost:8080/")


def test_proxy_config_rejects_empty_target():
    with pytest.raises(ValidationError, match="target must not be empty"):
        ProxyConfig(endpoint="/api/svc", target="")


def test_proxy_config_rejects_non_http_target():
    with pytest.raises(ValidationError, match="must be an HTTP or HTTPS URL"):
        ProxyConfig(endpoint="/api/svc", target="file:///etc/passwd")


def test_proxy_config_rejects_target_without_hostname():
    with pytest.raises(ValidationError, match="must include a hostname"):
        ProxyConfig(endpoint="/api/svc", target="http://")


def test_proxy_config_accepts_valid_http_target():
    proxy = ProxyConfig(endpoint="/api/svc", target="http://backend:8080/")
    assert proxy.target == "http://backend:8080/"


def test_proxy_config_accepts_valid_https_target():
    proxy = ProxyConfig(endpoint="/api/svc", target="https://backend.example.com/api")
    assert proxy.target == "https://backend.example.com/api"


def test_app_config_rejects_root_endpoint():
    config_data = {
        "tenants": [],
        "users": [],
        "roles": {},
        "proxy": [{"endpoint": "/", "target": "http://backend:8080/"}],
    }

    with pytest.raises(ValidationError, match="would capture all traffic"):
        AppConfig.from_dict(config_data)


def test_app_config_rejects_endpoint_conflicting_with_gateway_api():
    config_data = {
        "tenants": [],
        "users": [],
        "roles": {},
        "proxy": [{"endpoint": "/_gateway", "target": "http://backend:8080/"}],
    }

    with pytest.raises(ValidationError, match="conflicts with reserved gateway path"):
        AppConfig.from_dict(config_data)


def test_app_config_rejects_endpoint_conflicting_with_health():
    config_data = {
        "tenants": [],
        "users": [],
        "roles": {},
        "proxy": [{"endpoint": "/health", "target": "http://backend:8080/"}],
    }

    with pytest.raises(ValidationError, match="conflicts with reserved gateway path"):
        AppConfig.from_dict(config_data)


def test_app_config_allows_non_conflicting_endpoint():
    config_data = {
        "tenants": [],
        "users": [],
        "roles": {},
        "proxy": [{"endpoint": "/api/service", "target": "http://backend:8080/"}],
    }

    config = AppConfig.from_dict(config_data)
    assert len(config.proxy) == 1


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


def test_create_application_fails_on_permission_error(monkeypatch, tmp_path):
    config_path = tmp_path / "unreadable-config.yml"
    config_path.write_text("tenants: []", encoding="utf-8")
    config_path.chmod(0o000)

    monkeypatch.setenv("CONFIG_FILE", str(config_path))

    with pytest.raises(ConfigLoadError, match="permissions"):
        create_application()

    # Restore permissions so tmp_path cleanup works
    config_path.chmod(0o644)


def test_create_application_fails_on_invalid_yaml(monkeypatch, tmp_path):
    config_path = tmp_path / "bad-yaml.yml"
    config_path.write_text("tenants: [\n", encoding="utf-8")

    monkeypatch.setenv("CONFIG_FILE", str(config_path))

    with pytest.raises(ConfigLoadError, match="invalid YAML syntax"):
        create_application()
