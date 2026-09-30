"""Veritabani baglanti kontrolu — sadece baglandi / baglanmadi sonucu.

Calistirma:
    venv/Scripts/python.exe scripts/db_connection_check.py

Cikti net olsun diye PASSED/FAILED yerine CONNECTED / DISCONNECTED yazar.
"""
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["KAFKA_ENABLED"] = "0"

from app import create_app  # noqa: E402
from app import models      # noqa: E402

YESIL, KIRMIZI, SARI, SIFIRLA = "\033[32m", "\033[31m", "\033[33m", "\033[0m"


def kontrol(db_yolu, yazma_testi=True):
    """Verilen DB yoluna baglanmayi dener. (baglandi_mi, mesaj) doner.

    yazma_testi=False verilirse hicbir veri degistirilmez; sadece baglanti,
    sema ve okuma kontrolu yapilir. Gercek veritabani dosyalarinda yazma
    yapilmaz, aksi halde kontrol kendi kaydini birakir ve sonraki
    calistirmada UNIQUE ihlali olur.
    """
    app = create_app({
        "TESTING": True,
        "DB_PATH": db_yolu,
        "KAFKA_ENABLED": False,
    })
    try:
        with app.app_context():
            conn = models.get_db()
            if not isinstance(conn, sqlite3.Connection):
                return False, "baglanti sqlite3.Connection degil"
            conn.execute("SELECT 1").fetchone()

            # tablo var mi
            tablolar = [t["name"] for t in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            if "cargo" not in tablolar:
                return False, "baglandi ama 'cargo' tablosu yok"

            # okuma testi (veri degistirmez)
            kayitlar = models.list_cargo()
            adet = len(kayitlar)

            if not yazma_testi:
                durum = ", ".join(
                    f"{k}:{v}" for k, v in models.count_by_status().items()) or "-"
                return True, f"tablo='cargo', kayit={adet}, durum: {durum}"

            # yazma testi (yalnizca gecici dosyada)
            etiket = "KRG-CHK-" + os.urandom(3).hex().upper()
            k = models.create_cargo(etiket, "S", "R")
            if k is None or models.get_cargo(k["id"]) is None:
                return False, "baglandi ama yazma/okuma calismadi"
            models.delete_cargo(k["id"])          # iz birakma
            return True, f"tablo='cargo', yazma/okuma testi gecti, kayit={adet}"

    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def main():
    print("\n" + "=" * 58)
    print("  VERITABANI BAGLANTI KONTROLU")
    print("=" * 58)

    sonuclar = []

    # --- 1) Gecici, temiz veritabani (her zaman acilmali) ---
    import tempfile
    gecici = os.path.join(tempfile.mkdtemp(), "chk.db")
    ok, msg = kontrol(gecici, yazma_testi=True)
    sonuclar.append(("Gecici veritabani (yeni dosya)", ok, msg))

    # --- 2) Proje veritabani (dosya varsa) — SADECE OKUMA ---
    proje_db = os.path.abspath(
        Path(__file__).resolve().parent.parent / "cargo.db")
    if os.path.exists(proje_db):
        ok2, msg2 = kontrol(proje_db, yazma_testi=False)
        sonuclar.append(("Proje veritabani (cargo.db)", ok2, msg2))
    else:
        sonuclar.append(("Proje veritabani (cargo.db)", None,
                         "dosya yok - normal, API ilk calistirmada olusturur"))

    # --- 3) Docker icindeki SQLite (volume) — SADECE OKUMA ---
    docker_db = "/data/cargo.db"
    if os.path.exists(docker_db):
        ok3, msg3 = kontrol(docker_db, yazma_testi=False)
        sonuclar.append(("Docker volume (/data/cargo.db)", ok3, msg3))
    else:
        sonuclar.append(("Docker volume (/data/cargo.db)", None,
                         "container ici degilsiniz - bu adim atlandi"))

    # --- sonuclari goster ---
    print()
    basarili = 0
    for ad, ok, msg in sonuclar:
        if ok is None:
            isaret = f"{SARI}SKIP{SIFIRLA}"
        elif ok:
            isaret = f"{YESIL}CONNECTED{SIFIRLA}"
            basarili += 1
        else:
            isaret = f"{KIRMIZI}DISCONNECTED{SIFIRLA}"
        print(f"  {ad:<34} {isaret}")
        print(f"    {msg}")

    print("\n" + "-" * 58)
    if basarili == 0:
        print(f"  {KIRMIZI}SONUC: HICBIR BAGLANTI KURULAMADI{SIFIRLA}")
        print("  -> API calisiyor mu?  docker compose ps")
    else:
        print(f"  {YESIL}SONUC: {basarili} baglanti BASARILI{SIFIRLA}")
    print("-" * 58 + "\n")
    return 0 if basarili > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
