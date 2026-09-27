#!/usr/bin/env bash
# Sunum canlı demo komutları — bu dosyayı terminalde çalıştır, çıktıları göster.
# Her adımda: komutu çalıştır → çıktıyı göster → tarayıcıda ilgili sayfayı yenile.

API="http://localhost:5000"
say() { printf '\n\033[1;36m▸ %s\033[0m\n' "$1"; }

# ---------- ADIM 1: kargo oluştur (Kafka'ya event gönderir) ----------
say "1) Kargo oluşturuluyor → Kafka'ya cargo.created gider"
curl -s -X POST "$API/cargo" -H 'Content-Type: application/json' \
  -d '{"tracking_number":"KRG-DEMO-1","sender":"Ahmet Yilmaz","receiver":"Mehmet Demir"}' \
  | python -m json.tool

# ---------- ADIM 2: durum değiştir ----------
say "2) Durum değiştiriliyor → cargo.status_changed gider"
curl -s -X PUT "$API/cargo/1/status" -H 'Content-Type: application/json' \
  -d '{"status":"IN_TRANSIT"}' | python -m json.tool

say "3) Teslim ediliyor → cargo.delivered gider"
curl -s -X PUT "$API/cargo/1/status" -H 'Content-Type: application/json' \
  -d '{"status":"DELIVERED"}' | python -m json.tool

# ---------- ADIM 4: terminal durum koruması (400 dönmeli) ----------
say "4) Terminal durum koruması — teslim edilmiş kargo tekrar dağıtılamaz"
curl -s -w "\nHTTP kodu: %{http_code}\n" -X PUT "$API/cargo/1/status" \
  -H 'Content-Type: application/json' -d '{"status":"OUT_FOR_DELIVERY"}' | python -m json.tool 2>/dev/null \
  || curl -s -X PUT "$API/cargo/1/status" -H 'Content-Type: application/json' \
       -d '{"status":"OUT_FOR_DELIVERY"}'
echo "(beklenen: 400 - 'DELIVERED durumundaki kargo tekrar degistirilemez')"

# ---------- ADIM 5: Kafka event'leri (consumer terminalinde) ----------
say "5) Kafka event'leri — consumer bunları okuyup işledi"
docker compose logs --tail=6 consumer 2>&1 | grep -E "cargo\." || echo "(consumer loglarını aç)"

# ---------- ADIM 6: metrikler ----------
say "6) API metrikleri (http://localhost:5000/metrics)"
curl -s "$API/metrics" | grep -E "^cargo_(created|delivered|cancelled|status_changed)_total "

say "7) Consumer metrikleri (http://localhost:9091/metrics)"
curl -s http://localhost:9091/metrics | grep -E "^cargo_events_consumed_total"

say "8) Prometheus hedefleri (http://localhost:9090/targets)"
curl -s 'http://localhost:9090/api/v1/targets' | python -c "
import sys, json
for t in json.load(sys.stdin)['data']['activeTargets']:
    print(f\"  {t['labels']['job']:<16} {t['health']}\")
"

say "9) Veritabanı durumu (http://localhost:5000/health)"
curl -s "$API/health" | python -m json.tool

printf '\n\033[1;32m▸ Şimdi tarayıcıda: http://localhost:3000 → dashboard sayılarını güncelle\033[0m\n'
