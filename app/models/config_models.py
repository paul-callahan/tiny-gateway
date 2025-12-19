import logging
from pydantic import BaseModel, Field, ValidationError
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class Tenant(BaseModel):
    id: str

class ProxyConfig(BaseModel):
    endpoint: str
    target: str
    rewrite: str = ""
    change_origin: bool = False
    required_resource: Optional[str] = None
    required_actions: List[str] = Field(default_factory=list)

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
