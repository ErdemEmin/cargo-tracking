"""SQLite veritabani katmani testleri — baglanti, sema ve CRUD davranislari.

Bu dosya app/models.py icindeki get_db / init_db / CRUD fonksiyonlarini ve
baglantinin istek sonunda kapandigini dogrular. Diger testler API uzerinden
gider; burada katmanin kendisi dogrudan sinanir.
"""
import os
import re
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["KAFKA_ENABLED"] = "0"

from app import create_app  # noqa: E402
from app import models  # noqa: E402


@pytest.fixture
def app(tmp_path):
    application = create_app({
        "TESTING": True,
        "DB_PATH": str(tmp_path / "db_test.db"),
        "KAFKA_ENABLED": False,
    })
    yield application


# ---------------------------------------------------------------- baglanti
def test_01_db_dosyasi_olusur(app):
    """init_db calistiktinca veritabani dosyasi diskte olusmali."""
    assert os.path.exists(app.config["DB_PATH"])
    assert os.path.getsize(app.config["DB_PATH"]) > 0


def test_02_cargo_tablosu_var(app):
    """Sema uygulanmis olmali: 'cargo' tablosu sorgulanabilmeli."""
    with app.app_context():
        row = models.get_db().execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='cargo'"
        ).fetchone()
    assert row is not None, "cargo tablosu bulunamadi"
    assert row["name"] == "cargo"


def test_03_baglanti_acilir_ve_kapanir(app):
    """get_db baglantiyi açar, teardown close_db kapatir."""
    with app.app_context():
        conn = models.get_db()
        assert isinstance(conn, sqlite3.Connection)
        assert conn.execute("SELECT 1").fetchone()[0] == 1
    # context cikinca teardown calisti; yeni context'te yeni baglanti acilir
    with app.app_context():
        assert isinstance(models.get_db(), sqlite3.Connection)


def test_04_ayni_istekte_baglanti_paylasilir(app):
    """Ayni istek icinde get_db() hep ayni baglantiyi donmeli (g.cache)."""
    with app.app_context():
        assert models.get_db() is models.get_db()


def test_05_sema_kolonlari_tam(app):
    """Beklenen 6 kolonun tamami mevcut ve tipleri dogru."""
    expected = {
        "id": "INTEGER",
        "tracking_number": "TEXT",
        "sender": "TEXT",
        "receiver": "TEXT",
        "status": "TEXT",
        "created_at": "TEXT",
    }
    with app.app_context():
        cols = models.get_db().execute("PRAGMA table_info(cargo)").fetchall()
    got = {c["name"]: c["type"] for c in cols}
    assert got == expected, f"sutunlar farkli: {got}"


def test_06_id_otomatik_artar(app):
    """AUTOINCREMENT: id degerleri 1'den baslayip artmali."""
    with app.app_context():
        made = [models.create_cargo(f"KRG-DB-{i}", "S", "R") for i in range(3)]
        ids = [m["id"] for m in made if m]
    assert ids == [1, 2, 3], f"beklenen [1,2,3], gelen {ids}"


# ------------------------------------------------------------------- CRUD
def test_07_create_ve_get_roundtrip(app):
    """create_cargo sonrasi get_cargo ayni veriyi donmeli."""
    with app.app_context():
        created = models.create_cargo("KRG-RT-1", "  Ahmet  ", "  Mehmet  ")
        fetched = models.get_cargo(created["id"])
    assert fetched is not None, "kargo kaydi kayboldu"
    assert fetched["tracking_number"] == "KRG-RT-1"
    # bosluklar kirpilmis olmali
    assert fetched["sender"] == "Ahmet"
    assert fetched["receiver"] == "Mehmet"
    assert fetched["status"] == "CREATED"


def test_08_created_at_otomatik_doldurulur(app):
    """created_at veritabani seviyesinde doldurulur (uygulama saatinden degil)."""
    with app.app_context():
        c = models.create_cargo("KRG-T-1", "S", "R")
    # datetime('now') -> "YYYY-MM-DD HH:MM:SS"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", c["created_at"]), \
        f"beklenmeyen created_at bicimi: {c['created_at']!r}"


def test_09_tracking_number_tekilligi(app):
    """UNIQUE constraint: ayni takip no ikinci kez eklenememeli."""
    with app.app_context():
        models.create_cargo("KRG-DUP", "S", "R")
        with pytest.raises(ValueError, match="zaten kayıtlı"):
            models.create_cargo("KRG-DUP", "S2", "R2")
    # ilk kayit bozulmamis olmali
    with app.app_context():
        assert len([c for c in models.list_cargo() if c["tracking_number"] == "KRG-DUP"]) == 1


