"""Uygulama geneli yapılandırma ayarları."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    # --- Flask ---
    SECRET_KEY = os.getenv("SECRET_KEY", "cargo-tracking-dev-key")

    # --- SQLite ---
    DB_PATH = os.getenv("DB_PATH", os.path.join(BASE_DIR, "cargo.db"))
    SCHEMA = """
        CREATE TABLE IF NOT EXISTS cargo (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            tracking_number TEXT    NOT NULL UNIQUE,
            sender          TEXT    NOT NULL,
            receiver        TEXT    NOT NULL,
            status          TEXT    NOT NULL DEFAULT 'CREATED',
            created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
        );
    """

    # --- Kafka ---
    KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
    KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "cargo-events")
    KAFKA_ENABLED = os.getenv("KAFKA_ENABLED", "1") == "1"

    # --- Prometheus ---
    METRICS_PORT = int(os.getenv("METRICS_PORT", "9091"))
