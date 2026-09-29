"""Slaytlari yeniden uretir: title_only layout + asagida konumlandirilmis
tablo, diyagram veya madde listesi. Ust uste binme sorunu bu duzeni cozuyor
(onceki 'title_content' layout'unda tablo ve bullet listesi ayni yere yaziliyordu).
"""
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "Kargo_Takip_Sistemi_Sunum.pptx"

W, H = Inches(13.333), Inches(7.5)
ACCENT = RGBColor(0x1F, 0x6F, 0xEB)
DARK = RGBColor(0x0B, 0x25, 0x45)
ORANGE = RGBColor(0xE8, 0x5D, 0x04)
SLATE = RGBColor(0x3D, 0x5A, 0x80)
GREY = RGBColor(0x82, 0x9A, 0xB1)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
MUTED = RGBColor(0x60, 0x6B, 0x7A)
LIGHT = RGBColor(0xF4, 0xF6, 0xF8)

prs = Presentation()
prs.slide_width, prs.slide_height = W, H
BLANK = prs.slide_layouts[6]


def tb(slide, text, l, t, w, h, size=18, bold=False, color=DARK,
       align=PP_ALIGN.LEFT, font="Arial", spacing=1.0):
    """Tek parca metin kutusu."""
    box = slide.shapes.add_textbox(l, t, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    p.line_spacing = spacing
    r = p.add_run()
    r.text = text
    r.font.size, r.font.bold, r.font.name = Pt(size), bold, font
    r.font.color.rgb = color
    return box


def bullets(slide, items, l, t, w, h, size=15, color=DARK, gap=8):
    """Madde listesi."""
    box = slide.shapes.add_textbox(l, t, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(gap)
        p.line_spacing = 1.15
        r = p.add_run()
        r.text = ("•  " + item) if isinstance(item, str) else "•  "
        r.font.size, r.font.name = Pt(size), "Arial"
        r.font.color.rgb = color
        if not isinstance(item, str):
            r.text = "•  " + item[0]
            r.font.size = Pt(item[1]) if len(item) > 1 else Pt(size)
            r.font.bold = len(item) > 2 and item[2] == "b"
    return box


def title(slide, text, color=DARK, size=30):
    tb(slide, text, Inches(0.6), Inches(0.35), Inches(12.1), Inches(0.8),
       size=size, bold=True, color=color)


def rect(slide, text, l, t, w, h, fill, tcolor=WHITE, size=11, shape=1):
    """Dolu dikdortgen/ok + icinde yazi."""
    from pptx.enum.shapes import MSO_SHAPE
    kinds = {1: MSO_SHAPE.ROUNDED_RECTANGLE, 2: MSO_SHAPE.CHEVRON,
             3: MSO_SHAPE.OVAL, 4: MSO_SHAPE.RECTANGLE}
    s = slide.shapes.add_shape(kinds[shape], l, t, w, h)
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    s.line.fill.background()
    tf = s.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Emu(45720)
    tf.margin_top = tf.margin_bottom = Emu(22860)
    for i, line in enumerate(text.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = line
        r.font.size, r.font.name = Pt(size), "Arial"
        r.font.color.rgb = tcolor
        r.font.bold = True
    return s


def table(slide, rows, l, t, w, col_w=None, row_h=0.32, size=11):
    """Baslik satiri koyu renkli tablo."""
    nr, nc = len(rows), len(rows[0])
    gt = slide.shapes.add_table(nr, nc, l, t, w, Inches(row_h * nr)).table
    if col_w:
        total = sum(col_w)
        for i, cw in enumerate(col_w):
            gt.columns[i].width = Emu(int(w * cw / total))
    for ri, row in enumerate(rows):
        gt.rows[ri].height = Inches(row_h)
        for ci, cell in enumerate(row):
            c = gt.cell(ri, ci)
            c.text = str(cell)
            c.margin_left = c.margin_right = Emu(64008)
            c.margin_top = c.margin_bottom = Emu(27432)
            c.vertical_anchor = 3  # middle
            p = c.text_frame.paragraphs[0]
            r = p.runs[0] if p.runs else p.add_run()
            r.font.size, r.font.name = Pt(size), "Arial"
            r.font.bold = (ri == 0)
            r.font.color.rgb = WHITE if ri == 0 else DARK
            c.fill.solid()
            c.fill.fore_color.rgb = ACCENT if ri == 0 else (
                WHITE if ri % 2 else LIGHT)
    return gt


def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def new(bg=None):
    s = prs.slides.add_slide(BLANK)
    if bg:
        s.background.fill.solid()
        s.background.fill.fore_color.rgb = bg
    return s


# ---------------------------------------------------------------- 1 Kapak
s = new(DARK)
tb(s, "Kafka ve Grafana Tabanlı", Inches(0.9), Inches(2.5), Inches(11.5),
   Inches(0.7), size=40, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
tb(s, "Kargo Takip Sistemi", Inches(0.9), Inches(3.25), Inches(11.5),
   Inches(0.7), size=40, bold=True, color=ACCENT, align=PP_ALIGN.CENTER)
tb(s, "Olay tabanlı mimari ile izlenebilir bir REST API", Inches(0.9),
   Inches(4.25), Inches(11.5), Inches(0.4), size=16, color=GREY,
   align=PP_ALIGN.CENTER)
tb(s, "Erdem Emin", Inches(0.9), Inches(5.5), Inches(11.5), Inches(0.4),
   size=15, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
notes(s, "Projenin amacı yalnızca çalışan bir REST API geliştirmek değil; uçtan uca "
         "kod yazma → test etme → olay üretme → olay tüketme → ölçme → "
         "görselleştirme → container'da çalıştırma zincirini kurmak.")

# ---------------------------------------------------------------- 2 Problem
s = new()
title(s, "Problem ve Çözüm")
bullets(s, [
    "Kargo durumu değişiklikleri birden fazla servise bildirilmelidir",
    "Klasik yaklaşımda API her bileşene doğrudan bağlanır → sıkı bağımlılık",
    "Çözüm: olay tabanlı mimari — API sadece olayı üretir, bağlı olanlar dinler",
    "Sonuç: API yavaşlasa bile event'ler kaybolmaz, yeni servisler kolayca eklenir",
    "Bu projede: Flask → Kafka → Consumer → Prometheus → Grafana",
], Inches(0.75), Inches(1.5), Inches(11.8), Inches(4.2), size=18, gap=14)
notes(s, "Kargo oluştuğunda birden çok tarafı haberdar etmem gerekiyor. Doğrudan "
         "çağırsam API yavaşlar ve biri çökerse tüm zincir düşer. Kafka tampon "
         "görevi görür: event yazılır, ilgilenenler sonra kendi hızında okur.")

# ---------------------------------------------------------------- 3 Mimari
s = new()
title(s, "Sistem Mimarisi")
D = Inches
rect(s, "Client", D(0.55), D(1.45), D(1.25), D(0.55), ACCENT, size=12)
rect(s, "POST /cargo", D(1.95), D(1.58), D(1.45), D(0.3), GREY, DARK, size=9, shape=2)
rect(s, "Flask API\n:5000", D(3.55), D(1.3), D(1.9), D(0.85), ACCENT, size=12)
rect(s, "SQLite\nkargo kaydı", D(0.55), D(2.6), D(1.6), D(0.75), SLATE, size=11)
rect(s, "kaydeder + event üretir", D(2.2), D(2.75), D(1.3), D(0.32), GREY, DARK, size=8, shape=2)
rect(s, "Kafka\ncargo-events\n:9092", D(6.1), D(1.3), D(2.1), D(1.0), DARK, size=11)
rect(s, "event gönderir", D(5.35), D(1.62), D(0.7), D(0.3), GREY, DARK, size=7, shape=2)
rect(s, "event okunur", D(6.75), D(2.55), D(0.8), D(0.3), GREY, DARK, size=7, shape=2)
rect(s, "Consumer\n:9091", D(6.1), D(3.05), D(2.1), D(0.8), DARK, size=12)
rect(s, "metrik üretir", D(8.35), D(3.28), D(0.85), D(0.3), GREY, DARK, size=7, shape=2)
rect(s, "Prometheus\n:9090", D(9.35), D(3.05), D(2.0), D(0.8), ORANGE, size=12)
rect(s, "sorgular", D(9.75), D(2.55), D(1.2), D(0.3), GREY, DARK, size=7, shape=2)
rect(s, "Grafana\n:3000", D(9.35), D(1.3), D(2.0), D(0.8), ORANGE, size=12)
rect(s, "tek komutla ayağa kalkar:  docker compose up -d", D(0.75), D(4.55),
     D(11.8), D(0.5), LIGHT, DARK, size=13, shape=4)
notes(s, "Akışı soldan sağa takip et. API iki iş yapar: SQLite'a yazar, Kafka'ya "
         "event gönderir. Consumer event'i okuyup işler ve kendi metrik sayacını "
         "artırır. Prometheus iki hedefi scrape eder, Grafana sorgular.")

# ---------------------------------------------------------------- 4 API
s = new()
title(s, "REST API ve Durum Makinesi")
table(s, [
    ["Metot", "Yol", "İşlev", "Yanıt"],
    ["POST", "/cargo", "Kargo oluştur", "201"],
    ["GET", "/cargo", "Listele + filtrele", "200"],
    ["GET", "/cargo/<id>", "Tek kargo", "404"],
    ["PUT", "/cargo/<id>/status", "Durum değiştir", "200/400"],
    ["DELETE", "/cargo/<id>", "Sil", "200/404"],
], Inches(0.75), Inches(1.45), Inches(11.8), col_w=[1.4, 3.0, 3.4, 1.5])
tb(s, "Durum akışı", Inches(0.75), Inches(3.85), Inches(11.8), Inches(0.35),
   size=15, bold=True, color=ACCENT)
rect(s, "CREATED  →  SHIPPED  →  IN_TRANSIT  →  OUT_FOR_DELIVERY  →  DELIVERED",
     Inches(0.75), Inches(4.3), Inches(11.8), D(0.55), LIGHT, DARK, size=13, shape=4)
rect(s, "DELIVERED ve CANCELLED terminal durumdur — tekrar değiştirilemez, API 400 döner",
     Inches(0.75), Inches(5.1), Inches(11.8), D(0.55), ORANGE, WHITE, size=13, shape=4)
tb(s, "Bu kural teslim edilmiş bir kargonun yeniden yola çıkmasını engeller "
      "(app/models.py → TERMINAL_STATUSES, testlerle doğrulanmış)",
    Inches(0.75), Inches(5.85), Inches(11.8), D(0.4), size=12, color=MUTED)
notes(s, "Terminal durum kuralını vurgula. Hoca 'neden önemli' diye sorarsa: "
         "gerçek hayatta teslim edilmiş kargo iptal edilemez. Kural models.py'de, "
         "test_06 ve test_06b ile doğrulandı.")

# ---------------------------------------------------------------- 5 Producer
s = new()
title(s, "Kafka Producer: 5 Olay Tipi")
table(s, [
    ["Event", "Ne zaman gönderilir"],
    ["cargo.created", "Kargo oluşturuldu (POST /cargo)"],
    ["cargo.status_changed", "Durum değişti (PUT /cargo/<id>/status)"],
    ["cargo.delivered", "Durum DELIVERED yapıldı"],
    ["cargo.cancelled", "Durum CANCELLED yapıldı"],
    ["cargo.deleted", "Kargo silindi (DELETE /cargo/<id>)"],
], Inches(0.75), Inches(1.45), Inches(11.8), col_w=[3.4, 6.0])
rect(s, "cargo_id  mesaj anahtarı (key) olarak kullanılır", Inches(0.75),
     Inches(4.05), Inches(11.8), D(0.5), ACCENT, WHITE, size=13, shape=4)
tb(s, "→ Aynı kargonun event'leri aynı partition'a düşer, sıralama korunur. "
      "Key verilmezse round-robin dağıtılır ve sıralama bozulur.",
    Inches(0.75), Inches(4.75), Inches(11.8), D(0.6), size=13, color=MUTED)
notes(s, "Key olarak cargo_id vermek önemli bir karar. Kafka key'e göre partition "
         "atar; key yoksa round-robin dağıtır. Aynı kargonun iki olayının farklı "
         "partition'a gitmesi sıralama garantisini kırar.")

# ---------------------------------------------------------------- 6 Tasarım
s = new()
title(s, "Tasarım Kararı: Kafka Yokken API Çökmez")
bullets(s, [
    "Producer tembel (lazy) bağlanır — uygulama açılışında değil, ilk gönderimde",
    "Broker kapalıysa API isteği yine 201/200 döner",
    "Event kaybolur ve terminale uyarı loglanır",
    "Retry: 3 deneme, 3 saniye istek zaman aşımı",
], Inches(0.75), Inches(1.45), Inches(11.8), Inches(2.5), size=17, gap=12)
rect(s, "Sonuç:  veri yazma sorumluluğu ile event yayınlama sorumluluğu ayrışır",
     Inches(0.75), Inches(4.2), Inches(11.8), D(0.55), ACCENT, WHITE, size=14, shape=4)
rect(s, "Pratik fayda:  API ve testler Kafka kurulmadan doğrulanabilir "
       "(testler KAFKA_ENABLED=0 ile koşar)", Inches(0.75), Inches(5.0),
     Inches(11.8), D(0.55), LIGHT, DARK, size=14, shape=4)
notes(s, "En çok savunduğum tasarım kararı bu. Testler KAFKA_ENABLED=0 ile Kafka "
         "olmadan koşar; API açılışı Kafka'ya bağlı değildir. Production'da kalıcı "
         "kuyruk (dead-letter topic) eklenebilir — ileriye yönelik öneri.")

# ---------------------------------------------------------------- 7 Metrikler
s = new()
title(s, "Prometheus Metrikleri")
table(s, [
    ["Metrik", "Tip", "Ne ölçer"],
    ["cargo_created_total", "Counter", "Oluşturulan kargo sayısı"],
    ["cargo_delivered_total", "Counter", "Teslim edilen kargo"],
    ["cargo_cancelled_total", "Counter", "İptal edilen kargo"],
    ["cargo_status_changed_total", "Counter", "Durum değişikliği"],
    ["api_request_total", "Counter", "İstek sayısı (3 etiket)"],
    ["api_request_duration_seconds", "Histogram", "İstek süresi"],
], Inches(0.75), Inches(1.45), Inches(11.8), col_w=[4.4, 1.9, 3.9])
rect(s, "Histogram otomatik _sum / _count / _max üretir → ortalama süre sorgusu mümkün",
     Inches(0.75), Inches(4.35), Inches(11.8), D(0.5), LIGHT, DARK, size=13, shape=4)
tb(s, "Counter yalnızca artar (kargo sayısı monoton artar), Gauge ini çekilir.",
    Inches(0.75), Inches(5.0), Inches(11.8), D(0.4), size=12, color=MUTED)
notes(s, "Counter ile Gauge farkını bilmesi gerekebilir: Counter sadece artar, "
         "Gauge ini çekilir. Kargo sayısı monoton artar → Counter doğru seçim. "
         "Histogram'ın _sum/_count/_max üretmesi ortalama süre hesabını mümkün kılar.")

# ---------------------------------------------------------------- 8 Grafana
s = new()
title(s, "Grafana Dashboard")
table(s, [
    ["Panel grubu", "İçerik"],
    ["6 istatistik paneli", "Toplam, Teslim, İptal, Aktif Kargo, Event, API İsteği"],
    ["4 zaman serisi grafiği", "Dakikadaki işlem, API süresi, event türleri, durum dağılımı"],
], Inches(0.75), Inches(1.45), Inches(11.8), col_w=[3.6, 6.6])
rect(s, "Dashboard JSON dosyasından provisioning ile yüklenir", Inches(0.75),
     Inches(2.75), Inches(11.8), D(0.5), ACCENT, WHITE, size=13, shape=4)
bullets(s, [
    "Container yeniden başlasa da korunur, elle yapılandırma gerekmez",
    "Veri kaynağı da dosyadan tanımlanır (datasources/prometheus.yml)",
    "Dashboard 5 saniyede bir yenilenir — Prometheus'un scrape aralığıyla aynı",
    "Sunumdaki ekran görüntüsü: docs/grafana-dashboard.png (10 panel, canlı veri)",
], Inches(0.75), Inches(3.5), Inches(11.8), Inches(2.6), size=15, gap=10)
notes(s, "Provisioning'in avantajını açıkla: ortamlar arası tekrarlanabilirlik, "
         "sürüm kontrolü, container yeniden başlasa da korunması.")

# ---------------------------------------------------------------- 9 Testler
s = new()
title(s, "Test Sonuçları")
bullets(s, [
    "13 PyTest testi yazıldı (doküman isteği: en az 8)",
    "Her test kendi geçici SQLite'ını kullanır (tmp_path) → testler izole ve sırasız",
    "Testler KAFKA_ENABLED=0 ile Kafka bağımsız koşar",
    "Tam akış senaryosu: 20 kargo → 10 IN_TRANSIT → 5 DELIVERED → 2 CANCELLED",
], Inches(0.75), Inches(1.4), Inches(11.8), Inches(2.2), size=15, gap=9)
table(s, [
    ["Kontrol", "Sonuç"],
    ["PyTest", "13 passed in 1.75s"],
    ["API metrikleri", "oluşturma 20 · teslim 5 · iptal 2 · durum değişikliği 17"],
    ["Consumer metrikleri", "created 20 · status_changed 17 · delivered 5 · cancelled 2"],
    ["Prometheus hedefleri", "cargo-api up, cargo-consumer up"],
], Inches(0.75), Inches(3.75), Inches(11.8), col_w=[3.2, 6.8], size=11)
rect(s, "API sayaçları ile consumer sayaçları BİREBİR AYNI  →  event'ler kayıpsız iletildi",
     Inches(0.75), Inches(5.85), Inches(11.8), D(0.6), ORANGE, WHITE, size=14, shape=4)
notes(s, "EN ÖNEMLİ NOKTA BURASI: API'nin ürettiği sayaçlar ile consumer'ın "
         "saydığı event sayısı birebir aynı (20/17/5/2). Producer ile consumer "
         "farklı süreçlerde, farklı sayaçlarla çalışıyor; eşleşmeleri event'lerin "
         "kayıpsız iletildiğinin somut kanıtı. Bunu vurgula.")

# ---------------------------------------------------------------- 10 Docker
s = new()
title(s, "Docker Compose: Tek Komutla Beş Servis")
table(s, [
    ["Servis", "İmaj", "Port"],
    ["kafka", "apache/kafka:3.7.1", "9092"],
    ["flask", "Dockerfile (build)", "5000"],
    ["consumer", "Dockerfile (build)", "9091"],
    ["prometheus", "prom/prometheus:v2.54.1", "9090"],
    ["grafana", "grafana/grafana:11.2.0", "3000"],
], Inches(0.75), Inches(1.45), Inches(11.8), col_w=[2.4, 5.4, 1.4])
bullets(s, [
    "Kafka KRaft modunda çalışır — ZooKeeper gerekmez (CLUSTER_ID ile küme kimliği)",
    "Healthcheck: servisler Kafka hazır olmadan başlamaz (depends_on: service_healthy)",
    "Volume: SQLite kalıcı; docker compose down -v ile temizlenir",
    "Tek Dockerfile iki servis tarafından paylaşılır (flask + consumer)",
], Inches(0.75), Inches(4.05), Inches(11.8), Inches(2.4), size=14, gap=8)
notes(s, "Dockerfile tek, iki servis onu paylaşıyor. Kafka için bitnami yerine resmi "
         "apache imajı kullanıldı (bitnami etiketlerini taşıdı). Healthcheck sayesinde "
         "consumer, Kafka hazır olmadan event dinlemeye başlamıyor.")

# ---------------------------------------------------------------- 11 Demo
s = new(ORANGE)
tb(s, "CANLI DEMO", Inches(0.9), Inches(2.7), Inches(11.5), Inches(0.9),
   size=52, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
tb(s, "Kargo oluştur  →  Kafka event  →  Consumer  →  Prometheus  →  Grafana",
   Inches(0.9), Inches(3.8), Inches(11.5), Inches(0.5), size=20, color=WHITE,
   align=PP_ALIGN.CENTER)
tb(s, "bash scripts/demo.sh", Inches(0.9), Inches(4.7), Inches(11.5), Inches(0.5),
   size=17, bold=True, color=DARK, align=PP_ALIGN.CENTER, font="Consolas")
notes(s, "Slayt 11'de geçiş yap, slayt 12'ye hemen geçme. Burada canlı demoyu yap, "
         "sonra dön. Sıra: 1) curl POST /cargo 2) consumer logları 3) /metrics "
         "4) Prometheus targets 5) Grafana dashboard.")

# ---------------------------------------------------------------- 12 Sonuç
s = new()
title(s, "Sonuç ve İleriye Yönelik Öneriler")
rect(s, "5 servis tek komutla çalışıyor, uçtan uca zincir doğrulandı", Inches(0.75),
     Inches(1.4), Inches(11.8), D(0.5), ACCENT, WHITE, size=14, shape=4)
tb(s, "Öğrenilen kavramlar", Inches(0.75), Inches(2.1), Inches(11.8), D(0.35),
   size=15, bold=True, color=ACCENT)
bullets(s, [
    "Olay tabanlı mimari ve gevşek bağımlılık",
    "Mesaj kuyruğu ayrışması — API yavaşlasa bile event kaybolmaz",
    "Mesaj anahtarı (key) kullanımı ve sıralama garantisi",
    "Metrik tasarımı: Counter/Histogram seçimi ve etiketleme",
    "Test izolasyonu: tmp_path ile her testin kendi veritabanı",
    "Docker orkestrasyonu: healthcheck, volume, provisioning",
], Inches(0.75), Inches(2.5), Inches(11.8), Inches(2.4), size=14, gap=6)
tb(s, "İleriye yönelik", Inches(0.75), Inches(4.85), Inches(11.8), D(0.35),
   size=15, bold=True, color=ORANGE)
bullets(s, [
    "PostgreSQL'e geçiş ve confluent-kafka ile daha yüksek performans",
    "Prometheus alert kuralları ve Alertmanager ile otomatik bildirim",
    "Web arayüzü ve gerçek taşıyıcı entegrasyonu",
], Inches(0.75), Inches(5.25), Inches(11.8), Inches(1.4), size=14, gap=6)
notes(s, "Kapanış: Nihai hedef kod yazma → test etme → olay üretme → olay tüketme "
         "→ ölçme → görselleştirme → container'da çalıştırma zinciriydi ve hepsi "
         "tamamlandı. Soru varsa mimari, terminal durum kuralı, test izolasyonu veya "
         "metrik tasarımı üzerinden git.")

prs.save(str(OUT))
print(f"PPTX yazildi: {OUT} ({len(prs.slides.__iter__.__self__._sldIdLst)} slayt)")
