"""Aşama 2 smoke testi: API'yi gerçek HTTP istekleriyle dener.
Kafkasiz çalışır (KAFKA_ENABLED=0), böylece Aşama 2/3 Kafka olmadan geçer.
Çalıştırma: venv/Scripts/python.exe scripts_smoke_check.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["KAFKA_ENABLED"] = "0"

from app import create_app  # noqa: E402

db = os.path.join(tempfile.mkdtemp(), "smoke.db")
app = create_app({"TESTING": True, "DB_PATH": db, "KAFKA_ENABLED": False})
c = app.test_client()

fails = []


def check(label, got, want):
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'}  {label}: got={got} want={want}")
    if not ok:
        fails.append(label)


# 1) POST /cargo
r = c.post("/cargo", json={"tracking_number": "KRG-1001",
                           "sender": "Ahmet", "receiver": "Mehmet"})
check("POST /cargo", r.status_code, 201)
cargo_id = r.get_json()["id"]
check("POST varsayilan durum", r.get_json()["status"], "CREATED")

# 2) POST eksik alan
check("POST tracking_number bos",
      c.post("/cargo", json={"sender": "A", "receiver": "B"}).status_code, 400)

# 3) GET tek kargo
check("GET /cargo/<id>", c.get(f"/cargo/{cargo_id}").status_code, 200)
check("GET olmayan kargo", c.get("/cargo/9999").status_code, 404)

# 4) PUT durum
r = c.put(f"/cargo/{cargo_id}/status", json={"status": "IN_TRANSIT"})
check("PUT status", r.status_code, 200)
check("PUT yeni durum", r.get_json()["status"], "IN_TRANSIT")

# 5) PUT gecersiz durum
check("PUT gecersiz durum",
      c.put(f"/cargo/{cargo_id}/status", json={"status": "UCUS"}).status_code, 400)

# 6) Terminal durum
check("DELIVERED", c.put(f"/cargo/{cargo_id}/status",
                         json={"status": "DELIVERED"}).status_code, 200)
check("DELIVERED sonrasi tekrar dagit",
      c.put(f"/cargo/{cargo_id}/status",
            json={"status": "OUT_FOR_DELIVERY"}).status_code, 400)

# 7) Liste
check("GET /cargo liste", c.get("/cargo").get_json()["count"], 1)
check("GET /cargo status filtresi",
      c.get("/cargo?status=DELIVERED").get_json()["count"], 1)
check("GET /cargo gecersiz filtre", c.get("/cargo?status=X").status_code, 400)

# 8) DELETE
check("DELETE", c.delete(f"/cargo/{cargo_id}").status_code, 200)
check("silinen tekrar GET", c.get(f"/cargo/{cargo_id}").status_code, 404)

# 9) Metrikler
m = c.get("/metrics").get_data(as_text=True)
for line in ("cargo_created_total", "cargo_delivered_total",
             "cargo_status_changed_total", "api_request_total",
             "api_request_duration_seconds"):
    check(f"metrik {line}", any(l.startswith(line) for l in m.splitlines()), True)

# 10) Health
check("GET /health", c.get("/health").status_code, 200)

print("\n" + ("TUM SMOKE TESTLERI GECTI" if not fails
              else f"FAIL: {fails}"))
sys.exit(1 if fails else 0)
