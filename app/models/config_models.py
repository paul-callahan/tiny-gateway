import logging
from pydantic import BaseModel, Field, ValidationError, model_validator
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class Tenant(BaseModel):
    id: str

class ProxyConfig(BaseModel):
    endpoint: str
    target: str
    resource: str | None = None
    rewrite: str = ""
    change_origin: bool = False

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
