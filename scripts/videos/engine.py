#!/usr/bin/env python3
"""Motor genérico de vídeo-aula: lê um roteiro (specs/<id>.py) e gera MP4 + MP3 + roteiro.md.

Uso: python3 engine.py specs/m01d2.py [saida_dir]
"""
import os, sys, re, math, wave, subprocess, importlib.util
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1920, 1080
COL = dict(bg="#0f172a", fg="#e2e8f0", muted="#94a3b8", acc="#38bdf8", green="#4ade80", red="#f87171",
           amber="#fbbf24", violet="#a78bfa", card="#1e293b", line="#334155")
TINT = dict(red="#2a1215", green="#0f2a1a", amber="#2a2110", acc="#0c2233", violet="#1e1633", muted="#1e293b")
F = "/usr/share/fonts/opentype/inter/Inter-%s.otf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
_fc = {}
def font(sz, w="Regular"):
    k = (sz, w)
    if k not in _fc: _fc[k] = ImageFont.truetype(MONO if w == "mono" else F % w, sz)
    return _fc[k]
def c(name): return COL.get(name, name)

VOICE_ID = os.environ.get("VOICE", "pm_alex"); SPEED = float(os.environ.get("SPEED", "1.0"))
PAUSE_SECS = 6
WARN = []

# ---------------- pronúncia ----------------
PT = [(r"\bSLOs?\b", "ésse éle ó"), (r"\bSLAs?\b", "ésse éle á"), (r"\bSLIs?\b", "ésse éle í"), (r"\bAPIs\b", "a pê ís"),
      (r"\bAPI\b", "a pê í"), (r"\bEC2\b", "é cê dois"), (r"\bNTP\b", "ene tê pê"), (r"\bHTTP\b", "agá tê tê pê"),
      (r"\bDNS\b", "dê ene ésse"), (r"\bSQL\b", "ésse quê éle"), (r"\bPIX\b", "pix"), (r"\bBC\b", "bê cê"),
      (r"\bSPI\b", "ésse pê í"), (r"\bDICT\b", "díqui"), (r"\bLGPD\b", "éle gê pê dê"), (r"\bPCI\b", "pê cê í"),
      (r"\bKYC\b", "cá ípsilon cê"), (r"\bAML\b", "á ême éle"), (r"\bTLS\b", "tê éle ésse"), (r"\bmTLS\b", "ême tê éle ésse"),
      (r"\bJWT\b", "jóta dáblio tê"), (r"\bHSM\b", "agá ésse ême"), (r"\bKMS\b", "cá ême ésse"), (r"\bID\b", "ai dí"),
      (r"\bIDs\b", "ai dís"), (r"\bCPU\b", "cê pê u"), (r"\bRPO\b", "érre pê ó"), (r"\bRTO\b", "érre tê ó"),
      (r"\bMVCC\b", "ême vê cê cê"), (r"\bACID\b", "ácid"), (r"\bCAP\b", "cáp"), (r"\bISO\b", "íso"), (r"\bDLQ\b", "dê éle quê"),
      (r"\bSRE\b", "ésse érre é"), (r"\bOTel\b", "ôu tél"), (r"\bp99\.9\b", "pê noventa e nove ponto nove"),
      (r"\bp99\b", "pê noventa e nove"), (r"\bp50\b", "pê cinquenta"), (r"\bp95\b", "pê noventa e cinco"),
      (r"\bSWIFT\b", "suíft"), (r"\bFX\b", "éfe xis"), (r"\bUUID\b", "u u ai dí"), (r"\bUTC\b", "u tê cê")]
