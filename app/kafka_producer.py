"""Kafka Producer.

Tasarım kararı: producer tembel (lazy) bağlanır ve Kafka ayakta değilse
API'yi DÜŞÜRMEZ. Böylece Aşama 2-3 (API + testler) Kafka kurulmadan da
çalışır; event kaybı olursa terminal loguna uyarı düşer.
"""
import atexit
import json
import logging
import threading

from config import Config

log = logging.getLogger(__name__)

_producer = None
_lock = threading.Lock()


def _get_producer():
    """KafkaProducer'ı ilk kullanımda oluşturur, bağlantı yoksa None döner."""
    global _producer
    if not Config.KAFKA_ENABLED:
        return None
    if _producer is not None:
        return _producer

    with _lock:
        if _producer is not None:
            return _producer
        try:
            from kafka import KafkaProducer

            _producer = KafkaProducer(
                bootstrap_servers=Config.KAFKA_BOOTSTRAP,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: str(k).encode("utf-8"),
                acks=1,
                retries=3,
                request_timeout_ms=3000,
                max_block_ms=3000,
                api_version_auto_timeout_ms=3000,
            )
            log.info("Kafka producer bağlandı: %s", Config.KAFKA_BOOTSTRAP)
        except Exception as exc:  # noqa: BLE001
            log.warning("Kafka'ya bağlanılamadı (%s). Event'ler gönderilmeyecek.", exc)
            return None
    return _producer


@atexit.register
def _close():
    if _producer is not None:
        try:
            _producer.flush(timeout=3)
            _producer.close(timeout=3)
        except Exception:  # noqa: BLE001
            pass


def publish(event, cargo_id, tracking_number=None, status=None, **extra):
    """cargo-events topic'ine JSON event gönderir. Başarısızlıkta False."""
    payload = {"event": event, "cargo_id": cargo_id}
    if tracking_number is not None:
        payload["tracking_number"] = tracking_number
    if status is not None:
        payload["status"] = status
    payload.update(extra)

    producer = _get_producer()
    if producer is None:
        return False
    try:
        producer.send(Config.KAFKA_TOPIC, key=cargo_id, value=payload)
        producer.flush(timeout=5)
        log.info("Kafka'ya gönderildi: %s", payload)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("Kafka gönderimi başarısız (%s): %s", event, exc)
        return False


def healthcheck():
    """Broker erişilebilir mi? (Docker healthcheck için)"""
    producer = _get_producer()
    if producer is None:
        return False
    try:
        return bool(producer.bootstrap_connected())
    except Exception:  # noqa: BLE001
        return False
