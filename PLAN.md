# Kargo Takip Sistemi — Uygulama Planı

## Mimari
```
Client → Flask API (SQLite + Kafka Producer)
              ↓                      ↓
           SQLite              Kafka (cargo-events)
                                     ↓
                              Consumer (ayrı servis)
                                     ↓
                              Prometheus (/metrics)
                                     ↓
                                 Grafana
```

## Aşamalar

| # | Aşama | Çıktı | Durum |
|---|-------|-------|-------|
| 1 | Proje iskeleti | klasör yapısı, venv, requirements.txt | ☐ |
| 2 | Flask REST API + SQLite | 5 endpoint, çalışır durumda | ☐ |
| 3 | Unit Test | ≥8 pytest testi, hepsi geçer | ☐ |
| 4 | Kafka Producer | topic: cargo-events, 3 event tipi | ☐ |
| 5 | Kafka Consumer | terminal log çıktısı | ☐ |
| 6 | Prometheus | 6 metrik + /metrics endpoint | ☐ |
| 7 | Grafana | dashboard (5 panel) | ☐ |
| 8 | Docker Compose | 5 servis, tek komut | ☐ |
| 9 | Tam akış testi | 20 kargo senaryosu | ☐ |
| 10 | Rapor + sunum | README.md (12 başlık) | ☐ |

## Kritik kararlar
- **Kafka imajı:** `bitnami/kafka:3.7` (KRaft modu, ZooKeeper yok)
- **DB:** SQLite, `app/db.py` üzerinden `get_db()` factory
- **Kafka erişilebilirliği:** Producer lazy-connect; Kafka yoksa API çökmez, sadece event düşer (log uyarısı)
- **Test izolasyonu:** pytest'ta `tmp_path` ile geçici SQLite, her test kendi DB'si
- **State geçişleri:** DELIVERED ve CANCELLED terminal durum → yeniden değiştirilemez (Test 6)
- **Metrikler:** `prometheus_client`, `/metrics` endpoint'i consumer'da da ayrı exposition portu (9091) ile sunulur
- **Docker:** flask/consumer Dockerfile, `kafka` + `zookeeper` yerine KRaft; sqlite volume mount

## Ortam
- Python 3.11.15 (sistem) — venv ile izole
- Docker 29.1.2 / Compose v2.40.3 — kurulu ✓
