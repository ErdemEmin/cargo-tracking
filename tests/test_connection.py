"""Veritabani baglanti testi — sadece baglantinin calistigini dogrular.

Calistirma:
    venv/Scripts/python.exe -m pytest tests/test_connection.py -v
"""
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["KAFKA_ENABLED"] = "0"

from app import create_app  # noqa: E402
from app import models  # noqa: E402


@pytest.fixture
def app(tmp_path):
    """Her calistirmada gecici, temiz bir veritabani dosyasi."""
    return create_app({
        "TESTING": True,
        "DB_PATH": str(tmp_path / "conn_test.db"),
        "KAFKA_ENABLED": False,
    })


def test_database_connection(app):
    """Baglanti kurulur, sorgu calisir, yazma-okuma yuvarlani yapilir."""
    with app.app_context():
        # 1) Baglanti acilabiliyor mu?
        conn = models.get_db()
        assert isinstance(conn, sqlite3.Connection), "baglanti acilmadi"

        # 2) Kanonik test sorgusu calisiyor mu?
        assert conn.execute("SELECT 1").fetchone()[0] == 1, "sorgu calismadi"

        # 3) Sema uygulanmis mi?
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        assert "cargo" in [t["name"] for t in tables], "cargo tablosu yok"

        # 4) Gercekten yazip okuyabiliyor muyuz?
        models.create_cargo("KRG-CONN-1", "Gonderici", "Alici")
        kayit = models.get_cargo(1)
        assert kayit is not None, "kargo kaydi okunamadi"
        assert kayit["tracking_number"] == "KRG-CONN-1"

        # 5) Degisiklikler kalici mi? (yeni baglanti ile dogrula)
        models.update_status(1, "IN_TRANSIT")

    with app.app_context():                      # yeni baglanti, ayni dosya
        kayit = models.get_cargo(1)
        assert kayit is not None
        assert kayit["status"] == "IN_TRANSIT", "degisiklik kayboldu"


def test_connection_is_isolated(tmp_path):
    """Test veritabani ana veritabanina karismaz."""
    app = create_app({
        "TESTING": True,
        "DB_PATH": str(tmp_path / "izole.db"),
        "KAFKA_ENABLED": False,
    })
    with app.app_context():
        models.create_cargo("KRG-ISO-1", "S", "R")
        assert len(models.list_cargo()) == 1
    # izole.db dosyasi ayri yerde olmali
    assert os.path.exists(str(tmp_path / "izole.db"))
    assert app.config["DB_PATH"] != "cargo.db"
