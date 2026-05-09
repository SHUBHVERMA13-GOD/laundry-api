"""
test_api.py — Automated tests for the Laundry Order Management System.

Run tests:
    pytest test_api.py -v

Uses FastAPI's built-in TestClient (wraps httpx) — no live server needed.
Each test function is independent; a fresh app state is used per test session.
"""

from __future__ import annotations

import importlib
import sys

import pytest
from fastapi.testclient import TestClient


# ── Reload storage so each pytest session starts with an empty store ──────
def _fresh_client():
    """Import (or re-import) app with a clean storage state."""
    # Remove cached modules so counters reset between test runs.
    for mod in ["storage", "main", "models"]:
        sys.modules.pop(mod, None)
    from main import app
    return TestClient(app)


client = _fresh_client()


# ---------------------------------------------------------------------------
# Sample payloads
# ---------------------------------------------------------------------------

PRIYA_ORDER = {
    "customer_name": "Priya Sharma",
    "phone_number":  "9876543210",
    "items": [
        {"garment": "Saree",  "quantity": 2, "price_per_item": 60.0},
        {"garment": "Shirt",  "quantity": 3, "price_per_item": 25.0},
        {"garment": "Pants",  "quantity": 2, "price_per_item": 30.0},
    ],
}

RAVI_ORDER = {
    "customer_name": "Ravi Kumar",
    "phone_number":  "9123456789",
    "items": [
        {"garment": "Kurta",   "quantity": 1, "price_per_item": 40.0},
        {"garment": "Dhoti",   "quantity": 2, "price_per_item": 35.0},
    ],
}


# ---------------------------------------------------------------------------
# Tests: Health
# ---------------------------------------------------------------------------

def test_root_returns_200():
    """GET / should return 200 and confirm the service is running."""
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "running"
    print("\n✅ Root health-check passed:", data)


# ---------------------------------------------------------------------------
# Tests: Create Order  (POST /orders)
# ---------------------------------------------------------------------------

def test_create_order_success():
    """A valid order should return 201 with correct order_id and total."""
    res = client.post("/orders", json=PRIYA_ORDER)
    assert res.status_code == 201
    data = res.json()

    # Order ID should follow ORD-XXXX pattern.
    assert data["order_id"].startswith("ORD-")
    assert data["customer_name"] == "Priya Sharma"
    assert data["status"] == "RECEIVED"

    # Total = (2×60) + (3×25) + (2×30) = 120 + 75 + 60 = 255
    assert data["total_amount"] == 255.0
    print("\n✅ Create order:", data)


def test_create_order_missing_items():
    """Sending an empty items list should return HTTP 422 Unprocessable Entity."""
    bad_payload = {**PRIYA_ORDER, "items": []}
    res = client.post("/orders", json=bad_payload)
    assert res.status_code == 422
    print("\n✅ Empty items correctly rejected:", res.json()["detail"])


def test_create_order_invalid_phone():
    """Non-numeric phone number should fail validation."""
    bad_payload = {**PRIYA_ORDER, "phone_number": "ABCD-EFGH"}
    res = client.post("/orders", json=bad_payload)
    assert res.status_code == 422
    print("\n✅ Invalid phone correctly rejected.")


def test_create_order_zero_quantity():
    """Quantity < 1 should fail Pydantic validation."""
    bad_payload = {
        "customer_name": "Test User",
        "phone_number":  "1234567890",
        "items": [{"garment": "Shirt", "quantity": 0, "price_per_item": 25.0}],
    }
    res = client.post("/orders", json=bad_payload)
    assert res.status_code == 422
    print("\n✅ Zero quantity correctly rejected.")


# ---------------------------------------------------------------------------
# Tests: Update Status  (PUT /orders/{id}/status)
# ---------------------------------------------------------------------------

