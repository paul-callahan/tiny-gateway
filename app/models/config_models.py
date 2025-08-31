import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

@dataclass
class Tenant:
    id: str

@dataclass
class ProxyConfig:
    endpoint: str
    target: str
    rewrite: str = ""
    change_origin: bool = False

@dataclass
class User:
    name: str
    password: str
    tenant_id: str
    roles: List[str] = field(default_factory=list)

@dataclass
class Permission:
    resource: str
    actions: List[str]

@dataclass
class AppConfig:
    tenants: List[Tenant] = field(default_factory=list)
    proxy: List[ProxyConfig] = field(default_factory=list)
    users: List[User] = field(default_factory=list)
    roles: Dict[str, List[Permission]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, config_dict: dict) -> 'AppConfig':
        # Extract tenants
        tenants = [
            Tenant(id=tenant["id"])
            for tenant in config_dict.get("tenants", [])
            if isinstance(tenant, dict) and "id" in tenant
        ]
        
        # Extract proxy configs
        proxy_configs = []
        for i, proxy in enumerate(config_dict.get("proxy", [])):
            if not isinstance(proxy, dict):
                logger.error("Skipping proxy config #%d: expected dict, got %s", 
                           i, type(proxy).__name__)
                continue
            try:
                proxy_configs.append(ProxyConfig(
                    endpoint=proxy.get("endpoint", ""),
                    target=proxy.get("target", ""),
                    rewrite=proxy.get("rewrite", ""),
                    change_origin=proxy.get("change_origin", False)
                ))
            except Exception as e:
                logger.error("Error creating proxy config from %s: %s", proxy, str(e))
        
        # Extract users with tenant validation
        users = []
        for i, user in enumerate(config_dict.get("users", [])):
            if not isinstance(user, dict):
                logger.error("Skipping user #%d: expected dict, got %s", 
                           i, type(user).__name__)
                continue
                
            if "tenant_id" not in user:
                logger.error("User %s is missing required field 'tenant_id' - skipping user", 
                           user.get('name', f'at index {i}'))
                continue
                
            try:
                users.append(User(
                    name=user["name"],
                    password=user["password"],
                    roles=user.get("roles", []),
                    tenant_id=user["tenant_id"]
                ))
            except Exception as e:
                logger.error("Error creating user from %s: %s", user, str(e))
        
        # Extract roles
        roles = {}
        for role_name, permissions in config_dict.get("roles", {}).items():
            if not isinstance(permissions, list):
                logger.error("Skipping role '%s': expected list of permissions, got %s", 
                           role_name, type(permissions).__name__)
                continue
                
            role_permissions = []
            for i, perm in enumerate(permissions):
                if not isinstance(perm, dict):
                    logger.error("Skipping permission #%d in role '%s': expected dict, got %s", 
                               i, role_name, type(perm).__name__)
                    continue
                    
                try:
                    role_permissions.append(Permission(
                        resource=perm.get("resource", ""),
                        actions=perm.get("actions", [])
                    ))
                except Exception as e:
                    logger.error("Error creating permission %s in role '%s': %s", 
                               perm, role_name, str(e))
                    
            if role_permissions:  # Only add role if it has valid permissions
                roles[role_name] = role_permissions
                
        return cls(
            tenants=tenants,
            proxy=proxy_configs,
            users=users,
            roles=roles
        )
