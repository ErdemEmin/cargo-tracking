"""PyTest testleri — Aşama 4 (en az 8 test)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["KAFKA_ENABLED"] = "0"

from app import create_app  # noqa: E402
from app import models  # noqa: E402


@pytest.fixture
def app(tmp_path):
    """Her test kendi geçici SQLite'ını kullanır -> testler izole."""
    application = create_app({
        "TESTING": True,
        "DB_PATH": str(tmp_path / "test_cargo.db"),
        "KAFKA_ENABLED": False,
    })
    yield application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sample(client):
    """Testlerde kullanılacak hazır kargo (id döner)."""
    r = client.post("/cargo", json={
        "tracking_number": "KRG-1001",
        "sender": "Ahmet",
        "receiver": "Mehmet",
    })
    return r.get_json()["id"]


# --- Test 1: geçerli bilgilerle kargo oluşturma ---
def test_01_create_cargo_success(client):
    r = client.post("/cargo", json={
        "tracking_number": "KRG-2001", "sender": "Ayşe", "receiver": "Ali",
    })
    assert r.status_code == 201
    body = r.get_json()
    assert body["tracking_number"] == "KRG-2001"
    assert body["status"] == "CREATED"          # varsayılan durum
    assert body["id"] > 0
    assert body["created_at"]


# --- Test 2: tracking number boşsa hata ---
def test_02_create_cargo_missing_tracking_number(client):
    r = client.post("/cargo", json={"sender": "A", "receiver": "B"})
    assert r.status_code == 400
    assert "tracking_number" in r.get_json()["error"]


# --- Test 2b: aynı tracking number iki kez eklenemez ---
def test_02b_duplicate_tracking_number(client, sample):
    r = client.post("/cargo", json={
        "tracking_number": "KRG-1001", "sender": "X", "receiver": "Y",
    })
    assert r.status_code == 400
    assert "zaten kayıtlı" in r.get_json()["error"]


# --- Test 3: olmayan kargo -> 404 ---
def test_03_get_missing_cargo_returns_404(client):
    assert client.get("/cargo/999999").status_code == 404
    assert client.delete("/cargo/999999").status_code == 404


# --- Test 4: durum değiştirme ---
def test_04_update_status_success(client, sample):
    r = client.put(f"/cargo/{sample}/status", json={"status": "IN_TRANSIT"})
    assert r.status_code == 200
    assert r.get_json()["status"] == "IN_TRANSIT"
    # kalıcılık kontrolü
    assert client.get(f"/cargo/{sample}").get_json()["status"] == "IN_TRANSIT"


# --- Test 5: geçersiz durum -> hata ---
def test_05_update_status_invalid_value(client, sample):
    r = client.put(f"/cargo/{sample}/status", json={"status": "UCUS"})
    assert r.status_code == 400
    assert "geçersiz durum" in r.get_json()["error"]
    # durum değişmemiş olmalı
    assert client.get(f"/cargo/{sample}").get_json()["status"] == "CREATED"


# --- Test 6: teslim edilen kargo tekrar dağıtıma çıkamaz ---
def test_06_delivered_cargo_is_terminal(client, sample):
    assert client.put(
        f"/cargo/{sample}/status", json={"status": "DELIVERED"}
    ).status_code == 200

    r = client.put(f"/cargo/{sample}/status", json={"status": "OUT_FOR_DELIVERY"})
    assert r.status_code == 400
    assert "DELIVERED" in r.get_json()["error"]
    # durum değişmedi
    assert client.get(f"/cargo/{sample}").get_json()["status"] == "DELIVERED"


# --- Test 6b: iptal edilen kargo da terminal ---
def test_06b_cancelled_cargo_is_terminal(client, sample):
    client.put(f"/cargo/{sample}/status", json={"status": "CANCELLED"})
    r = client.put(f"/cargo/{sample}/status", json={"status": "SHIPPED"})
    assert r.status_code == 400
    assert "CANCELLED" in r.get_json()["error"]


# --- Test 7: silme ---
def test_07_delete_cargo(client, sample):
    assert client.delete(f"/cargo/{sample}").status_code == 200


# --- Test 8: silinen kargo tekrar sorgulanınca 404 ---
def test_08_deleted_cargo_returns_404(client, sample):
    client.delete(f"/cargo/{sample}")
    assert client.get(f"/cargo/{sample}").status_code == 404
    assert client.get("/cargo").get_json()["count"] == 0


# --- Test 9: listeleme ---
def test_09_list_and_filter(client, sample):
    for i in range(2, 5):
        client.post("/cargo", json={
            "tracking_number": f"KRG-100{i}", "sender": "S", "receiver": "R",
        })
    assert client.get("/cargo").get_json()["count"] == 4
    client.put(f"/cargo/{sample}/status", json={"status": "DELIVERED"})
    assert client.get("/cargo?status=DELIVERED").get_json()["count"] == 1
    assert client.get("/cargo?status=CREATED").get_json()["count"] == 3


# --- Test 10: model katmanı (CRUD fonksiyonları) ---
def test_10_model_crud_functions(app):
    with app.app_context():
        created = models.create_cargo("KRG-3001", "S", "R")
        assert created["id"] > 0
        assert models.get_cargo(created["id"])["sender"] == "S"
        assert models.get_cargo(999999) is None

        updated = models.update_status(created["id"], "SHIPPED")
        assert updated["status"] == "SHIPPED"

        assert models.count_by_status()["SHIPPED"] == 1
        assert models.delete_cargo(created["id"]) is True
        assert models.delete_cargo(created["id"]) is False
        assert models.get_cargo(created["id"]) is None


# --- Test 11: Prometheus metrikleri üretiliyor mu? ---
def test_11_metrics_endpoint(client, sample):
    client.get("/cargo")
    body = client.get("/metrics").get_data(as_text=True)
    for name in ("cargo_created_total", "cargo_status_changed_total",
                 "api_request_total", "api_request_duration_seconds"):
        assert name in body, f"{name} metriği /metrics çıktısında yok"
