"""Asama 11: tam akis dogrulamasi (calisan Docker Compose uzerinden)."""
import json
import subprocess
import time
import urllib.error
import urllib.request

API = "http://localhost:5000"


def req(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(API + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        return e.code, (json.loads(raw) if raw else None)


def get_text(url, user=None):
    req_obj = urllib.request.Request(url)
    if user:
        import base64
        tok = base64.b64encode(user.encode()).decode()
        req_obj.add_header("Authorization", "Basic " + tok)
    with urllib.request.urlopen(req_obj, timeout=15) as resp:
        return resp.read().decode()


fails = []


def check(label, cond, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {label}{'  ' + str(detail) if detail else ''}")
    if not cond:
        fails.append(label)


# --- Hazirlik: mevcut kargolari temizle ---
st, lst = req("GET", "/cargo?limit=1000")
for c in (lst or {}).get("items", []):
    req("DELETE", f"/cargo/{c['id']}")
print(f"Temizlik: onceki kayit sayisi = {len((lst or {}).get('items', []))}\n")

# --- ASAMA 11: 20 kargo olustur ---
ids = []
for i in range(1, 21):
    st, c = req("POST", "/cargo", {
        "tracking_number": f"KRG-{2000 + i}",
        "sender": f"Gonderici {i}",
        "receiver": f"Alici {i}",
    })
    if st == 201:
        ids.append(c["id"])
check("20 kargo olusturuldu", len(ids) == 20, f"ids={ids[:3]}...{ids[-1:]}")

# --- 10 kargoyu IN_TRANSIT yap ---
ok = 0
for cid in ids[:10]:
    st, _ = req("PUT", f"/cargo/{cid}/status", {"status": "IN_TRANSIT"})
    ok += st == 200
check("10 kargo IN_TRANSIT", ok == 10, f"{ok}/10")

# --- 5 kargoyu DELIVERED yap (ONCE OUT_FOR_DELIVERY) ---
ok = 0
for cid in ids[:5]:
    req("PUT", f"/cargo/{cid}/status", {"status": "OUT_FOR_DELIVERY"})
    st, _ = req("PUT", f"/cargo/{cid}/status", {"status": "DELIVERED"})
    ok += st == 200
check("5 kargo DELIVERED", ok == 5, f"{ok}/5")

# --- 2 kargoyu iptal et ---
ok = 0
for cid in ids[15:17]:
    st, _ = req("PUT", f"/cargo/{cid}/status", {"status": "CANCELLED"})
    ok += st == 200
check("2 kargo CANCELLED", ok == 2, f"{ok}/2")

# --- Terminal durum kontrolu ---
st, _ = req("PUT", f"/cargo/{ids[0]}/status", {"status": "OUT_FOR_DELIVERY"})
check("DELIVERED kargo tekrar dagitilamaz (400)", st == 400, f"got={st}")

print("\n--- Veritabani durum dagilimi ---")
st, lst = req("GET", "/cargo?limit=1000")
from collections import Counter  # noqa: E402
dist = Counter(c["status"] for c in lst["items"])
for k, v in sorted(dist.items()):
    print(f"  {k:18} {v}")
check("toplam 20 kayit", lst["count"] == 20, f"count={lst['count']}")
check("DELIVERED = 5", dist.get("DELIVERED") == 5, dist.get("DELIVERED"))
check("CANCELLED = 2", dist.get("CANCELLED") == 2, dist.get("CANCELLED"))
check("IN_TRANSIT = 5", dist.get("IN_TRANSIT") == 5, dist.get("IN_TRANSIT"))

print("\n--- PROMETHEUS metrikleri ---")
time.sleep(3)
prom = get_text("http://localhost:9090/api/v1/query?query=up")
pj = json.loads(prom)
targets = {t["metric"]["job"]: t["value"][1] for t in pj["data"]["result"]}
check("Prometheus iki hedefi de up", all(v == "1" for v in targets.values()), targets)

for q, label in [
    ("cargo_created_total", "cargo_created_total"),
    ("cargo_delivered_total", "cargo_delivered_total"),
    ("cargo_cancelled_total", "cargo_cancelled_total"),
    ("cargo_status_changed_total", "cargo_status_changed_total"),
    ("api_request_total", "api_request_total"),
    ("api_request_duration_seconds_count", "api_request_duration_seconds_count"),
    ("api_request_duration_seconds_sum", "api_request_duration_seconds_sum"),
    ("api_request_duration_seconds_bucket", "api_request_duration_seconds_bucket"),
    ("cargo_events_consumed_total", "cargo_events_consumed_total (consumer)"),
]:
    d = json.loads(get_text(
        "http://localhost:9090/api/v1/query?query=" + q))["data"]["result"]
    val = d[0]["value"][1] if d else None
    check(f"metrik sorgusu: {label}", bool(d), f"deger={val}")

created = json.loads(get_text(
    "http://localhost:9090/api/v1/query?query=cargo_created_total"))["data"]["result"]
check("cargo_created_total >= 20", float(created[0]["value"][1]) >= 20, created[0]["value"][1])

print("\n--- GRAFANA ---")
try:
    with urllib.request.urlopen("http://localhost:3000/api/health", timeout=10) as resp:
        gh = json.loads(resp.read().decode())
    check("Grafana ayakta", gh.get("database") == "ok", gh)
except Exception as e:
    check("Grafana ayakta", False, e)

dashes = json.loads(get_text("http://localhost:3000/api/search?type=dash-db", "admin:admin"))
print(f"  Grafana dashboard sayisi: {len(dashes)}")
for d in dashes:
    print(f"    - {d.get('title')}  (uid={d.get('uid')})")
check("Grafana dashboard yuklendi", len(dashes) > 0, f"{len(dashes)} dashboard")

# Dashboard panel sayisi
if dashes:
    uid = dashes[0]["uid"]
    dash = json.loads(get_text(
        f"http://localhost:3000/api/dashboards/uid/{uid}", "admin:admin"))["dashboard"]
    n = len(dash.get("panels", []))
    print(f"  '{dash.get('title')}' panel sayisi: {n}")
    check("dashboard >= 5 panel", n >= 5, n)

print("\n--- KAFKA consumer logu ---")
out = subprocess.run(["docker", "compose", "logs", "--tail=25", "consumer"],
                     capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
lines = [l for l in out.splitlines() if "cargo." in l.lower()]
for l in lines[-8:]:
    print("  " + l.split("consumer-1  | ")[-1])
check("consumer event baslari", len(lines) > 0, f"{len(lines)} satir")
check("'delivered' mesaji goruldu", any("delivered" in l.lower() for l in lines))
check("'cancelled' mesaji goruldu", any("cancelled" in l.lower() for l in lines))

print("\n" + ("TUM ASAMA 11 KONTROLLERI GECTI" if not fails else f"FAIL: {fails}"))
raise SystemExit(1 if fails else 0)
