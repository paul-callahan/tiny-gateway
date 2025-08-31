def test_health_check(client):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_root_endpoint(client):
    """Test root endpoint returns 404 since we don't have a root route"""
    response = client.get("/")
    assert response.status_code == 404

def test_nonexistent_route(client):
    """Test non-existent route returns 404"""
    response = client.get("/nonexistent-route")
    assert response.status_code == 404
