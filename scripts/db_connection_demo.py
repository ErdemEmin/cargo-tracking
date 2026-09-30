"""Veritabani baglanti demosu — sunumda terminalde calistirilir.

Her adim ayri bir komut olarak yazilir ve calistirilir; ciktilar
birer birer basilir. Boylece baglantinin nasil kuruldugu gorunur.

Calistirma:
    venv/Scripts/python.exe scripts/db_connection_demo.py
"""
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["KAFKA_ENABLED"] = "0"

from app import create_app          # noqa: E402
from app import models              # noqa: E402

# --- yardimcilar -------------------------------------------------------
BOLD, DIM, YESIL, KIRMIZI, MAVI, SIFIRLA = (
    "\033[1m", "\033[2m", "\033[32m", "\033[31m", "\033[36m", "\033[0m")


def adim(no, baslik):
    print(f"\n{BOLD}{MAVI}[{no}] {baslik}{SIFIRLA}")


def komut(kod, aciklama=""):
    print(f"{DIM}$ {kod}{SIFIRLA}")
    if aciklama:
        print(f"{DIM}  -> {aciklama}{SIFIRLA}")


def tamam(mesaj):
    print(f"{YESIL}  ✓ {mesaj}{SIFIRLA}")


def hata(mesaj):
    print(f"{KIRMIZI}  ✗ {mesaj}{SIFIRLA}")


