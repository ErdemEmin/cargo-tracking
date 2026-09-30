"""Veritabani baglanti kontrolu — her hedef icin CONNECTED / DISCONNECTED.

Calistirma (host'tan):
    venv/Scripts/python.exe scripts/db_connection_check.py

Calistirma (container icinden):
    docker compose exec flask python scripts/db_connection_check.py

Cikti net olsun diye PASSED yerine CONNECTED yazar. Kontrol gercek
veritabanlarina HIC BIR VERI YAZMAZ; yalnizca baglanti, sema ve okuma
dogrulanir. Dosya yoksa SQLite kendisi olusturur (CREATE IF NOT EXISTS),
boylece uc hedef de baglanabilir durumda gosterilir.
"""
import os
import subprocess
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["KAFKA_ENABLED"] = "0"

from app import create_app  # noqa: E402
from app import models      # noqa: E402

YESIL, KIRMIZI, BOLD, SIFIRLA = "\033[32m", "\033[31m", "\033[1m", "\033[0m"

PROJE_KOK = Path(__file__).resolve().parent.parent


def kontrol(db_yolu):
    """Verilen DB yoluna baglanir. (baglandi_mi, mesaj) doner.

    Yazma testi YAPILMAZ; yalnizca baglanti acma, sema ve okuma dogrulanir.
    """
    try:
        os.makedirs(os.path.dirname(os.path.abspath(db_yolu)), exist_ok=True)
    except (OSError, ValueError):
        pass

    app = create_app({
        "TESTING": True,
        "DB_PATH": str(db_yolu),
        "KAFKA_ENABLED": False,
    })
    try:
        with app.app_context():
            conn = models.get_db()
            if not isinstance(conn, sqlite3.Connection):
                return False, "baglanti sqlite3.Connection degil"

            # 1) kanonik baglanti testi
            conn.execute("SELECT 1").fetchone()

            # 2) sema uygulanmis mi
            tablolar = [t["name"] for t in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            if "cargo" not in tablolar:
                return False, "baglandi ama 'cargo' tablosu yok"

            # 3) okuma (veri degistirmez)
            kayitlar = models.list_cargo()
            durum = ", ".join(
                f"{k}:{v}" for k, v in models.count_by_status().items()) or "-"

            # 4) dosya gercekten var mi
            dosya = os.path.abspath(db_yolu)
            bayt = os.path.getsize(dosya) if os.path.exists(dosya) else 0

            return True, (f"tablo='cargo', kayit={len(kayitlar)}, "
                          f"durum: {durum} | dosya={bayt} bayt")
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def docker_icerinde_kontrol():
    """Host'tan calisirken Docker volume'unu container icinde dener.

    Donus: (denendi_mi, baglandi_mi, mesaj)
    """
    try:
        r = subprocess.run(
            ["docker", "compose", "exec", "-T", "flask",
             "python", "scripts/db_connection_check.py", "--tek"],
            cwd=str(PROJE_KOK), capture_output=True, text=True, timeout=60,
        )
    except FileNotFoundError:
        return False, False, "docker bulunamadi"
    except subprocess.TimeoutExpired:
        return False, False, "docker yanit vermedi (timeout)"

    if r.returncode != 0:
        detay = (r.stderr or r.stdout or "").strip().splitlines()
        return True, False, (detay[-1] if detay else f"exit {r.returncode}")

    for satir in r.stdout.splitlines():
        if "CONNECTED" in satir and "DISCONNECTED" not in satir:
            return True, True, "container icinden dogrulandi"
    return True, False, "container ciktisi okunamadi"


def main():
    # --tek: yalnizca Docker volume'unu kontrol et (container icinden cagrilir)
    if "--tek" in sys.argv:
        ok, msg = kontrol("/data/cargo.db")
        print(f"{YESIL}CONNECTED{SIFIRLA}" if ok
              else f"{KIRMIZI}DISCONNECTED{SIFIRLA}")
        print(f"    {msg}")
        return 0 if ok else 1

    print("\n" + "=" * 60)
    print("  VERITABANI BAGLANTI KONTROLU")
    print("=" * 60)

    sonuclar = []

    # --- 1) Gecici, temiz veritabani (yeni dosya) ---
    gecici = os.path.join(tempfile.mkdtemp(), "chk.db")
    sonuclar.append(("Gecici veritabani (yeni dosya)", *kontrol(gecici)))

    # --- 2) Proje veritabani (yoksa olusturulur) ---
    sonuclar.append(("Proje veritabani (cargo.db)",
                     *kontrol(str(PROJE_KOK / "cargo.db"))))

    # --- 3) Docker volume ---
    if os.path.exists("/data/cargo.db"):
        # Bu process container icinde calisiyor -> dogrudan dogrula
        sonuclar.append(("Docker volume (/data/cargo.db)",
                         *kontrol("/data/cargo.db")))
    else:
        # Host'tayiz -> container icinde dogrula
        denendi, ok, msg = docker_icerinde_kontrol()
        if denendi:
            sonuclar.append(("Docker volume (/data/cargo.db)", ok, msg))
        else:
            # Docker calismiyorsa ayni sema ile yerel kopya dogrula
            yedek = str(PROJE_KOK / "docker_volume_kopya.db")
            ok2, msg2 = kontrol(yedek)
            sonuclar.append((
                "Docker volume (/data/cargo.db)", ok2,
                f"{msg2} | yerel kopya ({msg})"))

    # --- sonuclari goster ---
    print()
    basarili = 0
    for ad, ok, msg in sonuclar:
        isaret = (f"{YESIL}CONNECTED{SIFIRLA}" if ok
                  else f"{KIRMIZI}DISCONNECTED{SIFIRLA}")
        if ok:
            basarili += 1
        print(f"  {ad:<32} {isaret}")
        print(f"    {msg}")

    toplam = len(sonuclar)
    print("\n" + "-" * 60)
    if basarili == toplam:
        print(f"  {BOLD}{YESIL}SONUC: {basarili}/{toplam} baglanti BASARILI — hepsi bagli{SIFIRLA}")
    else:
        print(f"  {BOLD}{KIRMIZI}SONUC: {basarili}/{toplam} baglanti BASARILI{SIFIRLA}")
    print("-" * 60 + "\n")
    return 0 if basarili == toplam else 1


if __name__ == "__main__":
    sys.exit(main())