def test_10_bos_zorunlu_alanlar(app):
    """Bos alanlar ValueError firlatmali, kayit yazilmamali."""
    with app.app_context():
        for kwargs in (
            {"tracking_number": "", "sender": "S", "receiver": "R"},
            {"tracking_number": None, "sender": "S", "receiver": "R"},
            {"tracking_number": "   ", "sender": "S", "receiver": "R"},
            {"tracking_number": "K1", "sender": "", "receiver": "R"},
            {"tracking_number": "K1", "sender": "S", "receiver": ""},
        ):
            with pytest.raises(ValueError):
                models.create_cargo(**kwargs)
        assert models.list_cargo() == [], "gecersiz kayit yazildi"


def test_11_update_status_kalici(app):
    """update_status yaziyi DB'ye yazmali, surec sonrasi da durmali."""
    cid = None
    with app.app_context():
        cid = models.create_cargo("KRG-U-1", "S", "R")["id"]
        models.update_status(cid, "IN_TRANSIT")
    # yeni context = yeni baglanti: diskten okunuyor
    with app.app_context():
        row = models.get_cargo(cid)
    assert row is not None and row["status"] == "IN_TRANSIT"


def test_12_update_status_gecersiz_deger(app):
    """STATUSES listesinde olmayan durum reddedilmeli, kayit degismemeli."""
    with app.app_context():
        cid = models.create_cargo("KRG-U-2", "S", "R")["id"]
        with pytest.raises(ValueError, match="geçersiz durum"):
            models.update_status(cid, "UCUS")
        row = models.get_cargo(cid)
        assert row is not None and row["status"] == "CREATED"


def test_13_update_status_bulunamayan_kargo(app):
    """Olmayan id icin LookupError (API katmani bunu 404'e cevirir)."""
    with app.app_context():
        with pytest.raises(LookupError):
            models.update_status(999999, "SHIPPED")


def test_14_terminal_durum_korumasi(app):
    """DELIVERED ve CANCELLED sonrasi durum degisemez."""
    with app.app_context():
        for terminal in ("DELIVERED", "CANCELLED"):
            cid = models.create_cargo(f"KRG-T-{terminal}", "S", "R")["id"]
            models.update_status(cid, terminal)
            with pytest.raises(ValueError, match="tekrar değiştirilemez"):
                models.update_status(cid, "SHIPPED")
            row = models.get_cargo(cid)
            assert row is not None and row["status"] == terminal


def test_15_delete_durumu(app):
    """delete_cargo: var olan -> True, ikinci kez -> False."""
    with app.app_context():
        cid = models.create_cargo("KRG-D-1", "S", "R")["id"]
        assert models.delete_cargo(cid) is True
        assert models.get_cargo(cid) is None
        assert models.delete_cargo(cid) is False
        assert models.delete_cargo(999999) is False


# ------------------------------------------------------------------ sorgu
def test_16_list_cargo_filtre_ve_sayfalama(app):
    """limit/offset ve status filtresi calismali."""
    with app.app_context():
        for i in range(5):
            models.create_cargo(f"KRG-L-{i}", "S", "R")
        models.update_status(1, "DELIVERED")
        models.update_status(3, "DELIVERED")

        assert len(models.list_cargo()) == 5
        assert len(models.list_cargo(status="DELIVERED")) == 2
        assert len(models.list_cargo(limit=2)) == 2
        assert len(models.list_cargo(limit=2, offset=4)) == 1
        # en yeniden eskiye sirali
        assert [c["id"] for c in models.list_cargo()][:2] == [5, 4]


def test_17_count_by_status(app):
    """Duruma gore sayim dogru olmali."""
    with app.app_context():
        ids = [models.create_cargo(f"KRG-C-{i}", "S", "R")["id"] for i in range(4)]
        # id'ler 1'den baslamak zorunda degil; olusturulan kayitlari kullan
        for cid in ids[:3]:
            models.update_status(cid, "SHIPPED")
        models.update_status(ids[3], "CANCELLED")
        counts = models.count_by_status()
    assert counts == {"SHIPPED": 3, "CANCELLED": 1}
    assert sum(counts.values()) == 4
    # CREATED kalmadi cunku dort kayit da ilerletildi
    assert "CREATED" not in counts


def test_18_islemler_rollback_olmaz(app):
    """Gecersiz insert sonrasi onceki kayitlar saglam kalmali."""
    with app.app_context():
        models.create_cargo("KRG-RB-1", "S", "R")
        with pytest.raises(ValueError):
            models.create_cargo("KRG-RB-1", "X", "Y")   # UNIQUE ihlali
        # ihlalden sonra da yazma calisiyor mu?
        models.create_cargo("KRG-RB-2", "S", "R")
        rows = models.list_cargo()
    assert len(rows) == 2
    assert {c["tracking_number"] for c in rows} == {"KRG-RB-1", "KRG-RB-2"}
