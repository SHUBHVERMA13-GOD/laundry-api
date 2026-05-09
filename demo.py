"""
demo.py — Hits the live API server and prints formatted results.
Run:  python demo.py
"""
import urllib.request, json

BASE = "http://127.0.0.1:8000"

def post(path, data):
    body = json.dumps(data).encode()
    req  = urllib.request.Request(BASE+path, data=body,
                                  headers={"Content-Type":"application/json"},
                                  method="POST")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def put(path, data):
    body = json.dumps(data).encode()
    req  = urllib.request.Request(BASE+path, data=body,
                                  headers={"Content-Type":"application/json"},
                                  method="PUT")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def get(path):
    with urllib.request.urlopen(BASE+path) as r:
        return json.loads(r.read())

SEP = "="*60

# ── 1. Create Order (Priya) ────────────────────────────────────
print(SEP)
print("STEP 1 | POST /orders  (Priya Sharma)")
print(SEP)
o1 = post("/orders", {
    "customer_name": "Priya Sharma",
    "phone_number":  "9876543210",
    "items": [
        {"garment": "Saree", "quantity": 2, "price_per_item": 60.0},
        {"garment": "Shirt", "quantity": 3, "price_per_item": 25.0},
        {"garment": "Pants", "quantity": 2, "price_per_item": 30.0},
    ],
})
print(json.dumps(o1, indent=2))
# Expected total = (2*60)+(3*25)+(2*30) = 120+75+60 = Rs.255.0

# ── 2. Create Order (Ravi) ────────────────────────────────────
print()
print(SEP)
print("STEP 2 | POST /orders  (Ravi Kumar)")
print(SEP)
o2 = post("/orders", {
    "customer_name": "Ravi Kumar",
    "phone_number":  "9123456789",
    "items": [
        {"garment": "Kurta", "quantity": 1, "price_per_item": 40.0},
        {"garment": "Dhoti", "quantity": 2, "price_per_item": 35.0},
    ],
})
print(json.dumps(o2, indent=2))
# Expected total = 40 + 70 = Rs.110.0

# ── 3. Update Status -> PROCESSING ───────────────────────────
print()
print(SEP)
print("STEP 3 | PUT /orders/" + o1["order_id"] + "/status  -> PROCESSING")
print(SEP)
upd = put("/orders/" + o1["order_id"] + "/status", {"status": "PROCESSING"})
print("  order_id      :", upd["order_id"])
print("  customer_name :", upd["customer_name"])
print("  status        :", upd["status"])

# ── 4. Update Status -> DELIVERED ────────────────────────────
print()
print(SEP)
print("STEP 4 | PUT /orders/" + o2["order_id"] + "/status  -> DELIVERED")
print(SEP)
upd2 = put("/orders/" + o2["order_id"] + "/status", {"status": "DELIVERED"})
print("  order_id :", upd2["order_id"])
print("  status   :", upd2["status"])

# ── 5. List ALL orders ────────────────────────────────────────
print()
print(SEP)
print("STEP 5 | GET /orders  (all)")
print(SEP)
all_orders = get("/orders")
print("  Total orders returned:", len(all_orders))
for o in all_orders:
    line = "  " + o["order_id"] + " | " + o["customer_name"].ljust(15)
    line += " | status=" + o["status"].ljust(12)
    line += " | total=Rs." + str(o["total_amount"])
    print(line)

# ── 6. Filter by status ───────────────────────────────────────
print()
print(SEP)
print("STEP 6 | GET /orders?status=PROCESSING")
print(SEP)
filtered = get("/orders?status=PROCESSING")
print("  Matching orders:", len(filtered))
for o in filtered:
    print("  ->", o["order_id"], "|", o["customer_name"])

# ── 7. Filter by name ─────────────────────────────────────────
print()
print(SEP)
print("STEP 7 | GET /orders?customer_name=ravi  (case-insensitive)")
print(SEP)
by_name = get("/orders?customer_name=ravi")
print("  Matching orders:", len(by_name))
for o in by_name:
    print("  ->", o["order_id"], "|", o["customer_name"])

# ── 8. Dashboard ─────────────────────────────────────────────
print()
print(SEP)
print("STEP 8 | GET /dashboard")
print(SEP)
dash = get("/dashboard")
print(json.dumps(dash, indent=2))
print()
print("  NOTE: total_revenue counts DELIVERED orders only.")
print("        Ravi's order (Rs.110) was DELIVERED -> revenue = Rs.110")