EN = ["Challenges with distributed systems", "Builders' Library", "load balancer", "leap second", "client token",
      "causal reverse", "Cockroach Labs", "Date.now", "hrtime", "created_at", "nextval", "trade-off", "hard real-time",
      "timestamps", "timestamp", "timeouts", "timeout", "retries", "retry", "backoff", "jitter", "Cloudflare", "UNKNOWN",
      "FAILED", "COMPLETED", "PENDING", "heartbeats", "heartbeat", "ledger", "ledgers", "slewing", "stepping", "sequence",
      "worker", "workers", "job", "jobs", "threads", "thread", "Postgres", "PostgreSQL", "Stripe", "flashcards", "stack",
      "commit", "commits", "rollback", "Go", "Amazon", "AWS", "Google", "Anki", "Cassandra", "Kafka", "RabbitMQ", "broker",
      "brokers", "consumer", "consumers", "producer", "producers", "offset", "offsets", "partition", "partitions",
      "outbox", "inbox", "saga", "sagas", "lock", "locks", "deadlock", "deadlocks", "snapshot", "isolation", "Serializable",
      "Repeatable Read", "Read Committed", "write skew", "lost update", "dirty read", "phantom", "SELECT FOR UPDATE",
      "FOR UPDATE", "SKIP LOCKED", "upsert", "idempotency key", "idempotency keys", "key", "keys", "hash", "request",
      "requests", "response", "payload", "endpoint", "webhook", "webhooks", "replica", "replicas", "replication lag",
      "leader", "follower", "followers", "quorum", "Raft", "Paxos", "failover", "split brain", "circuit breaker",
      "bulkhead", "rate limit", "rate limiting", "load shedding", "throttling", "tracing", "trace", "traces", "span",
      "spans", "logs", "log", "metrics", "dashboard", "dashboards", "alert", "alerts", "on-call", "runbook", "runbooks",
      "postmortem", "postmortems", "error budget", "toil", "OpenTelemetry", "Prometheus", "Grafana", "Datadog", "Jaeger",
      "Honeycomb", "Shopify", "Uber", "Netflix", "Square", "Modern Treasury", "Brex", "Nubank", "Adyen", "Wise", "Visa",
      "Mastercard", "chargeback", "chargebacks", "settlement", "clearing", "acquirer", "issuer", "gateway", "tokenization",
      "token", "tokens", "secrets", "vault", "Vault", "fraud", "scoring", "feature store", "rules engine", "allowlist",
      "denylist", "chaos engineering", "canary", "feature flag", "feature flags", "rollout", "deploy", "blue-green",
      "event sourcing", "CQRS", "exactly-once", "at-least-once", "at-most-once", "dead letter queue", "schema registry",
      "Avro", "Protobuf", "JSON", "TigerBeetle", "double-entry", "journal", "posting", "postings", "balance", "balances",
      "reconciliation", "end-to-end", "Kubernetes", "Redis", "DynamoDB", "Spanner", "CockroachDB", "Jepsen", "Kleppmann",
      "Designing Data-Intensive Applications", "Martin Fowler", "Pat Helland", "Brandur", "Debezium", "CDC", "change data capture",
      "fan-out", "backpressure", "ordering", "consumer group", "consumer groups", "retention", "compaction", "orchestration",
      "choreography", "compensation", "two-phase commit", "2PC", "HMAC", "OAuth", "OWASP", "threat model", "STRIDE",
      "least privilege", "audit log", "nonce", "replay", "SLO", "golden signals", "latency", "throughput", "cardinality",
      "sampling", "health check", "readiness", "liveness", "nostro", "vostro", "correspondent banking", "stablecoin",
      "big tech", "fintech", "fintechs", "startup", "backend", "frontend", "cache", "batch", "streaming", "queue", "queues",
      "topic", "topics", "lag", "hot path", "SLA", "mock", "test", "tests", "property-based testing", "property-based",
      "fuzzing", "pull request", "code review", "lab", "DSA"]
EN_SAY = {"Date.now": "date now", "hrtime": "H R time", "created_at": "created at", "nextval": "next val", "AWS": "A W S",
          "Builders' Library": "Builders Library", "2PC": "two P C", "CQRS": "C Q R S", "CDC": "C D C", "HMAC": "H mac",
          "OWASP": "O wasp", "DSA": "D S A", "JSON": "jason", "SLA": "S L A", "SLO": "S L O"}
