# Simple API Gateway (Development Only)

A lightweight multi-tenant API gateway service, designed exclusively for development and testing purposes. This service provides authentication, authorization, and request routing for microservices in a development environment, especially docker-compose environments.

## ⚠️ Important Notice
This service is **not intended for production use**. It's designed specifically for development and testing environments. Do not deploy this to production.

## Features

- 🔐 JWT-based authentication
- 👥 Role-based access control (RBAC)
- 🏢 Multi-tenant architecture with tenant isolation
- 🔄 Request proxying to backend services
- 🏗️ Simple YAML-based configuration

## Prerequisites

- Python 3.8+
- pip (Python package manager)
- Virtual environment (recommended)

## Environment Variables

- `CONFIG_FILE`: Path to the configuration file (default: `config.yml` in the project root)
- `SECRET_KEY`: Secret key for JWT token signing (default: a development key)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: JWT token expiration time in minutes (default: 30)

## Getting Started

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd tiny-gateway
   ```

2. **Set up a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -e .
   ```

4. **Configure the service**
   Edit the `config.yml` file to set up your routes, users, and permissions.

5. **Run the service**
   ```bash
   uvicorn main:app --reload
   ```
   The API will be available at `http://localhost:8000`

## Multi-Tenant Architecture

The API Gateway supports multi-tenancy, where each user is associated with a single tenant. This provides logical isolation between different tenants' data and operations.

### Key Concepts

- **Tenant**: A logical group of users and resources
- **Tenant ID**: Unique identifier for each tenant
- **Tenant Isolation**: Users can only access resources within their assigned tenant

### Configuration

Edit `config.yml` to configure:

- **Tenants**: Define your tenant IDs
  ```yaml
  tenants:
    - id: tenant-1
    - id: tenant-2
  ```

- **Users**: Assign users to specific tenants
  ```yaml
  users:
    - name: user1
      password: pass123
      roles: [user]
      tenant_id: tenant-1  # Required field
  ```

- **Roles**: Define permissions per tenant
  ```yaml
  roles:
    admin:
      - resource: "*"
        actions: [read, write, create, delete]
    user:
      - resource: "data"
        actions: [read]
  ```

- **Proxies**: Configure request routing to backend services
  ```yaml
  proxy:
    - endpoint: /api/data
      target: http://backend-service/
      rewrite: ""  # Currently unused, kept for future compatibility
      change_origin: true  # If true, updates the Host header to match target
  ```

  The proxy will forward requests from `{endpoint}/*` to `{target}/*` with the same path. For example, a request to `/api/data/items` will be forwarded to `http://backend-service/api/data/items`.

### Tenant ID in JWT Tokens

Each JWT token includes the user's `tenant_id` in its payload. Backend services can use this to enforce tenant isolation at the data access layer.

Example JWT payload:
```json
{
  "sub": "username",
  "roles": ["user"],
  "tenant_id": "tenant-1",
  "exp": 1234567890
}
```

Example configuration:

```yaml
users:
  - name: admin
    password: adminpass
    roles: [admin]
    tenant_id: test-tenant

roles:
  admin:
    - resource: "*"
      actions: [read, write, create, delete]

proxy:
  - endpoint: /api/service
    target: http://localhost:3000
    rewrite: ""
    change_origin: true
```

## API Endpoints

- `POST /api/v1/auth/login` - Obtain JWT token with tenant context
- `GET /api/v1/users/me` - Get current user information including tenant ID

## Running Tests

```bash
pytest tests/ -v
```

## Development

### Project Structure

```
.
├── app/                      # Application code
│   ├── api/                  # API routes
│   ├── core/                 # Core functionality
│   ├── models/               # Data models
│   └── config/               # Configuration
├── tests/                    # Test files
├── config.yml                # Main configuration
└── main.py                  # Application entry point
```

### Dependencies

- FastAPI - Web framework
- Uvicorn - ASGI server
- Pydantic - Data validation
- PyYAML - YAML configuration parsing
- pytest - Testing framework

## License

This project is for development use only. See LICENSE for more information.
