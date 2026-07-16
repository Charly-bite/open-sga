def test_health_endpoint_status(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_health_endpoint_json(client):
    response = client.get("/health")
    assert response.is_json
    data = response.get_json()
    assert data["status"] == "ok"


def test_health_endpoint_diagnostics(client):
    response = client.get("/health")
    data = response.get_json()
    assert "environment" in data
    assert "db_connected" in data
    assert "sap_available" in data
