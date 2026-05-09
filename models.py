"""
models.py — Pydantic data models for the Laundry Order Management System.

These models handle:
  - Request body validation (FastAPI uses them automatically)
  - Response serialization
  - Enum-based status transitions

Pydantic v2 is used (ships with FastAPI >= 0.100).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class OrderStatus(str, Enum):
    """
    Allowed lifecycle statuses for a laundry order.
    Using str-based Enum so FastAPI serialises the *value* (e.g. "RECEIVED")
    rather than the Enum member name.
    """
    RECEIVED   = "RECEIVED"
    PROCESSING = "PROCESSING"
    READY      = "READY"
    DELIVERED  = "DELIVERED"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class GarmentItem(BaseModel):
    """
    Represents a single garment line inside an order.

    Example:
        {"garment": "Shirt", "quantity": 3, "price_per_item": 25.0}
    """
    garment: str = Field(
        ...,
        min_length=1,
        examples=["Shirt"],
        description="Type of garment (e.g. Shirt, Pants, Saree, Jacket).",
    )
    quantity: int = Field(
        ...,
        ge=1,
        examples=[3],
        description="Number of pieces for this garment type. Must be ≥ 1.",
    )
    price_per_item: float = Field(
        ...,
        gt=0,
        examples=[25.0],
        description="Price charged per single piece of this garment type.",
    )

    # Computed helper — not a DB column, used during order creation.
    @property
    def line_total(self) -> float:
        return self.quantity * self.price_per_item


# ---------------------------------------------------------------------------
# Request models  (what the client SENDS)
# ---------------------------------------------------------------------------

class CreateOrderRequest(BaseModel):
    """
    Request body for POST /orders.

    Example JSON:
    {
        "customer_name": "Priya Sharma",
        "phone_number": "9876543210",
        "items": [
            {"garment": "Saree",  "quantity": 2, "price_per_item": 60.0},
            {"garment": "Shirt",  "quantity": 3, "price_per_item": 25.0},
            {"garment": "Pants",  "quantity": 2, "price_per_item": 30.0}
        ]
    }
    """
    customer_name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        examples=["Priya Sharma"],
        description="Full name of the customer.",
    )
    phone_number: str = Field(
        ...,
        examples=["9876543210"],
        description="Customer's phone number (stored as string to preserve leading zeros).",
    )
    items: List[GarmentItem] = Field(
        ...,
        min_length=1,
        description="At least one garment item is required.",
    )

    @field_validator("phone_number")
    @classmethod
    def phone_must_be_numeric(cls, v: str) -> str:
        """Ensure phone number contains only digits (and optional leading +)."""
        cleaned = v.lstrip("+")
        if not cleaned.isdigit():
            raise ValueError("phone_number must contain only digits (optionally prefixed with +).")
        if len(cleaned) < 7 or len(cleaned) > 15:
            raise ValueError("phone_number must be between 7 and 15 digits.")
        return v


class UpdateStatusRequest(BaseModel):
    """
    Request body for PUT /orders/{order_id}/status.

    Example JSON:
        {"status": "PROCESSING"}
    """
    status: OrderStatus = Field(
        ...,
        description="New status to set. Must be one of: RECEIVED, PROCESSING, READY, DELIVERED.",
    )


# ---------------------------------------------------------------------------
# Response models  (what the API RETURNS)
# ---------------------------------------------------------------------------

class OrderResponse(BaseModel):
    """
    Full order representation returned by the API.
    """
    order_id: str         = Field(..., description="Unique identifier for this order.")
    customer_name: str    = Field(..., description="Customer's full name.")
    phone_number: str     = Field(..., description="Customer's phone number.")
    items: List[GarmentItem]
    total_amount: float   = Field(..., description="Sum of (quantity × price_per_item) across all items.")
    status: OrderStatus   = Field(..., description="Current lifecycle status of the order.")
    created_at: datetime  = Field(..., description="UTC timestamp when the order was created.")
    updated_at: datetime  = Field(..., description="UTC timestamp of the most recent update.")


class CreateOrderResponse(BaseModel):
    """
    Slim response returned immediately after creating an order.
    Contains the key fields a caller needs right away.
    """
    order_id: str
    customer_name: str
    total_amount: float
    status: OrderStatus
    message: str = "Order created successfully."


class DashboardResponse(BaseModel):
    """
    Summary statistics returned by GET /dashboard.
    """
    total_orders: int
    total_revenue: float
    orders_by_status: dict  # e.g. {"RECEIVED": 5, "PROCESSING": 2, ...}