EN_TERMS = []

def speak(t):
    for a, b in PT: t = re.sub(a, b, t)
    terms = sorted(set(EN + EN_TERMS), key=len, reverse=True)
    pat = r"(?<![\w{])(" + "|".join(re.escape(e) for e in terms) + r")(?![\w}])"
    return re.sub(pat, lambda m: "{" + EN_SAY.get(m.group(1), m.group(1)) + "}", t)

_K = None
def tts(text, path):
    global _K
    if os.path.exists(path): return
    import numpy as np, soundfile as sf
    from kokoro_onnx import Kokoro
    if _K is None: _K = Kokoro(HERE + "/kokoro-v1.0.onnx", HERE + "/voices-v1.0.bin")
    marked = speak(text)
    sents = [x for x in re.split(r"(?<=[.?!:])\s+", marked) if x.strip()]
    out = []; sr = 24000
    for snt in sents:
        ph = []
        for i, part in enumerate(re.split(r"\{([^}]*)\}", snt)):
            if part.strip(): ph.append(_K.tokenizer.phonemize(part, lang="en-us" if i % 2 else "pt-br"))
        p = " ".join(ph).strip()
        if not p: continue
        # o modelo aceita no máximo ~510 tokens; quebra frases longas nas vírgulas
        chunks = [p] if len(p) < 480 else re.split(r"(?<=,)\s+", p)
        for ch in chunks:
            a, sr = _K.create(ch, voice=VOICE_ID, speed=SPEED, is_phonemes=True)
            out.append(a)
        out.append(np.zeros(int(sr * 0.32), dtype=np.float32))
    sf.write(path, np.concatenate(out), sr)

def dur(path):
    with wave.open(path) as w: return w.getnframes() / w.getframerate()

# ---------------- desenho ----------------
def wrap(d, t, f, maxw):
    out = []
    for para in t.split("\n"):
        cur = ""
        for word in para.split():
            tst = (cur + " " + word).strip()
            if d.textlength(tst, font=f) > maxw and cur: out.append(cur); cur = word
            else: cur = tst
        out.append(cur)
    return "\n".join(out)

