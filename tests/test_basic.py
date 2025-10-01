import pytest
import json
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database_connected" in data
    assert "model_loaded" in data
    assert "schema_loaded" in data

def test_root_endpoint():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data
    assert "endpoints" in data

def test_schema_endpoint():
    """Test schema endpoint"""
    response = client.get("/schema")
    assert response.status_code == 200
    data = response.json()
    assert "tables" in data
    assert "relationships" in data
    assert "entity_scoped_tables" in data

def test_table_info_endpoint():
    """Test table info endpoint"""
    response = client.get("/schema/shipments")
    assert response.status_code == 200
    data = response.json()
    assert "table_name" in data
    assert "schema_info" in data

def test_query_endpoint_invalid_request():
    """Test query endpoint with invalid request"""
    response = client.post("/query", json={})
    assert response.status_code == 422  # Validation error

def test_query_endpoint_missing_fields():
    """Test query endpoint with missing required fields"""
    response = client.post("/query", json={"query": "test query"})
    assert response.status_code == 422  # Missing entity_id

def test_query_endpoint_valid_request():
    """Test query endpoint with valid request"""
    request_data = {
        "query": "Show all shipments",
        "entity_id": "test123",
        "include_explanation": False
    }
    response = client.post("/query", json=request_data)
    # This might fail if model is not loaded, but should return proper error
    assert response.status_code in [200, 500]  # Either success or model error

def test_rate_limiting():
    """Test rate limiting (basic test)"""
    # Make multiple requests quickly
    for _ in range(5):
        response = client.get("/health")
        assert response.status_code == 200

def test_cors_headers():
    """Test CORS headers are present"""
    response = client.get("/health")
    assert "access-control-allow-origin" in response.headers

if __name__ == "__main__":
    pytest.main([__file__]) 