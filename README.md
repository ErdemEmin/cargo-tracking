# Kafka ve Grafana Tabanlı Kargo Takip Sistemi

Olay tabanlı (event-driven) mimariyle çalışan bir kargo takip sistemi.
Flask REST API → Kafka → Consumer → Prometheus → Grafana zinciri tek komutla ayağa kalkar.

## Teslim Dokümanları

| Doküman | Dosya | Açıklama |
|---|---|---|
| **Proje Raporu (PDF)** | [`Kargo_Takip_Sistemi_Raporu.pdf`](Kargo_Takip_Sistemi_Raporu.pdf) | 13 sayfa, 12 başlıklı white paper — teslim için bu kullanılır |
| Rapor kaynağı | [`RAPOR.md`](RAPOR.md) | Markdown hali, GitHub'da düzenlenebilir |
| **Sunum (PPTX)** | [`Kargo_Takip_Sistemi_Sunum.pptx`](Kargo_Takip_Sistemi_Sunum.pptx) | 12 slayt, her slaytta konuşmacı notu var |
| Dashboard görseli | [`docs/grafana-dashboard.png`](docs/grafana-dashboard.png) | Grafana dashboard ekran görüntüsü (10 panel, canlı veri) |
| Uygulama planı | [`PLAN.md`](PLAN.md) | Aşama planı ve teknik kararlar |

### Sunum / Demo Nasıl Yapılır

```bash
# 1) Servisleri ayağa kaldır
docker compose up -d

# 2) Demo akışını çalıştır (9 adım: kargo → Kafka → consumer → metrikler)
bash scripts/demo.sh
```

Ardından tarayıcıda:

| Adres | Ne gösterir |
|---|---|
| http://localhost:5000 | REST API |
| http://localhost:9091/metrics | Consumer metrikleri |
| http://localhost:9090/targets | Prometheus hedefleri (`cargo-api up`, `cargo-consumer up`) |
| http://localhost:3000 | Grafana dashboard (admin / admin) |

Demo sırasında bakılacak en önemli nokta: **API'nin ürettiği sayaçlar ile
consumer'ın saydığı event sayısı birebir aynıdır** (oluşturma 20, durum değişikliği 17,
teslim 5, iptal 2). Bu, event'lerin kayıpsız iletildiğinin kanıtıdır.

---

## Mimari

```
Client
  │  POST /cargo
  ▼
Flask API ──────→ SQLite (kargo kaydı)
  │                     │
  │                     └── durum değişimleri
  ▼
Kafka (cargo-events)
  │
  ▼
Consumer (event'i okur, işler, loglar)
  │
  ▼
Prometheus (:9090, iki hedefi toplar: flask:5000 + consumer:9091)
  │
  ▼
Grafana (:3000)
```

## Tek komutla çalıştırma

```bash
docker compose up -d --build
docker compose ps
```

| Servis | Adres | Açıklama |
|---|---|---|
| Flask API | http://localhost:5000 | REST API |
| API metrikleri | http://localhost:5000/metrics | Prometheus formatı |
| Consumer metrikleri | http://localhost:9091/metrics | Event sayaçları |
| Prometheus | http://localhost:9090 | Toplayıcı |
| Grafana | http://localhost:3000 | admin / admin |

## Lokal geliştirme (Docker'sız)

```bash
python -m venv venv
venv/Scripts/activate
pip install -r requirements.txt
python run.py
```

Consumer'ı ayrı terminalde: `python consumer/consumer.py`
Kafka olmadan da API ve testler çalışır (producer tembel bağlanır, Kafka yoksa event düşer).

## API

| Metot | Yol | Açıklama |
|---|---|---|
| POST | `/cargo` | Kargo oluştur → 201 |
| GET | `/cargo` | Liste (`?status=`, `?limit=`, `?offset=`) |
| GET | `/cargo/<id>` | Tek kargo → 404 yoksa |
| PUT | `/cargo/<id>/status` | Durum değiştir (`{"status": "IN_TRANSIT"}`) |
| DELETE | `/cargo/<id>` | Sil |
| GET | `/health` | Durum + kargo sayıları |
| GET | `/metrics` | Prometheus metrikleri |