class Canvas:
    def __init__(s, meta, section, idx, total):
        s.im = Image.new("RGB", (W, H), COL["bg"]); s.d = ImageDraw.Draw(s.im); s.meta = meta
        s.d.text((100, 60), section.upper(), font=font(26, "SemiBold"), fill=COL["acc"])
        s.d.text((W - 100, 60), meta["label"], font=font(24), fill=COL["muted"], anchor="ra")
        s.d.rectangle((0, H - 10, W, H), fill=COL["line"])
        s.d.rectangle((0, H - 10, int(W * idx / total), H), fill=COL["acc"])
    def fit(s, t, maxw, maxh, sz, w="Regular", minsz=20):
        while True:
            f = font(sz, w); tw = wrap(s.d, t, f, maxw)
            bb = s.d.multiline_textbbox((0, 0), tw, font=f, spacing=int(sz * 0.3))
            if bb[3] <= maxh or sz <= minsz:
                if bb[3] > maxh: WARN.append(f"texto não coube: {t[:60]}")
                return f, tw, bb[3], sz
            sz -= 2
    def text(s, x, y, t, sz=36, col="fg", w="Regular", maxw=1720, maxh=900, anchor="la", align="left"):
        f, tw, h, sz2 = s.fit(t, maxw, maxh, sz, w)
        s.d.multiline_text((x, y), tw, font=f, fill=c(col), anchor=anchor, spacing=int(sz2 * 0.3), align=align)
        return h
    def box(s, x, y, w, h, col="acc", fill=None, width=4):
        s.d.rounded_rectangle((x, y, x + w, y + h), radius=18, fill=fill or COL["card"], outline=c(col), width=width)
    def boxtext(s, x, y, w, h, head, body=None, col="acc", hsz=34, bsz=26, fill=None, center=True):
        s.box(x, y, w, h, col, fill)
        pad = 22
        if body:
            fh, th, hh, _ = s.fit(head, w - 2 * pad, h * 0.45, hsz, "Bold")
            fb, tb, bh, bsz2 = s.fit(body, w - 2 * pad, h - hh - 3 * pad, bsz)
            if center:
                tot = hh + 14 + bh; y0 = y + (h - tot) / 2
                s.d.multiline_text((x + w / 2, y0), th, font=fh, fill=c(col), anchor="ma", align="center", spacing=6)
                s.d.multiline_text((x + w / 2, y0 + hh + 14), tb, font=fb, fill=COL["fg"], anchor="ma", align="center", spacing=int(bsz2 * 0.3))
            else:
                s.d.multiline_text((x + pad, y + pad), th, font=fh, fill=c(col), spacing=6)
                s.d.multiline_text((x + pad, y + pad + hh + 16), tb, font=fb, fill=COL["fg"], spacing=int(bsz2 * 0.3))
        else:
            fh, th, hh, _ = s.fit(head, w - 2 * pad, h - 2 * pad, hsz, "SemiBold")
            s.d.multiline_text((x + w / 2, y + h / 2), th, font=fh, fill=COL["fg"], anchor="mm", align="center", spacing=6)
    def arrow(s, x1, y1, x2, y2, col="muted", w=5):
        s.d.line((x1, y1, x2, y2), fill=c(col), width=w)
        a = math.atan2(y2 - y1, x2 - x1); L = 20
        s.d.polygon([(x2, y2), (x2 - L * math.cos(a - 0.45), y2 - L * math.sin(a - 0.45)),
                     (x2 - L * math.cos(a + 0.45), y2 - L * math.sin(a + 0.45))], fill=c(col))
    def heading(s, t):
        s.text(100, 115, t, sz=60, w="Bold", maxh=80)
    def callout(s, co, y=None):
        head, sub, col = co[0], (co[1] if len(co) > 1 else None), (co[2] if len(co) > 2 else "amber")
        h = 190 if sub else 140; y = y or (H - 60 - h)
        s.box(100, y, 1720, h, col, TINT.get(col, COL["card"]))
        if sub:
            s.text(W / 2, y + 30, head, sz=44, w="Bold", maxw=1640, maxh=60, anchor="ma", align="center")
            s.text(W / 2, y + 105, sub, sz=30, col="muted", maxw=1640, maxh=70, anchor="ma", align="center")
        else:
            s.text(W / 2, y + h / 2, head, sz=44, w="Bold", maxw=1640, maxh=110, anchor="mm", align="center")
    def bullets(s, items, y, k, bottom, numbered=False, sz=38):
        n = len(items); avail = bottom - y
        gap = min(130, avail / max(n, 1))
        for i, it in enumerate(items[:k]):
            t, col = (it, "acc") if isinstance(it, str) else it
            yy = y + i * gap
            if numbered:
                s.d.ellipse((100, yy, 150, yy + 50), fill=c(col)); s.d.text((125, yy + 25), str(i + 1), font=font(28, "Bold"), fill=COL["bg"], anchor="mm")
            else:
                s.d.ellipse((104, yy + 16, 122, yy + 34), fill=c(col))
            s.text(175 if numbered else 150, yy + (4 if numbered else 0), t, sz=sz, maxw=1640, maxh=gap - 10)
    def code(s, lines, hl, y, maxh):
        sz = 30
        while sz > 18:
            lh = int(sz * 1.5); h = lh * len(lines) + 50
            wmax = max(s.d.textlength(l, font=font(sz, "mono")) for l in lines)
            if h <= maxh and wmax <= 1660: break
            sz -= 2
        s.d.rounded_rectangle((100, y, 1820, y + h), radius=14, fill="#020617", outline=COL["line"], width=2)
        for i, ln in enumerate(lines):
            s.d.text((130, y + 25 + i * lh), ln, font=font(sz, "mono"), fill=COL["amber"] if i in (hl or []) else "#cbd5e1")
        return h

