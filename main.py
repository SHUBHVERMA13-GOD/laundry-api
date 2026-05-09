"""
main.py — FastAPI application entry-point for the Laundry Order Management System.

Run the server:
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000

Interactive docs:
    http://127.0.0.1:8000/docs   ← Swagger UI  (try endpoints directly!)
    http://127.0.0.1:8000/redoc  ← ReDoc
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

import storage
from models import (
    CreateOrderRequest,
    CreateOrderResponse,
    DashboardResponse,
    OrderResponse,
    OrderStatus,
    UpdateStatusRequest,
)

# ---------------------------------------------------------------------------
# App initialisation
# ---------------------------------------------------------------------------

app = FastAPI(
    title="🧺 Mini Laundry Order Management System",
    description=(
        "A lightweight REST API to manage laundry orders.\n\n"
        "**Status flow:** RECEIVED → PROCESSING → READY → DELIVERED"
    ),
    version="1.0.0",
    contact={"name": "Laundry Admin"},
    license_info={"name": "MIT"},
)

# Allow all origins so a frontend (or curl / Postman) can reach the API freely.
# Tighten this in production by listing specific origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------

@app.get("/", tags=["Dashboard"])
def root():
    """Serve the frontend dashboard."""
    return FileResponse("static/index.html")


# ---------------------------------------------------------------------------
# POST /orders — Create a new laundry order
# ---------------------------------------------------------------------------

@app.post(
    "/orders",
    response_model=CreateOrderResponse,
    status_code=201,
    tags=["Orders"],
    summary="Create a new laundry order",
)
def create_order(body: CreateOrderRequest):
    """
    **Creates a new laundry order.**

    - Validates customer details and garment list.
    - Calculates the total bill automatically.
    - Assigns a unique Order ID (e.g. ORD-0001).
    - Initial status is always **RECEIVED**.

    **Example request body:**
    ```json
    {
        "customer_name": "Priya Sharma",
        "phone_number": "9876543210",
        "items": [
            {"garment": "Saree",  "quantity": 2, "price_per_item": 60.0},
            {"garment": "Shirt",  "quantity": 3, "price_per_item": 25.0},
            {"garment": "Pants",  "quantity": 2, "price_per_item": 30.0}
        ]
    }
    ```
    """
    record = storage.create_order(
        customer_name=body.customer_name,
        phone_number=body.phone_number,
        items=body.items,
    )

    return CreateOrderResponse(
        order_id=record["order_id"],
        customer_name=record["customer_name"],
        total_amount=record["total_amount"],
        status=record["status"],
        message=f"Order {record['order_id']} created successfully. Total: ₹{record['total_amount']}",
    )


# ---------------------------------------------------------------------------
# PUT /orders/{order_id}/status — Update order status
# ---------------------------------------------------------------------------

@app.put(
    "/orders/{order_id}/status",
    response_model=OrderResponse,
    tags=["Orders"],
    summary="Update the status of an existing order",
)
def update_order_status(
    order_id: str = Path(..., examples=["ORD-0001"], description="The unique Order ID."),
    body: UpdateStatusRequest = ...,
):
    """
    **Updates the lifecycle status of an order.**

    Allowed transitions (the API does NOT enforce ordering — you can
    jump to any status for flexibility):
    ```
    RECEIVED → PROCESSING → READY → DELIVERED
    ```

    **Example request body:**
    ```json
    {"status": "PROCESSING"}
    ```
    """
    record = storage.update_order_status(order_id, body.status)

    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Order '{order_id}' not found. Please check the Order ID and try again.",
        )

    return _record_to_response(record)


# ---------------------------------------------------------------------------
# GET /orders — List all orders (with optional filters)
# ---------------------------------------------------------------------------

@app.get(
    "/orders",
    response_model=List[OrderResponse],
    tags=["Orders"],
    summary="List all orders with optional filters",
)
def list_orders(
    status: Optional[OrderStatus] = Query(
        None,
        description="Filter by order status (RECEIVED | PROCESSING | READY | DELIVERED).",
    ),
    customer_name: Optional[str] = Query(
        None,
        description="Filter by customer name (partial, case-insensitive match).",
    ),
    phone: Optional[str] = Query(
        None,
        description="Filter by exact phone number.",
    ),
):
    """
    **Returns a list of all laundry orders**, sorted newest-first.

    All query parameters are **optional** and **combinable**:

    | Parameter     | Match type                 | Example              |
    |---------------|----------------------------|----------------------|
    | `status`      | Exact (case-insensitive)   | `?status=READY`      |
    | `customer_name` | Substring                | `?customer_name=Raj` |
    | `phone`       | Exact                      | `?phone=9876543210`  |

    **Examples:**
    - `/orders` — all orders
    - `/orders?status=READY` — only ready orders
    - `/orders?customer_name=priya&status=PROCESSING` — combined filter
    """
    records = storage.list_orders(
        status=status.value if status else None,
        customer_name=customer_name,
        phone_number=phone,
    )
    return [_record_to_response(r) for r in records]


# ---------------------------------------------------------------------------
# GET /orders/{order_id} — Fetch a single order
# ---------------------------------------------------------------------------

@app.get(
    "/orders/{order_id}",
    response_model=OrderResponse,
    tags=["Orders"],
    summary="Get a single order by ID",
)
def get_order(
    order_id: str = Path(..., examples=["ORD-0001"], description="The unique Order ID."),
):
    """**Fetches a single order** by its Order ID."""
    record = storage.get_order(order_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Order '{order_id}' not found.",
        )
    return _record_to_response(record)


# ---------------------------------------------------------------------------
# GET /dashboard — Summary statistics
# ---------------------------------------------------------------------------

@app.get(
    "/dashboard",
    response_model=DashboardResponse,
    tags=["Dashboard"],
    summary="Get summary statistics",
)
def get_dashboard():
    """
    **Returns a real-time summary of all orders.**

    ```json
    {
        "total_orders": 12,
        "total_revenue": 2450.00,
        "orders_by_status": {
            "RECEIVED": 3,
            "PROCESSING": 4,
            "READY": 3,
            "DELIVERED": 2
        }
    }
    ```

    > **Note:** `total_revenue` counts only **DELIVERED** orders.
    """
    stats = storage.get_dashboard_stats()
    return DashboardResponse(**stats)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

# Mount the static directory to serve index.html, styles.css, and app.js.
# This should be at the end so it doesn't override other routes.
app.mount("/", StaticFiles(directory="static", html=True), name="static")


def _record_to_response(record: dict) -> OrderResponse:
    """Convert a raw storage dict into a validated OrderResponse model."""
    return OrderResponse(**record)
