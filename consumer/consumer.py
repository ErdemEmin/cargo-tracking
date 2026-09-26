"""Kafka Consumer — Aşama 5.

cargo-events topic'inden event'leri okur, işler ve Prometheus metriğini
artırır. Metriklerini 9091 portunda ayrı bir HTTP sunucusunda açar; Flask
API'deki metriklerle birlikte Prometheus ikisini de toplar.
"""
import json
import logging
import os
import signal
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("KAFKA_BOOTSTRAP", "localhost:9092")

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest  # noqa: E402

from config import Config  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("consumer")

# --- Consumer metrikleri ---
CARGO_EVENTS_CONSUMED = Counter(
    "cargo_events_consumed_total",
    "Consumer'in isledigi toplam Kafka event sayisi",
    ["event"],
)
EVENT_LAST_SEEN = Gauge(
    "cargo_event_last_timestamp_seconds",
    "En son islenen event'in Unix zaman damgasi",
)
CARGO_BY_STATUS = Gauge(
    "cargo_consumer_status_total",
    "Event basina gorulen kargo durumu",
    ["status"],
)


class MetricsHandler(BaseHTTPRequestHandler):
    """Prometheus'un metrikleri cektigi HTTP ucu."""

    def do_GET(self):  # noqa: N802
        if self.path == "/metrics":
            body = generate_latest().decode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPE_LATEST)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))
        else:
            self.send_error(404)

    def log_message(self, fmt, *args):
        pass  # erisim loglarini sustur


def start_metrics_server(port):
    server = HTTPServer(("0.0.0.0", port), MetricsHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    log.info("Consumer metrik sunucusu: http://0.0.0.0:%d/metrics", port)
    return server


def describe(data):
    """Event'e gore anlamli terminal mesaji uretir."""
    name = data.get("event", "unknown")
    cid = data.get("cargo_id", "?")
    if name == "cargo.created":
        return f"Cargo {cid} created. (tracking: {data.get('tracking_number')})"
    if name == "cargo.status_changed":
        return f"Cargo {cid} status changed to {data.get('status')}."
    if name == "cargo.delivered":
        return f"Cargo {cid} delivered."
    if name == "cargo.cancelled":
        return f"Cargo {cid} cancelled."
    if name == "cargo.deleted":
        return f"Cargo {cid} deleted."
    return f"Cargo {cid} event: {name}"


_running = True


def _stop(signum, frame):  # noqa: ARG001
    global _running
    log.info("Shutdown sinyali alindi, kapaniyor...")
    _running = False


def main():
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    start_metrics_server(Config.METRICS_PORT)

    from kafka import KafkaConsumer

    log.info("Kafka'ya baglaniliyor: %s", Config.KAFKA_BOOTSTRAP)
    consumer = KafkaConsumer(
        Config.KAFKA_TOPIC,
        bootstrap_servers=Config.KAFKA_BOOTSTRAP,
        group_id="cargo-consumer-group",
        auto_offset_reset="latest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        consumer_timeout_ms=1000,
    )
    log.info("Topic dinleniyor: %s (group: cargo-consumer-group)", Config.KAFKA_TOPIC)
    log.info("Bekleniyor... (event gondermek icin: POST http://localhost:5000/cargo)")

    try:
        while _running:
            for msg in consumer:
                if not _running:
                    break
                data = msg.value
                event = data.get("event", "unknown")
                CARGO_EVENTS_CONSUMED.labels(event=event).inc()
                EVENT_LAST_SEEN.set(time.time())
                if data.get("status"):
                    CARGO_BY_STATUS.labels(status=data["status"]).inc()
                log.info("[%s@%d] %s", event, msg.partition, describe(data))
    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()
        log.info("Consumer kapandi.")


if __name__ == "__main__":
    main()
