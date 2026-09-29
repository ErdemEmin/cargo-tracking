"""REST API rotaları + kontrol paneli."""
import json
import time

from flask import (Blueprint, current_app, jsonify, render_template, request)
from prometheus_client import generate_latest

from app import kafka_producer as producer
from app import metrics, models
from config import Config

bp = Blueprint("api", __name__)

# Kontrol paneli icin yardimci servisler. Container icinde servis adi dogru
# adrestir; Flask local calistirildiginde localhost kullanilir.
_PROM_URLS = ("http://prometheus:9090", "http://localhost:9090")
_GRAFANA_URLS = ("http://grafana:3000", "http://localhost:3000")


def _fetch_json(bases, path, timeout=2.5):
    """Verilen adreslerden ilk calisani GET eder. (veri, hata) doner."""
    import urllib.request

    last = "bilinmiyor"
    for base in bases:
        try:
            with urllib.request.urlopen(base + path, timeout=timeout) as r:
                return json.load(r), None
        except Exception as exc:  # noqa: BLE001
            last = str(exc)
    return None, last


# --------------------------------------------------------------------------
# Prometheus metrik toplayıcıları
# --------------------------------------------------------------------------
@bp.before_request
def _start_timer():
    request.environ["_t0"] = time.perf_counter()


@bp.after_request
def _record_metrics(response):
    t0 = request.environ.get("_t0")
    if t0 is not None:
        metrics.API_REQUEST_DURATION.labels(
            method=request.method, endpoint=request.path
        ).observe(time.perf_counter() - t0)
    metrics.API_REQUEST_TOTAL.labels(
        method=request.method,
        endpoint=request.path,
        status=response.status_code,
    ).inc()
    return response


@bp.get("/metrics")
def prometheus_metrics():
    """Prometheus'un çektiği metrik çıktısı."""
    return current_app.response_class(
        generate_latest(), mimetype="text/plain; version=0.0.4"
    )


# --------------------------------------------------------------------------
# Kargo endpoint'leri
# --------------------------------------------------------------------------
@bp.get("/cargo")
def list_cargo():
    status = request.args.get("status")
    limit = int(request.args.get("limit", 100))
    offset = int(request.args.get("offset", 0))
    if status and status not in models.STATUSES:
        return jsonify({"error": f"geçersiz durum: {status}"}), 400
    items = models.list_cargo(status=status, limit=limit, offset=offset)
    return jsonify({"count": len(items), "items": items}), 200


@bp.post("/cargo")
def create_cargo():
    data = request.get_json(silent=True) or {}
    try:
        cargo = models.create_cargo(
            data.get("tracking_number"),
            data.get("sender"),
            data.get("receiver"),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    metrics.CARGO_CREATED.inc()
    producer.publish(
        "cargo.created",
        cargo["id"],
        tracking_number=cargo["tracking_number"],
        status=cargo["status"],
    )
    return jsonify(cargo), 201


@bp.get("/cargo/<int:cargo_id>")
def get_cargo(cargo_id):
    cargo = models.get_cargo(cargo_id)
    if cargo is None:
        return jsonify({"error": "kargo bulunamadı"}), 404
    return jsonify(cargo), 200


@bp.put("/cargo/<int:cargo_id>/status")
def update_status(cargo_id):
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    try:
        cargo = models.update_status(cargo_id, new_status)
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    metrics.CARGO_STATUS_CHANGED.inc()
    producer.publish(
        "cargo.status_changed",
        cargo["id"],
        tracking_number=cargo["tracking_number"],
        status=cargo["status"],
    )
    if cargo["status"] == "DELIVERED":
        metrics.CARGO_DELIVERED.inc()
        producer.publish("cargo.delivered", cargo["id"],
                         tracking_number=cargo["tracking_number"])
    elif cargo["status"] == "CANCELLED":
        metrics.CARGO_CANCELLED.inc()
        producer.publish("cargo.cancelled", cargo["id"],
                         tracking_number=cargo["tracking_number"])
    return jsonify(cargo), 200


@bp.delete("/cargo/<int:cargo_id>")
def delete_cargo(cargo_id):
    if not models.delete_cargo(cargo_id):
        return jsonify({"error": "kargo bulunamadı"}), 404
    producer.publish("cargo.deleted", cargo_id)
    return jsonify({"message": "kargo silindi", "id": cargo_id}), 200


@bp.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "kafka": producer.healthcheck(),
        "counts": models.count_by_status(),
    }), 200


# --------------------------------------------------------------------------
# Kontrol paneli (demo arayuzu)
# --------------------------------------------------------------------------
@bp.get("/")
@bp.get("/panel")
def panel():
    """Hocaya gosterilecek tek ekran: islemler + event akisi + metrikler."""
    return render_template("dashboard.html")


@bp.get("/api/kafka")
def api_kafka():
    """Panel rozeti icin broker durumu."""
    return jsonify({
        "connected": producer.healthcheck(),
        "bootstrap": Config.KAFKA_BOOTSTRAP,
        "topic": Config.KAFKA_TOPIC,
    })


@bp.get("/api/prom")
def api_prom():
    """Prometheus hedeflerinin up/down durumu.

    Container icinden localhost degil servis adi kullanilir; local calistirmada
    (docker disi) localhost dogru adrestir, bu yuzden once biri denenir.
    """
    body, err = _fetch_json(_PROM_URLS, "/api/v1/targets")
    if err or not isinstance(body, dict):
        return jsonify({"up": False, "error": err or "hata", "targets": {}})
    try:
        targets = body["data"]["activeTargets"]
    except (KeyError, TypeError):
        return jsonify({"up": False, "error": "beklenmeyen yanit", "targets": {}})
    return jsonify({
        "up": bool(targets) and all(t["health"] == "up" for t in targets),
        "targets": {t["labels"]["job"]: t["health"] for t in targets},
    })


@bp.get("/api/grafana")
def api_grafana():
    """Grafana ayakta mi?"""
    body, err = _fetch_json(_GRAFANA_URLS, "/api/health")
    if err or not isinstance(body, dict):
        return jsonify({"up": False, "error": err or "hata"})
    return jsonify({"up": True, **body})
