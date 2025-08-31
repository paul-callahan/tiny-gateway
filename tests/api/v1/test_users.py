from fastapi import status

def test_get_current_user(client, auth_headers, test_config):
    """Test getting current user information"""
    test_user = test_config.users[0]
    response = client.get("/api/v1/users/me", headers=auth_headers)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["username"] == test_user.name
    assert set(data["roles"]) == set(test_user.roles)
    assert data["tenant_id"] == test_user.tenant_id

def test_get_current_user_unauthorized(client):
    """Test getting current user without authentication"""
    response = client.get("/api/v1/users/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
