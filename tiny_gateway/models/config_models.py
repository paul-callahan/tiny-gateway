import logging
from urllib.parse import urlparse

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from typing import List, Dict, Any

from tiny_gateway.config.settings import settings

logger = logging.getLogger(__name__)

RESERVED_PATH_PREFIXES = (
    settings.API_V1_STR,
    f"{settings.API_V1_STR}/openapi.json",
    "/health",
    "/test_login",
    "/docs",
)


class Tenant(BaseModel):
    id: str

class ProxyConfig(BaseModel):
    endpoint: str
    target: str
    resource: str | None = None
    rewrite: str = ""
    change_origin: bool = False

    @field_validator("endpoint")
    @classmethod
    def endpoint_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("endpoint must not be empty")
        return v

    @field_validator("target")
    @classmethod
    def target_must_be_valid_http_url(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("target must not be empty")
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"target must be an HTTP or HTTPS URL, got '{v}'")
        if not parsed.hostname:
            raise ValueError(f"target must include a hostname, got '{v}'")
        return v

class User(BaseModel):
    name: str
    password: str
    tenant_id: str
    roles: List[str] = Field(default_factory=list)

class Permission(BaseModel):
    resource: str
    actions: List[str]

class AppConfig(BaseModel):
    tenants: List[Tenant] = Field(default_factory=list)
    proxy: List[ProxyConfig] = Field(default_factory=list)
    users: List[User] = Field(default_factory=list)
    roles: Dict[str, List[Permission]] = Field(default_factory=dict)
    default_config: bool = False

    @model_validator(mode="after")
    def validate_user_references(self) -> "AppConfig":
        """Ensure user references to tenants and roles are valid."""
        tenant_ids = {tenant.id for tenant in self.tenants}
        defined_roles = set(self.roles.keys())
        errors: list[str] = []

        # Check for duplicate user names
        seen_names: set[str] = set()
        for user in self.users:
            if user.name in seen_names:
                errors.append(f"duplicate user name '{user.name}'")
            seen_names.add(user.name)

        for user in self.users:
            if tenant_ids and user.tenant_id not in tenant_ids:
                errors.append(
                    f"user '{user.name}' references undefined tenant_id '{user.tenant_id}'"
                )

            missing_roles = [role for role in user.roles if role not in defined_roles]
            if missing_roles:
                missing_roles_str = ", ".join(missing_roles)
                errors.append(
                    f"user '{user.name}' references undefined roles: {missing_roles_str}"
                )

        if errors:
            raise ValueError("; ".join(errors))

        return self

    @model_validator(mode="after")
    def validate_proxy_endpoints(self) -> "AppConfig":
        """Warn about proxy endpoints that shadow gateway routes."""
        for proxy in self.proxy:
            normalized = proxy.endpoint.strip().rstrip("/") or "/"
            if normalized == "/":
                raise ValueError(
                    f"proxy endpoint '/' would capture all traffic and shadow gateway API routes"
                )
            for reserved in RESERVED_PATH_PREFIXES:
                if reserved.startswith(normalized + "/") or reserved == normalized:
                    raise ValueError(
                        f"proxy endpoint '{proxy.endpoint}' conflicts with reserved gateway path '{reserved}'"
                    )
        return self

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'AppConfig':
        """
        Create AppConfig from a dictionary, typically loaded from YAML.
        
        Args:
            config_dict: Configuration dictionary
            
        Returns:
            AppConfig instance with parsed and validated configuration
            
        Raises:
            ValidationError: If the configuration data is invalid
        """
        try:
            return cls.model_validate(config_dict)
        except ValidationError as e:
            logger.error("Configuration validation failed: %s", str(e))
            raise