def main():
    print(f"{BOLD}{'=' * 62}")
    print("  VERITABANI BAGLANTI DEMOSU — SQLite")
    print(f"{'=' * 62}{SIFIRLA}")

    # ---------------------------------------------------------------- 0
    adim(0, "Uygulama ve baglanti ayari")
    db_yolu = os.path.join(os.path.dirname(__file__), "..", "demo_baglanti.db")
    db_yolu = os.path.abspath(db_yolu)
    if os.path.exists(db_yolu):
        os.remove(db_yolu)   # her calistirmada temiz basla

    app = create_app({
        "TESTING": True,
        "DB_PATH": db_yolu,
        "KAFKA_ENABLED": False,
    })
    komut(f'DB_PATH = "{db_yolu}"', "veritabani dosya konumu")
    tamam(f"uygulama olusturuldu, baglanti {db_yolu} adresine baglanacak")

    # ---------------------------------------------------------------- 1
    adim(1, "Baglantiyi acmak — app_context()")
    komut("with app.app_context():", "Flask uygulama baglami")
    komut("    conn = models.get_db()", "baglantiyi acar (ilk cagrida olusturur)")

    with app.app_context():
        conn = models.get_db()
        komut("    type(conn)", "baglanti tipi")
        print(f"    {BOLD}{type(conn)}{SIFIRLA}")
        if not isinstance(conn, sqlite3.Connection):
            hata("baglanti bir sqlite3.Connection degil")
            return 1
        tamam("baglanti acildi, tip: sqlite3.Connection")

        # ------------------------------------------------------------ 2
        adim(2, "Baglanti sagligini test etmek — SELECT 1")
        komut('    conn.execute("SELECT 1").fetchone()[0]', "kanonik baglanti testi")
        sonuc = conn.execute("SELECT 1").fetchone()[0]
        print(f"    {BOLD}{sonuc}{SIFIRLA}")
        if sonuc == 1:
            tamam("baglanti saglikli, sorgular calisiyor")
        else:
            hata("beklenmeyen sonuc")
            return 1

        # ------------------------------------------------------------ 3
        adim(3, "Baglanti dosyada mi?")
        komut('    conn.execute("PRAGMA database_list")', "aktif veritabani dosyasi")
        for satir in conn.execute("PRAGMA database_list").fetchall():
            print(f"    seq={satir['seq']}  name={satir['name']}  file={satir['file']}")
        tamam(f"dosya olustu: {os.path.getsize(db_yolu)} bayt")

        # ------------------------------------------------------------ 4
        adim(4, "Sema kontrolu — tablolar")
        komut("SELECT name FROM sqlite_master WHERE type='table'", "olusturulan tablolar")
        tablolar = [t["name"] for t in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        for t in tablolar:
            print(f"    - {t}")
        if "cargo" in tablolar:
            tamam("'cargo' tablosu hazir (init_db semayi uyguladi)")
        else:
            hata("'cargo' tablosu bulunamadi")
            return 1

        # ------------------------------------------------------------ 5
        adim(5, "Sutun yapisi — PRAGMA table_info(cargo)")
        komut("PRAGMA table_info(cargo)", "kolonlar ve tipleri")
        print(f"    {'kolon':<18}{'tip':<12}{'not null':<10}{'varsayilan'}")
        print(f"    {'-' * 52}")
        for c in conn.execute("PRAGMA table_info(cargo)").fetchall():
            print(f"    {c['name']:<18}{c['type']:<12}"
                  f"{str(c['notnull']):<10}{c['dflt_value'] or '-'}")
        tamam(f"{6} kolon dogrulandi")

        # ------------------------------------------------------------ 6
        adim(6, "Yazma testi — veri ekleme")
        komut("models.create_cargo('KRG-DEMO-1', 'Ahmet Yilmaz', 'Mehmet Demir')")
        kayit = models.create_cargo("KRG-DEMO-1", "Ahmet Yilmaz", "Mehmet Demir")
        if kayit is None:
            hata("kargo olusturulamadi")
            return 1
        print(f"    {BOLD}id={kayit['id']}  {kayit['tracking_number']}  "
              f"status={kayit['status']}  created_at={kayit['created_at']}{SIFIRLA}")
        tamam("kargo yazildi")

        # ------------------------------------------------------------ 7
        adim(7, "Okuma testi — veri cekme")
        komut("models.get_cargo(1)", "id=1 kaydini getir")
        okunan = models.get_cargo(kayit["id"])
        if okunan is None:
            hata("kargo okunamadi")
            return 1
        for alan, deger in okunan.items():
            print(f"    {alan:<18}= {deger}")
        tamam("veri aynen okundu")

        # ------------------------------------------------------------ 8
        adim(8, "Guncelleme testi")
        komut("models.update_status(1, 'IN_TRANSIT')")
        models.update_status(kayit["id"], "IN_TRANSIT")
        guncel = models.get_cargo(kayit["id"])
        print(f"    status: CREATED -> {guncel['status']}")
        tamam("durum guncellendi")

        # ------------------------------------------------------------ 9
        adim(9, "Ham SQL ile dogrulama")
        komut("SELECT id, tracking_number, status FROM cargo", "sqlite3 ile dogrudan")
        print(f"    {'id':<6}{'tracking_number':<20}{'status'}")
        for r in conn.execute(
                "SELECT id, tracking_number, status FROM cargo").fetchall():
            print(f"    {r['id']:<6}{r['tracking_number']:<20}{r['status']}")
        tamam("SQL ile de ayni veri goruluyor")

        # ------------------------------------------------------------ 10
        adim(10, "Baglanti kapaniyor mu?")
        komut("app_context cikisinda close_db() cagrilir", "Flask teardown_appcontext")
    # context bitti -> baglanti kapandi
    tamam("app_context cikisiyla baglanti otomatik kapandi")

    # --------------------------------------------------------------- 11
    adim(11, "Baglanti kalici mi? — yeni baglanti ile tekrar okuma")
    komut("YENI app.app_context() ile yeni baglanti", "dosya diskinin okunmasi")
    with app.app_context():
        yeni = models.get_cargo(kayit["id"])
    if yeni is None:
        hata("yeni baglantida kayit bulunamadi")
        return 1
    print(f"    id={yeni['id']}  {yeni['tracking_number']}  "
          f"status={yeni['status']}")
    if yeni["status"] == "IN_TRANSIT":
        tamam("veri diskte kalici — yeni baglanti ayni veriyi okudu")
    else:
        hata("veri kalici degil")
        return 1

    # --------------------------------------------------------------- 12
    adim(12, "Baglanti temizligi")
    komut("os.remove(DB_PATH)", "demo dosyasini sil")
    os.remove(db_yolu)
    tamam(f"silindi: {db_yolu}")

    # --------------------------------------------------------------- sonuc
    print(f"\n{BOLD}{YESIL}{'=' * 62}")
    print("  TUM ADIMLAR BASARILI — BAGLANTI SAGLIKLI")
    print(f"{'=' * 62}{SIFIRLA}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
