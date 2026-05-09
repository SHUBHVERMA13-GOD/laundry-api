"""
storage.py — In-memory storage layer for the Laundry Order Management System.

Why a separate module?
  Keeping storage isolated from route logic makes it trivial to swap in
  a real database (SQLite / MongoDB) later without touching main.py.

Thread-safety note:
  FastAPI runs on an async event-loop (uvicorn).  A plain dict is safe for
  single-process deployments.  For multi-worker deployments you would replace
  this with a shared cache (Redis) or a proper DB.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

from models import GarmentItem, OrderResponse, OrderStatus


# ---------------------------------------------------------------------------
# Internal "database"
# ---------------------------------------------------------------------------

# Maps  order_id  →  OrderResponse  (stored as a dict for easy mutation)
_orders: Dict[str, dict] = {}

# Simple thread lock — safe even if uvicorn is started with multiple threads.
_lock = threading.Lock()

# Auto-increment counter used as the human-readable part of the Order ID.
_order_counter: int = 0


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _now() -> datetime:
    """Return the current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


def _generate_order_id() -> str:
    """
    Generate a short, readable Order ID like  ORD-0001 .
    Thread-safe via the module-level lock (caller must already hold the lock).
    """
    global _order_counter
    _order_counter += 1
    return f"ORD-{_order_counter:04d}"


# ---------------------------------------------------------------------------
# Public API used by main.py
# ---------------------------------------------------------------------------

def create_order(
    customer_name: str,
    phone_number: str,
    items: List[GarmentItem],
) -> dict:
    """
    Persist a new order and return the stored dict.

    Steps:
      1. Calculate total_amount = Σ (quantity × price_per_item)
      2. Assign a new Order ID
      3. Set initial status to RECEIVED
      4. Save to the in-memory store
    """
    total_amount = sum(item.quantity * item.price_per_item for item in items)
    now = _now()

    with _lock:
        order_id = _generate_order_id()
        record = {
            "order_id":      order_id,
            "customer_name": customer_name,
            "phone_number":  phone_number,
            # Store items as plain dicts so they can be serialised later.
            "items":         [item.model_dump() for item in items],
            "total_amount":  round(total_amount, 2),
            "status":        OrderStatus.RECEIVED.value,
            "created_at":    now,
            "updated_at":    now,
        }
        _orders[order_id] = record

    return record


def get_order(order_id: str) -> Optional[dict]:
    """Return a single order by ID, or None if not found."""
    return _orders.get(order_id)


def update_order_status(order_id: str, new_status: OrderStatus) -> Optional[dict]:
    """
    Update the status of an existing order.

    Returns the updated record, or None if the order_id doesn't exist.
    """
    with _lock:
        record = _orders.get(order_id)
        if record is None:
            return None
        record["status"]     = new_status.value
        record["updated_at"] = _now()
        return record


def list_orders(
    status: Optional[str]        = None,
    customer_name: Optional[str] = None,
    phone_number: Optional[str]  = None,
) -> List[dict]:
    """
    Return a filtered list of all orders.

    Filters (all optional, combinable):
      status        — exact match (case-insensitive)
      customer_name — substring match (case-insensitive)
      phone_number  — exact match
    """
    results: List[dict] = list(_orders.values())

    if status:
        results = [o for o in results if o["status"].upper() == status.upper()]

    if customer_name:
        needle = customer_name.lower()
        results = [o for o in results if needle in o["customer_name"].lower()]

    if phone_number:
        results = [o for o in results if o["phone_number"] == phone_number]

    # Return newest-first so the caller sees recent orders at the top.
    results.sort(key=lambda o: o["created_at"], reverse=True)
    return results


def get_dashboard_stats() -> dict:
    """
    Aggregate statistics across all stored orders.

    Returns a dict with:
      total_orders     — count of all orders
      total_revenue    — sum of total_amount for DELIVERED orders
                         (you can change this to *all* orders if preferred)
      orders_by_status — {status_label: count, …}
    """
    all_orders = list(_orders.values())

    # Count per status — initialise all statuses to 0 so the response is
    # always complete even when some buckets are empty.
    orders_by_status: Dict[str, int] = {s.value: 0 for s in OrderStatus}
    total_revenue = 0.0

    for order in all_orders:
        orders_by_status[order["status"]] = orders_by_status.get(order["status"], 0) + 1
        # Count revenue only for delivered orders (change condition as needed).
        if order["status"] == OrderStatus.DELIVERED.value:
            total_revenue += order["total_amount"]

    return {
        "total_orders":     len(all_orders),
        "total_revenue":    round(total_revenue, 2),
        "orders_by_status": orders_by_status,
    }