### Durumlar

`CREATED → SHIPPED → IN_TRANSIT → OUT_FOR_DELIVERY → DELIVERED`
`CANCELLED` herhangi bir aşamada.

`DELIVERED` ve `CANCELLED` **terminal** durumlardır: bu kargoların durumu bir daha değiştirilemez, API 400 döner.

### Örnek

```bash
curl -X POST http://localhost:5000/cargo \
  -H 'Content-Type: application/json' \
  -d '{"tracking_number":"KRG-1001","sender":"Ahmet","receiver":"Mehmet"}'
```

```json
{"id": 1, "tracking_number": "KRG-1001", "sender": "Ahmet",
 "receiver": "Mehmet", "status": "CREATED", "created_at": "2026-09-26 13:40:00"}
```

## Kafka Event'leri

Topic: `cargo-events`

| Event | Ne zaman |
|---|---|
| `cargo.created` | Kargo oluşturuldu |
| `cargo.status_changed` | Durum değişti |
| `cargo.delivered` | Teslim edildi |
| `cargo.cancelled` | İptal edildi |
| `cargo.deleted` | Silindi |

```json
{"event": "cargo.created", "cargo_id": 1, "tracking_number": "KRG-1001", "status": "CREATED"}
```

Consumer terminalde şunu basar:
```
[cargo.created@0] Cargo 1 created. (tracking: KRG-1001)
[cargo.delivered@0] Cargo 15 delivered.
```

## Metrikler

API: `cargo_created_total`, `cargo_delivered_total`, `cargo_cancelled_total`,
`cargo_status_changed_total`, `api_request_total{method,endpoint,status}`,
`api_request_duration_seconds{method,endpoint}`

Consumer: `cargo_events_consumed_total{event}`, `cargo_consumer_status_total{status}`,
`cargo_event_last_timestamp_seconds`

## Testler

```bash
venv/Scripts/python.exe -m pytest -q        # 13 test
bash scripts/full_flow_test.sh               # 20 kargoluk tam akış senaryosu
```

Testler Kafkasız çalışır; her test kendi geçici SQLite'ını kullanır (`tmp_path`).

## Proje Yapısı

```
cargo-tracking/
├── app/
│   ├── __init__.py          application factory
│   ├── routes.py            REST endpoint'leri + metrik toplayıcıları
│   ├── models.py            SQLite CRUD + iş kuralları (terminal durumlar)
│   ├── kafka_producer.py    lazy-connect producer
│   └── metrics.py           Prometheus metrik tanımları
├── consumer/consumer.py     Kafka consumer + metrik sunucusu (:9091)
├── deploy/
│   ├── prometheus/prometheus.yml
│   └── grafana/provisioning/   datasource + dashboard
├── tests/test_cargo.py      13 pytest testi
├── scripts/full_flow_test.sh
├── config.py
├── run.py
├── Dockerfile
└── docker-compose.yml
```

## Teknik Notlar

- **Kafka imajı:** `apache/kafka:3.7.1` — resmî imaj, KRaft modu (ZooKeeper yok).
  İki listener: `PLAINTEXT://kafka:9092` (container'lar arası) ve `EXTERNAL://localhost:29092` (host'tan).
- **Producer dayanıklılığı:** Kafka ayakta değilse API düşmez; event kaybolur ve loglanır.
  Bu sayede API ve testler Kafka'dan bağımsız doğrulanabilir.
- **Prometheus tek kaynak:** hem API hem consumer metrikleri aynı registry'ye yazılır,
  iki ayrı hedef olarak scrape edilir; Grafana sorgularını birleştirir (`sum(...)`).
- **Docker volume:** SQLite `cargo-data` volume'unda kalıcıdır; `docker compose down -v` ile silinir.
- **Grafana provisioning:** dashboard JSON'u dosyadan yüklenir, container yeniden başlasa da korunur.
