#!/usr/bin/env bash
# Aşama 11 — Tam akış senaryosu.
# 20 kargo oluştur -> 10 IN_TRANSIT -> 5 DELIVERED -> 2 CANCELLED
# Kafka mesajlarını, metrikleri ve servisleri doğrular.
set -euo pipefail

API="${API:-http://localhost:5000}"
CONSUMER_LOG="${CONSUMER_LOG:-/tmp/cargo-consumer.log}"

say() { printf '\n\033[1;36m=== %s ===\033[0m\n' "$1"; }

say "0) Servis durumu"
docker compose ps

say "1) 20 kargo oluşturuluyor"
IDS=()
for i in $(seq 1 20); do
  R=$(curl -s -X POST "$API/cargo" \
    -H 'Content-Type: application/json' \
    -d "{\"tracking_number\":\"KRG-2026-$i\",\"sender\":\"Gonderici $i\",\"receiver\":\"Alici $i\"}")
  ID=$(printf '%s' "$R" | python -c 'import sys,json;print(json.load(sys.stdin)["id"])')
  IDS+=("$ID")
done
echo "oluşturulan id'ler: ${IDS[*]}"

say "2) İlk 10 kargo -> IN_TRANSIT"
for id in "${IDS[@]:0:10}"; do
  curl -s -X PUT "$API/cargo/$id/status" \
    -H 'Content-Type: application/json' -d '{"status":"IN_TRANSIT"}' > /dev/null
  printf 'cargo %s -> IN_TRANSIT\n' "$id"
done

say "3) Sonraki 5 kargo -> DELIVERED"
for id in "${IDS[@]:10:5}"; do
  curl -s -X PUT "$API/cargo/$id/status" \
    -H 'Content-Type: application/json' -d '{"status":"DELIVERED"}' > /dev/null
  printf 'cargo %s -> DELIVERED\n' "$id"
done

say "4) Sonraki 2 kargo -> CANCELLED"
for id in "${IDS[@]:15:2}"; do
  curl -s -X PUT "$API/cargo/$id/status" \
    -H 'Content-Type: application/json' -d '{"status":"CANCELLED"}' > /dev/null
  printf 'cargo %s -> CANCELLED\n' "$id"
done

say "5) Terminal durum koruması (DELIVERED geri alınamaz)"
CODE=$(curl -s -o /dev/null -w '%{http_code}' -X PUT "$API/cargo/${IDS[10]}/status" \
  -H 'Content-Type: application/json' -d '{"status":"OUT_FOR_DELIVERY"}')
echo "beklenen 400, gelen $CODE"
[ "$CODE" = "400" ] || { echo "HATA: terminal durum koruması çalışmadı"; exit 1; }

say "6) Kafka mesajları (consumer log)"
docker compose logs --tail=40 consumer | grep -E 'cargo\.(created|status_changed|delivered|cancelled|deleted)' || echo "log'da event yok"

say "7) Prometheus metrikleri (API)"
curl -s "$API/metrics" | grep -E '^cargo_(created|delivered|cancelled|status_changed)_total ' || true

say "8) Prometheus metrikleri (consumer)"
curl -s "http://localhost:9091/metrics" | grep -E '^cargo_events_consumed_total|^cargo_consumer_status_total' | head -20 || true

say "9) Prometheus hedef durumu"
curl -s 'http://localhost:9090/api/v1/targets' | python -c '
import sys,json
d=json.load(sys.stdin)["data"]["activeTargets"]
for t in d: print(f'"'"'{t["labels"]["job"]:<15} {t["health"]}'"'"')
'

say "10) PyTest"
venv/Scripts/python.exe -m pytest -q || venv/bin/python -m pytest -q

say "11) Health"
curl -s "$API/health" | python -m json.tool

say "12) Beklenen sonuç"
echo "Toplam: 20 | IN_TRANSIT: 10 | DELIVERED: 5 | CANCELLED: 2 | CREATED: 3"
curl -s "$API/health" | python -c '
import sys,json
c=json.load(sys.stdin)["counts"]
print("veritabanı:", c)
exp={"CREATED":3,"IN_TRANSIT":10,"DELIVERED":5,"CANCELLED":2}
assert all(c.get(k,0)==v for k,v in exp.items()), f"Beklenen {exp}, gelen {c}"
print("DOGRULAMA BASARILI")
'
