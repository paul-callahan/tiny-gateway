from fastapi import status

def test_login_success(client, test_config):
    """Test successful login"""
    test_user = test_config.users[0]
    print(f"\nTesting login with user: {test_user}")
    print(f"Username: {test_user.name}")
    print(f"Password from config: {test_user.password}")
    
    # Print all users in config for debugging
    print("\nAll users in config:")
    for i, user in enumerate(test_config.users):
        print(f"User {i}: {user.name} (password: {user.password}, roles: {user.roles})")
    
    # Use the password from the test user object
    response = client.post(
        "/api/v1/auth/login",
        data={"username": test_user.name, "password": test_user.password},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    print(f"\nResponse status: {response.status_code}")
    print(f"Response content: {response.text}")
    
    assert response.status_code == status.HTTP_200_OK, f"Expected 200 OK, got {response.status_code}. Response: {response.text}"
    assert "access_token" in response.json(), f"No access_token in response: {response.json()}"
    assert response.json()["token_type"] == "bearer"

def test_login_invalid_credentials(client):
    """Test login with invalid credentials"""
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "nonexistent", "password": "wrongpassword"}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
