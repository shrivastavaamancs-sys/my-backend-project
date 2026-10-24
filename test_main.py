from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_read_main():
  # Root endpoint check karne ke liye
  response = client.get("/")
  assert response.status_code in [200, 404]  # Agar root route ho toh 200


def test_create_user():
  # Naya user register karne ka test
  response = client.post(
      "/users/", json={"email": "pytest_user@gmail.com", "password": "securepassword"}
  )
  # Agar user pehle se hoga toh 400 dega, naya hoga toh 200/201
  assert response.status_code in [200, 201, 400]


def test_login_access_token():
  # Login karke token mil raha hai ya nahi check karne ka test
  response = client.post(
      "/login", data={"username": "pytest_user@gmail.com", "password": "securepassword"}
  )
  # Agar credentials sahi hain toh 200 aana chahiye aur access_token milna chahiye
  assert response.status_code == 200
  data = response.json()
  assert "access_token" in data
  assert data["token_type"] == "bearer"