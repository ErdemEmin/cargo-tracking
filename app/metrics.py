"""Prometheus metrikleri.

API içindeki her istek ve her kargo işlemi burada sayılır.
Counter/Histogram nesneleri modül seviyesinde bir kez üretilir; yeniden
import edildiğinde Prometheus registry'de kopya oluşmaması için
sentinel kontrolü yapılır.
"""
from prometheus_client import Counter, Histogram

# --- Kargo işlemleri ---
CARGO_CREATED = Counter(
    "cargo_created_total",
    "Toplam oluşturulan kargo sayısı",
)
CARGO_DELIVERED = Counter(
    "cargo_delivered_total",
    "Toplam teslim edilen kargo sayısı",
)
CARGO_CANCELLED = Counter(
    "cargo_cancelled_total",
    "Toplam iptal edilen kargo sayısı",
)
CARGO_STATUS_CHANGED = Counter(
    "cargo_status_changed_total",
    "Toplam kargo durum değişikliği sayısı",
)

# --- API istekleri ---
API_REQUEST_TOTAL = Counter(
    "api_request_total",
    "Toplam API isteği sayısı",
    ["method", "endpoint", "status"],
)
API_REQUEST_DURATION = Histogram(
    "api_request_duration_seconds",
    "API istek süresi (saniye)",
    ["method", "endpoint"],
)

# --- Consumer tarafında üretilen metrikler ---
CARGO_EVENTS_CONSUMED = Counter(
    "cargo_events_consumed_total",
    "Consumer'ın işlediği toplam Kafka event sayısı",
    ["event"],
)
