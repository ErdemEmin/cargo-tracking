"""REST API rotaları."""
import time

from flask import Blueprint, current_app, jsonify, request
from prometheus_client import generate_latest

from app import kafka_producer as producer
from app import metrics, models

bp = Blueprint("api", __name__)


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