# ---------------- layouts ----------------
# Cada cena tem "elements": o passo k mostra os k primeiros elementos.
def n_elements(sc):
    t = sc["type"]; co = 1 if sc.get("callout") else 0
    if t == "title": return 1
    if t in ("bullets", "steps"): return len(sc["items"]) + co
    if t == "flow": return len(sc["nodes"]) + len(sc.get("notes", [])) + co
    if t == "cards": return len(sc["cards"]) + co
    if t == "compare": return 2 + co
    if t == "code": return 1 + len(sc.get("notes", [])) + co
    if t == "table": return len(sc["rows"]) + co
    if t == "statement": return 1 + (1 if sc.get("sub") else 0) + co
    if t == "recap": return len(sc["qa"])
    raise ValueError(t)

def draw(cv, sc, k, meta):
    t = sc["type"]; co = sc.get("callout")
    bottom = H - 60 - (210 if co and len(co) > 1 else 160) - 20 if co else H - 80
    if t != "title" and sc.get("title"): cv.heading(sc["title"])
    top = 230
    if t == "title":
        cv.text(W / 2, 420, meta["title"], sz=88, w="Bold", maxw=1700, maxh=220, anchor="md", align="center")
        cv.text(W / 2, 460, meta["subtitle"], sz=36, col="muted", maxw=1700, anchor="ma", align="center")
        if k >= 1:
            qs = sc["questions"]; n = len(qs); bw = (1720 - (n - 1) * 40) / n
            for i, q in enumerate(qs): cv.boxtext(100 + i * (bw + 40), 600, bw, 220, q, hsz=32)
        return
    if t in ("bullets", "steps"):
        n = len(sc["items"]); cv.bullets(sc["items"], top + 20, min(k, n), bottom, numbered=(t == "steps"), sz=sc.get("size", 38))
        if co and k > n: cv.callout(co)
    elif t == "flow":
        nodes = sc["nodes"]; n = len(nodes); notes = sc.get("notes", [])
        gap = 60; bw = (1720 - (n - 1) * gap) / n; bh = sc.get("node_h", 170); y = top + 40
        for i, nd in enumerate(nodes[:k]):
            lab, col = nd[0], nd[1] if len(nd) > 1 else "acc"; sub = nd[2] if len(nd) > 2 else None
            x = 100 + i * (bw + gap)
            cv.boxtext(x, y, bw, bh, lab, sub, col=col, hsz=32 if not sub else 30, bsz=24)
            if i > 0: cv.arrow(x - gap + 6, y + bh / 2, x - 8, y + bh / 2, col=sc.get("arrow", "muted"))
        if sc.get("edges"):
            for i, e in enumerate(sc["edges"][:max(0, min(k, n) - 1)]):
                if e: cv.text(100 + (i + 1) * (bw + gap) - gap / 2, y + bh + 14, e, sz=24, col="muted", maxw=260, anchor="ma", align="center")
        kn = max(0, k - n)
        if notes: cv.bullets(notes, y + bh + 90, min(kn, len(notes)), bottom, sz=sc.get("size", 34))
        if co and kn > len(notes): cv.callout(co)
    elif t == "cards":
        cards = sc["cards"]; n = len(cards)
        rows = 2 if n > 3 else 1; per = math.ceil(n / rows); gap = 36
        bw = (1720 - (per - 1) * gap) / per; bh = ((bottom - top - 20) - (rows - 1) * gap) / rows
        bh = min(bh, sc.get("card_h", 420))
        for i, cd in enumerate(cards[:k]):
            r, cidx = divmod(i, per)
            cv.boxtext(100 + cidx * (bw + gap), top + 20 + r * (bh + gap), bw, bh, cd[0], cd[1], col=cd[2] if len(cd) > 2 else "acc",
                       hsz=36, bsz=sc.get("size", 32), center=False)
        if co and k > n: cv.callout(co)
    elif t == "compare":
        bh = bottom - top - 20
        for i, side in enumerate([sc["left"], sc["right"]][:k]):
            head, items, col = side
            x = 100 + i * 880; cv.box(x, top + 20, 840, bh, col)
            cv.text(x + 40, top + 50, head, sz=40, w="Bold", col=col, maxw=760, maxh=60)
            yy = top + 130; g = (bh - 140) / max(len(items), 1); g = min(g, 120)
            for it in items:
                cv.d.ellipse((x + 40, yy + 13, x + 54, yy + 27), fill=c(col))
                cv.text(x + 72, yy, it, sz=sc.get("size", 32), maxw=730, maxh=g - 8); yy += g
        if co and k > 2: cv.callout(co)
    elif t == "code":
        notes = sc.get("notes", []); h = 0
        if k >= 1: h = cv.code(sc["code"], sc.get("hl"), top + 10, sc.get("code_h", 520))
        if notes and k > 1: cv.bullets(notes, top + 10 + h + 40, min(k - 1, len(notes)), bottom, sz=32)
        if co and k > 1 + len(notes): cv.callout(co)
    elif t == "table":
        cols = sc["header"]; rows = sc["rows"]; nc = len(cols); widths = sc.get("widths") or [1720 / nc] * nc
        rh = min(95, (bottom - top - 100) / (len(rows) + 1)); y = top + 20; x = 100
        for j, hd in enumerate(cols):
            cv.text(x + 20, y + 10, hd, sz=28, w="Bold", col="muted", maxw=widths[j] - 30, maxh=rh); x += widths[j]
        for i, row in enumerate(rows[:k]):
            y = top + 20 + (i + 1) * rh; x = 100
            cv.d.rounded_rectangle((100, y, 1820, y + rh - 10), radius=10, fill=COL["card"])
            for j, cell in enumerate(row):
                cv.text(x + 20, y + (rh - 10) / 2, cell, sz=sc.get("size", 30), w="SemiBold" if j == 0 else "Regular",
                        col="fg", maxw=widths[j] - 40, maxh=rh - 14, anchor="lm"); x += widths[j]
        if co and k > len(rows): cv.callout(co)
    elif t == "statement":
        col = sc.get("color", "red")
        if k >= 1:
            cv.box(160, 330, 1600, 280, col, TINT.get(col))
            cv.text(W / 2, 470, sc["text"], sz=60, w="Bold", maxw=1500, maxh=240, anchor="mm", align="center")
        if sc.get("sub") and k >= 2: cv.text(W / 2, 680, sc["sub"], sz=36, col="muted", maxw=1500, maxh=150, anchor="ma", align="center")
        if co and k > 1 + (1 if sc.get("sub") else 0): cv.callout(co)
    elif t == "recap":
        qa = sc["qa"]; g = (H - 100 - top) / len(qa)
        for i, (q, a) in enumerate(qa):
            y = top + 10 + i * g
            cv.text(100, y, f"{i+1}. {q}", sz=38, w="Bold", maxh=g * 0.45)
            if k >= i + 1: cv.text(140, y + g * 0.42, a, sz=31, col="green", maxw=1650, maxh=g * 0.5)

