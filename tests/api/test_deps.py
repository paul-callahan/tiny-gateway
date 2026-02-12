from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from tiny_gateway.api.deps import get_config
from tiny_gateway.models.config_models import AppConfig


def test_get_config_reads_from_app_state():
    app = FastAPI()
    app.state.config = AppConfig.from_dict(
        {
            "tenants": [{"id": "tenant-a"}],
            "users": [],
            "roles": {},
            "proxy": [],
        }
    )

    @app.get("/config-check")
    def config_check(config: AppConfig = Depends(get_config)):
        return {"tenant_count": len(config.tenants)}

    with TestClient(app) as client:
        response = client.get("/config-check")

    assert response.status_code == 200
    assert response.json() == {"tenant_count": 1}