def test_update_status_success():
    """Updating status from RECEIVED → PROCESSING should work."""
    # First create an order.
    create_res = client.post("/orders", json=RAVI_ORDER)
    order_id   = create_res.json()["order_id"]

    # Update status.
    res = client.put(f"/orders/{order_id}/status", json={"status": "PROCESSING"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "PROCESSING"
    assert data["order_id"] == order_id
    print(f"\n✅ Status updated to PROCESSING for {order_id}")


def test_update_status_not_found():
    """Updating a non-existent order should return 404."""
    res = client.put("/orders/ORD-9999/status", json={"status": "READY"})
    assert res.status_code == 404
    print("\n✅ 404 correctly returned for unknown order.")


def test_update_status_invalid_value():
    """An invalid status string should return 422."""
    create_res = client.post("/orders", json=PRIYA_ORDER)
    order_id   = create_res.json()["order_id"]
    res = client.put(f"/orders/{order_id}/status", json={"status": "WASHING"})
    assert res.status_code == 422
    print("\n✅ Invalid status 'WASHING' correctly rejected.")


# ---------------------------------------------------------------------------
# Tests: List Orders  (GET /orders)
# ---------------------------------------------------------------------------

def test_list_all_orders():
    """GET /orders should return a list (may be non-empty)."""
    res = client.get("/orders")
    assert res.status_code == 200
    assert isinstance(res.json(), list)
    print(f"\n✅ List all orders returned {len(res.json())} records.")


def test_filter_by_status():
    """Filter by status=RECEIVED should only include RECEIVED orders."""
    client.post("/orders", json=PRIYA_ORDER)   # creates with RECEIVED
    res  = client.get("/orders?status=RECEIVED")
    data = res.json()
    assert res.status_code == 200
    assert all(o["status"] == "RECEIVED" for o in data), "Non-RECEIVED order in results!"
    print(f"\n✅ Status filter returned {len(data)} RECEIVED orders.")


def test_filter_by_customer_name():
    """Filter by customer_name should do a case-insensitive substring match."""
    client.post("/orders", json=PRIYA_ORDER)
    res  = client.get("/orders?customer_name=priya")   # lowercase search
    data = res.json()
    assert res.status_code == 200
    assert all("priya" in o["customer_name"].lower() for o in data)
    print(f"\n✅ Name filter returned {len(data)} orders for 'priya'.")


def test_filter_by_phone():
    """Filter by exact phone number."""
    client.post("/orders", json=RAVI_ORDER)
    res  = client.get(f"/orders?phone={RAVI_ORDER['phone_number']}")
    data = res.json()
    assert res.status_code == 200
    assert all(o["phone_number"] == RAVI_ORDER["phone_number"] for o in data)
    print(f"\n✅ Phone filter returned {len(data)} orders.")


# ---------------------------------------------------------------------------
# Tests: Dashboard  (GET /dashboard)
# ---------------------------------------------------------------------------

def test_dashboard_keys():
    """Dashboard response must contain the three required keys."""
    res  = client.get("/dashboard")
    data = res.json()
    assert res.status_code == 200
    assert "total_orders"     in data
    assert "total_revenue"    in data
    assert "orders_by_status" in data
    print("\n✅ Dashboard response:", data)


def test_dashboard_revenue_counts_only_delivered():
    """
    Revenue should only include DELIVERED orders.
    Create one order, mark it DELIVERED, check revenue.
    """
    # Create a simple order with a known total: 1×100 = 100.0
    res = client.post("/orders", json={
        "customer_name": "Revenue Test",
        "phone_number":  "1111111111",
        "items": [{"garment": "Jacket", "quantity": 1, "price_per_item": 100.0}],
    })
    order_id = res.json()["order_id"]

    # Mark as DELIVERED.
    client.put(f"/orders/{order_id}/status", json={"status": "DELIVERED"})

    dash = client.get("/dashboard").json()
    # Revenue should be ≥ 100 (other tests may have also delivered orders).
    assert dash["total_revenue"] >= 100.0
    assert dash["orders_by_status"]["DELIVERED"] >= 1
    print(f"\n✅ Revenue after DELIVERED order: ₹{dash['total_revenue']}")


# ---------------------------------------------------------------------------
# Manual curl examples (printed when you run this file directly)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║        Manual cURL / HTTPie test examples                   ║
╚══════════════════════════════════════════════════════════════╝

# 1) Create order
curl -X POST http://127.0.0.1:8000/orders \\
  -H "Content-Type: application/json" \\
  -d '{
    "customer_name": "Priya Sharma",
    "phone_number": "9876543210",
    "items": [
      {"garment": "Saree",  "quantity": 2, "price_per_item": 60.0},
      {"garment": "Shirt",  "quantity": 3, "price_per_item": 25.0},
      {"garment": "Pants",  "quantity": 2, "price_per_item": 30.0}
    ]
  }'

# 2) Update status  (replace ORD-0001 with your actual ID)
curl -X PUT http://127.0.0.1:8000/orders/ORD-0001/status \\
  -H "Content-Type: application/json" \\
  -d '{"status": "PROCESSING"}'

# 3) List all orders
curl http://127.0.0.1:8000/orders

# 4) Filter by status
curl "http://127.0.0.1:8000/orders?status=RECEIVED"

# 5) Filter by customer name (partial)
curl "http://127.0.0.1:8000/orders?customer_name=priya"

# 6) Filter by phone
curl "http://127.0.0.1:8000/orders?phone=9876543210"

# 7) Dashboard
curl http://127.0.0.1:8000/dashboard

# ─── With HTTPie (pip install httpie) ────────────────────────
# http POST :8000/orders customer_name="Ravi" phone_number="9123456789" \\
#   items:='[{"garment":"Kurta","quantity":1,"price_per_item":40}]'
""")
