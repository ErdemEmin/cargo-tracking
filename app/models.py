"""SQLite veritabanı katmanı + kargo iş mantığı (CRUD)."""
import sqlite3

import click
from flask import current_app, g

# Kargonun alabileceği durumlar ve sıraları.
STATUSES = [
    "CREATED",
    "SHIPPED",
    "IN_TRANSIT",
    "OUT_FOR_DELIVERY",
    "DELIVERED",
    "CANCELLED",
]

# Bundan sonra kargo durumu değiştirilemez.
TERMINAL_STATUSES = {"DELIVERED", "CANCELLED"}


def get_db():
    """Bağlantıyı istek bağlamına açar, aynı istekte tekrar kullanır."""
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DB_PATH"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Tablonun var olduğundan emin olur."""
    db = get_db()
    db.executescript(current_app.config["SCHEMA"])
    db.commit()


# --------------------------------------------------------------------------
# CRUD
# --------------------------------------------------------------------------
def create_cargo(tracking_number, sender, receiver):
    """Yeni kargo ekler, sözlük olarak döndürür. ValueError → bozuk veri."""
    if not tracking_number or not str(tracking_number).strip():
        raise ValueError("tracking_number boş olamaz")
    if not sender or not str(sender).strip():
        raise ValueError("sender boş olamaz")
    if not receiver or not str(receiver).strip():
        raise ValueError("receiver boş olamaz")

    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO cargo (tracking_number, sender, receiver) "
            "VALUES (?, ?, ?)",
            (tracking_number.strip(), sender.strip(), receiver.strip()),
        )
        db.commit()
    except sqlite3.IntegrityError:
        raise ValueError("bu tracking number zaten kayıtlı")

    return get_cargo(cur.lastrowid)


def get_cargo(cargo_id):
    """Tek kargo döndürür; yoksa None."""
    db = get_db()
    row = db.execute("SELECT * FROM cargo WHERE id = ?", (cargo_id,)).fetchone()
    return dict(row) if row else None


def list_cargo(status=None, limit=100, offset=0):
    """Kargo listesi. status verilirse filtreler."""
    db = get_db()
    if status:
        cur = db.execute(
            "SELECT * FROM cargo WHERE status = ? "
            "ORDER BY id DESC LIMIT ? OFFSET ?",
            (status, limit, offset),
        )
    else:
        cur = db.execute(
            "SELECT * FROM cargo ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
    return [dict(r) for r in cur.fetchall()]


def update_status(cargo_id, new_status):
    """Durum değiştirir. ValueError → geçersiz durum / terminal kargo."""
    if new_status not in STATUSES:
        raise ValueError(f"geçersiz durum: {new_status}")

    cargo = get_cargo(cargo_id)
    if cargo is None:
        raise LookupError("kargo bulunamadı")
    if cargo["status"] in TERMINAL_STATUSES:
        raise ValueError(
            f"{cargo['status']} durumundaki kargo tekrar değiştirilemez"
        )

    db = get_db()
    db.execute(
        "UPDATE cargo SET status = ? WHERE id = ?", (new_status, cargo_id)
    )
    db.commit()
    return get_cargo(cargo_id)


def delete_cargo(cargo_id):
    """Kargoyu siler. Bulunamazsa False döner."""
    db = get_db()
    cur = db.execute("DELETE FROM cargo WHERE id = ?", (cargo_id,))
    db.commit()
    return cur.rowcount > 0


def count_by_status():
    """Duruma göre kargo sayıları (Grafana için)."""
    db = get_db()
    rows = db.execute(
        "SELECT status, COUNT(*) AS n FROM cargo GROUP BY status"
    ).fetchall()
    return {r["status"]: r["n"] for r in rows}


@click.command("init-db")
def init_db_command():
    """Tabloları oluşturur: flask init-db"""
    init_db()
    click.echo("veritabanı hazır.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