def render(spec_path, outdir):
    spec = importlib.util.spec_from_file_location("spec", spec_path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    meta = m.META; scenes = m.SCENES; EN_TERMS[:] = getattr(m, "EN_TERMS", []); EN_SAY.update(getattr(m, "EN_SAY", {}))
    build = f"{HERE}/build/{meta['id']}"; os.makedirs(build, exist_ok=True); os.makedirs(outdir, exist_ok=True)
    segs = []; total = len(scenes); script = [f"# Roteiro · {meta['label']}\n"]
    for si, sc in enumerate(scenes):
        ne = n_elements(sc); script.append(f"\n## {sc['section']}\n"); step = 0
        for bi, (b, text) in enumerate(sc["beats"]):
            base = f"{build}/s{si:02d}_{bi:02d}"
            cv = Canvas(meta, sc["section"], si + 1, total)
            if b == "P":
                draw(cv, sc, step, meta)
                ov = Image.new("RGBA", (W, H), (2, 6, 23, 228)); cv.im = Image.alpha_composite(cv.im.convert("RGBA"), ov).convert("RGB")
                cv.d = ImageDraw.Draw(cv.im)
                cv.d.text((W / 2, 300), "PAUSE E RESPONDA", font=font(40, "Bold"), fill=COL["amber"], anchor="mm")
                cv.text(W / 2, 400, re.sub(r"^Pergunta( um| dois| três)?: ", "", text), sz=54, w="SemiBold", maxw=1500, maxh=420, anchor="ma", align="center")
                wav = base + "_q.wav"; tts(text, wav); d = dur(wav) + PAUSE_SECS
                script.append(f"> **Pausa:** {text}\n")
            else:
                step = ne if b == "all" else b
                draw(cv, sc, step, meta)
                wav = base + ".wav"; tts(text, wav); d = dur(wav) + 0.6
                script.append(text + "\n")
            img = base + ".png"; cv.im.save(img); segs.append((img, wav, d))
    parts = []
    for i, (img, wav, d) in enumerate(segs):
        mp4 = f"{build}/part{i:03d}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "25", "-i", img, "-i", wav,
                        "-af", f"apad,atrim=0:{d:.2f},aresample=44100", "-t", f"{d:.2f}", "-c:v", "libx264", "-tune", "stillimage",
                        "-pix_fmt", "yuv420p", "-r", "25", "-c:a", "aac", "-b:a", "128k", "-ac", "1", mp4], check=True)
        parts.append(mp4)
    with open(f"{build}/list.txt", "w") as f:
        for p in parts: f.write(f"file '{p}'\n")
    name = meta["file"]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", f"{build}/list.txt", "-c", "copy",
                    "-movflags", "+faststart", f"{outdir}/{name}.mp4"], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{outdir}/{name}.mp4", "-vn", "-c:a", "libmp3lame", "-b:a", "96k",
                    f"{outdir}/{name}.mp3"], check=True)
    os.makedirs(f"{outdir}/roteiros", exist_ok=True); open(f"{outdir}/roteiros/{name}-roteiro.md", "w").write("\n".join(script))
    for p in parts: os.remove(p)
    print(f"{meta['id']}: {sum(d for _, _, d in segs)/60:.1f} min, {len(segs)} trechos", *(["AVISOS:"] + WARN if WARN else []))

def preview(spec_path, out_png):
    """Contact sheet de todos os quadros, sem gerar áudio (para revisar layout)."""
    spec = importlib.util.spec_from_file_location("spec", spec_path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    ims = []
    for si, sc in enumerate(m.SCENES):
        ne = n_elements(sc)
        steps = sorted(set(ne if b == "all" else b for b, _ in sc["beats"] if b != "P"))
        cv = Canvas(m.META, sc["section"], si + 1, len(m.SCENES)); draw(cv, sc, max(steps), m.META); ims.append(cv.im.resize((640, 360)))
    cols = 4; rows = math.ceil(len(ims) / cols); sheet = Image.new("RGB", (640 * cols, 360 * rows))
    for i, im in enumerate(ims): sheet.paste(im, ((i % cols) * 640, (i // cols) * 360))
    sheet.save(out_png); print("avisos:", WARN)

if __name__ == "__main__":
    if sys.argv[1] == "preview": preview(sys.argv[2], sys.argv[3])
    else: render(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "..", "videos"))
