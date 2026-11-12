#!/usr/bin/env python3
"""Gera o vídeo piloto: Módulo 1, dia 1 (Falhas, timeouts e tempo)."""
import os, subprocess, json, re, wave
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
OUT = os.path.dirname(os.path.abspath(__file__)) + "/build"
os.makedirs(OUT, exist_ok=True)
VOICE_ID = os.environ.get("VOICE", "pm_alex"); SPEED = float(os.environ.get("SPEED", "1.0"))

BG = "#0f172a"; FG = "#e2e8f0"; MUTED = "#94a3b8"; ACC = "#38bdf8"
GREEN = "#4ade80"; RED = "#f87171"; AMBER = "#fbbf24"; CARD = "#1e293b"; LINE = "#334155"
F = "/usr/share/fonts/opentype/inter/Inter-%s.otf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
def font(sz, w="Regular"): return ImageFont.truetype(F % w, sz)
def mono(sz): return ImageFont.truetype(MONO, sz)

# Pronúncia: a narração é em pt-BR; termos técnicos em inglês são falados com fonética inglesa
# (como um dev brasileiro fala), e siglas são soletradas em português.
PT = [
    (r"\bSLO\b", "ésse éle ó"), (r"\bSLA\b", "ésse éle á"), (r"\bSLI\b", "ésse éle í"),
    (r"\bAPI\b", "a pê í"), (r"\bp99\.9\b", "pê noventa e nove ponto nove"), (r"\bEC2\b", "é cê dois"),
    (r"\bNTP\b", "ene tê pê"), (r"\bHTTP\b", "agá tê tê pê"), (r"\bDNS\b", "dê ene ésse"), (r"\bseq\b", "séqui"),
]
EN = ["Challenges with distributed systems", "Builders' Library", "load balancer", "leap second", "client token",
      "causal reverse", "Cockroach Labs", "Date.now", "hrtime", "created_at", "nextval", "trade-off", "hard real-time",
      "timestamps", "timestamp", "timeouts", "timeout", "retries", "retry", "backoff", "jitter", "Cloudflare", "UNKNOWN", "FAILED", "COMPLETED",
      "PENDING", "heartbeats", "ledger", "slewing", "stepping", "sequence", "worker", "job", "threads", "Postgres",
      "Stripe", "flashcards", "stack", "commit", "Go", "Amazon", "AWS", "Google", "Anki", "Cassandra"]
EN_SAY = {"Date.now": "date now", "hrtime": "H R time", "created_at": "created at", "nextval": "next val",
          "AWS": "A W S", "Builders' Library": "Builders Library"}
def speak(t):
    for a, b in PT: t = re.sub(a, b, t)
    pat = r"\b(" + "|".join(re.escape(e) for e in sorted(EN, key=len, reverse=True)) + r")\b"
    return re.sub(pat, lambda m: "{" + EN_SAY.get(m.group(1), m.group(1)) + "}", t)

# ---------- desenho ----------
class Canvas:
    def __init__(s, section, idx, total):
        s.im = Image.new("RGB", (W, H), BG); s.d = ImageDraw.Draw(s.im)
        s.d.text((100, 60), section.upper(), font=font(26, "SemiBold"), fill=ACC)
        s.d.text((W - 100, 60), "M1 · Dia 1 · Falhas, timeouts e tempo", font=font(24), fill=MUTED, anchor="ra")
        s.d.rectangle((0, H - 10, W, H), fill=LINE)
        s.d.rectangle((0, H - 10, int(W * idx / total), H), fill=ACC)
    def title(s, t, y=120, sz=64):
        s.d.text((100, y), t, font=font(sz, "Bold"), fill=FG)
    def text(s, xy, t, sz=36, c=FG, w="Regular", anchor="la", maxw=None):
        f = font(sz, w)
        if maxw:
            lines, cur = [], ""
            for word in t.split():
                tst = (cur + " " + word).strip()
                if s.d.textlength(tst, font=f) > maxw and cur: lines.append(cur); cur = word
                else: cur = tst
            lines.append(cur); t = "\n".join(lines)
        s.d.multiline_text(xy, t, font=f, fill=c, anchor=anchor, spacing=int(sz * 0.35), align="center" if anchor == "mm" else "left")
    def box(s, x, y, w, h, label, c=ACC, sz=34, fill=CARD, tc=FG, sub=None):
        s.d.rounded_rectangle((x, y, x + w, y + h), radius=18, fill=fill, outline=c, width=4)
        cy = y + h / 2 - (18 if sub else 0)
        s.d.text((x + w / 2, cy), label, font=font(sz, "SemiBold"), fill=tc, anchor="mm")
        if sub: s.d.text((x + w / 2, cy + 44), sub, font=font(24), fill=MUTED, anchor="mm")
    def arrow(s, x1, y1, x2, y2, c=MUTED, w=5, label=None, lc=None):
        s.d.line((x1, y1, x2, y2), fill=c, width=w)
        import math
        a = math.atan2(y2 - y1, x2 - x1); L = 22
        p1 = (x2 - L * math.cos(a - 0.45), y2 - L * math.sin(a - 0.45))
        p2 = (x2 - L * math.cos(a + 0.45), y2 - L * math.sin(a + 0.45))
        s.d.polygon([(x2, y2), p1, p2], fill=c)
        if label: s.d.text(((x1 + x2) / 2, (y1 + y2) / 2 - 30), label, font=font(26), fill=lc or c, anchor="mm")
    def code(s, x, y, lines, sz=30, w=1720, hl=None):
        lh = int(sz * 1.5); h = lh * len(lines) + 50
        s.d.rounded_rectangle((x, y, x + w, y + h), radius=14, fill="#020617", outline=LINE, width=2)
        for i, ln in enumerate(lines):
            col = AMBER if hl and i in hl else "#cbd5e1"
            s.d.text((x + 30, y + 25 + i * lh), ln, font=mono(sz), fill=col)
    def bullets(s, x, y, items, sz=38, gap=78, maxw=1600):
        for i, (t, c) in enumerate(items):
            s.d.ellipse((x, y + i * gap + 14, x + 16, y + i * gap + 30), fill=c)
            s.text((x + 40, y + i * gap), t, sz=sz, maxw=maxw)

# Cada cena: (seção, função de desenho(c, passo), [(passo, narração), ...])
# Um passo "PAUSA" mostra a pergunta com contagem regressiva, sem narração.
SCENES = []
def scene(section, beats):
    def deco(fn): SCENES.append((section, fn, beats)); return fn
    return deco

# 0 abertura
@scene("Abertura", [
 (0, "Olá! Esta é a aula em vídeo do módulo um, dia um: falhas, timeouts e tempo. São uns doze minutos."),
 (1, "No final você vai conseguir responder três perguntas. O que um timeout realmente significa. Como fazer retry sem cobrar o cliente duas vezes. E por que você não pode ordenar eventos pelo relógio."),
 (1, "Em alguns momentos o vídeo vai parar e te fazer uma pergunta. Tente responder em voz alta antes da resposta aparecer. É esse esforço de lembrar que faz o conteúdo ficar."),
])
def s0(c, p):
    c.d.text((W / 2, 380), "Falhas, timeouts e tempo", font=font(96, "Bold"), fill=FG, anchor="mm")
    c.d.text((W / 2, 480), "Módulo 1 · Fundamentos de sistemas distribuídos · Dia 1", font=font(38), fill=MUTED, anchor="mm")
    if p >= 1:
        qs = ["O que um timeout realmente significa?", "Como fazer retry sem cobrar duas vezes?", "Por que não ordenar eventos pelo relógio?"]
        for i, q in enumerate(qs):
            c.box(260 + i * 480, 620, 440, 200, "", c=ACC)
            c.text((480 + i * 480, 720), q, sz=32, anchor="mm", maxw=380, w="SemiBold")
SCENES[-1] = (SCENES[-1][0], s0, SCENES[-1][2])

# 1 gancho
@scene("Por que importa", [
 (0, "Um sistema de pagamentos é distribuído desde a primeira linha. Sua API fala com o banco de dados. Um worker chama o banco parceiro. O parceiro chama o Pix."),
 (1, "Cada seta desse desenho é uma chamada de rede. E toda chamada de rede pode falhar de jeitos que uma função local não falha."),
 (2, "Os bugs mais caros em pagamentos vêm de uma confusão só: tratar não recebi resposta como se fosse não aconteceu. Guarde essa frase. A aula inteira gira em torno dela."),
])
def s1(c, p):
    c.title("Cada seta é uma chamada de rede")
    xs = [100, 540, 980, 1420]; names = ["Carteira", "API", "Banco parceiro", "Pix"]
    for i, (x, n) in enumerate(zip(xs, names)):
        c.box(x, 340, 380, 150, n, c=ACC if i < 2 else AMBER)
    for i in range(3):
        c.arrow(xs[i] + 385, 415, xs[i + 1] - 8, 415, c=RED if p >= 1 else MUTED)
    if p >= 1: c.d.text((W / 2, 540), "rede  ·  rede  ·  rede", font=font(30, "SemiBold"), fill=RED, anchor="mm")
    if p >= 2:
        c.box(310, 640, 1300, 200, "", c=RED, fill="#2a1215")
        c.d.text((W / 2, 715), "“Não recebi resposta”  ≠  “Não aconteceu”", font=font(56, "Bold"), fill=FG, anchor="mm")
        c.d.text((W / 2, 790), "a confusão por trás dos bugs mais caros em pagamentos", font=font(30), fill=MUTED, anchor="mm")

# 2 falha parcial
@scene("Falha parcial", [
 (0, "Em uma máquina só, ou o programa funciona, ou a máquina inteira caiu. As partes compartilham o destino."),
 (1, "Numa rede isso acaba. O servidor pode cair com o cliente rodando. A rede pode perder uma mensagem com as duas máquinas saudáveis. Os sistemas distribuídos falham parcialmente: algumas partes funcionam, outras não, e ninguém tem a visão completa."),
 (2, "Jacob Gabrielson, da AWS, classifica pagamentos como sistema de tempo real rígido: precisa responder rápido a requisições imprevisíveis. Sua carteira está nessa categoria."),
])
def s2(c, p):
    c.title("Sem destino compartilhado")
    c.box(100, 280, 800, 420, "", c=GREEN)
    c.text((140, 310), "Uma máquina", sz=40, w="Bold", c=GREEN)
    c.text((140, 390), "Funciona por inteiro, ou cai por inteiro. A falha é óbvia.", sz=34, maxw=720)
    if p >= 1:
        c.box(1020, 280, 800, 420, "", c=RED)
        c.text((1060, 310), "Pela rede", sz=40, w="Bold", c=RED)
        c.bullets(1060, 390, [("Servidor cai, cliente segue rodando", RED), ("Rede perde a mensagem, máquinas saudáveis", RED), ("Ninguém tem a visão completa", RED)], sz=32, gap=100, maxw=680)
    if p >= 2:
        c.text((W / 2, 820), "Pagamentos = hard real-time  (AWS Builders' Library)", sz=40, c=AMBER, w="SemiBold", anchor="mm")

# 3 oito passos
STEPS8 = ["Enviar requisição", "Rede entrega", "Validar requisição", "Atualizar estado do servidor",
          "Enviar resposta", "Rede entrega resposta", "Validar resposta", "Atualizar estado do cliente"]
@scene("Uma chamada, oito falhas", [
 (0, "Pegue uma única requisição com resposta. No caminho feliz, ela passa por oito passos. Enviar, a rede entregar, o servidor validar, o servidor fazer o trabalho. Depois a resposta faz o caminho de volta, também em quatro passos."),
 (1, "Cada passo pode falhar sozinho. Gabrielson chama isso de os oito modos de falha do apocalipse."),
 (2, "Agora leve isso para uma transferência. Se a falha foi nos passos um a três, nenhum dinheiro se moveu."),
 (3, "Se foi nos passos cinco a oito, o parceiro já debitou o cliente, e você nunca ficou sabendo. E aqui está o problema: do seu lado, os dois casos parecem idênticos. Nenhuma resposta utilizável."),
 ("PAUSA", "Pergunta: a resposta se perdeu no passo seis. O dinheiro do cliente saiu?"),
 (4, "Saiu, sim. O passo quatro, atualizar o estado do servidor, já aconteceu. Só a notícia que não chegou até você."),
])
def s3(c, p):
    c.title("Uma chamada, oito jeitos de falhar")
    for i, st in enumerate(STEPS8):
        row, col = divmod(i, 4)
        x = 100 + col * 435; y = 290 + row * 260
        color = ACC
        if p >= 2 and i < 3: color = GREEN
        if p >= 3 and i >= 4: color = RED
        if p >= 4 and i == 3: color = AMBER
        c.box(x, y, 400, 170, f"{i+1}", c=color, sz=48, sub=st)
        if p >= 1:
            c.d.line((x + 358, y + 12, x + 382, y + 36), fill=RED, width=5); c.d.line((x + 382, y + 12, x + 358, y + 36), fill=RED, width=5)
    c.text((100, 250), "cliente → servidor", sz=26, c=MUTED); c.text((100, 510), "servidor → cliente", sz=26, c=MUTED)
    if p >= 2: c.text((100, 830), "Falha em 1–3: nenhum dinheiro se moveu.", sz=36, c=GREEN, w="SemiBold")
    if p >= 3: c.text((100, 890), "Falha em 5–8: o parceiro JÁ debitou, e você não sabe.", sz=36, c=RED, w="SemiBold")
    if p >= 4: c.text((100, 950), "Passo 6 falhou → o passo 4 já aconteceu: o dinheiro saiu.", sz=36, c=AMBER, w="SemiBold")

# 4 três desfechos
@scene("Os três desfechos de um timeout", [
 (0, "Em uma máquina só, sacar dinheiro devolve sucesso ou saldo insuficiente. Pela rede, aparece um terceiro resultado: desconhecido. Nas palavras de Gabrielson: pode ou não ter acontecido, e o cliente precisa tratar isso corretamente."),
 (1, "Quando o timeout dispara, existem três situações. Um: a requisição nunca chegou. Nada aconteceu, tentar de novo é seguro."),
 (2, "Dois: chegou e foi processada, mas a resposta se perdeu. O efeito aconteceu. Tentar de novo sem proteção faz duas vezes."),
 (3, "Três: chegou e ainda está sendo processada, talvez presa numa fila. O efeito pode acontecer depois que você desistiu. E do seu lado, você não consegue distinguir nenhum dos três."),
 ("PAUSA", "Pergunta: por que marcar a transferência como falhou, logo no timeout, causa cobrança dupla?"),
 (4, "Porque o cliente vê falhou, tenta de novo, e se o primeiro pedido tinha dado certo, ele paga duas vezes."),
])
def s4(c, p):
    c.title("Timeout = “não sei”")
    cards = [("1 · Nunca chegou", "Nada aconteceu. Retry é seguro.", GREEN),
             ("2 · Processou, resposta perdida", "O efeito aconteceu. Retry ingênuo = 2×.", RED),
             ("3 · Ainda processando", "Pode acontecer depois que você desistiu.", AMBER)]
    c.text((100, 230), "Local: SUCCESS | INSUFFICIENT_FUNDS      Rede: + UNKNOWN", sz=36, c=MUTED, w="SemiBold")
    for i, (t, sub, col) in enumerate(cards):
        if p >= i + 1:
            x = 100 + i * 580
            c.d.rounded_rectangle((x, 320, x + 540, 560), radius=18, fill=CARD, outline=col, width=4)
            c.text((x + 30, 350), t, sz=34, w="Bold", c=col, maxw=480)
            c.text((x + 30, 450), sub, sz=30, maxw=480)
    if p >= 4:
        c.box(100, 640, 1720, 300, "", c=RED, fill="#2a1215")
        c.text((140, 670), "Bug clássico: timeout → FAILED", sz=42, w="Bold", c=RED)
        c.text((140, 750), "Cliente vê “falhou” → tenta de novo → o 1º pedido tinha dado certo → cobrado duas vezes.", sz=34, maxw=1640)

# 5 modelo de dados
@scene("Modelar o “não sei”", [
 (0, "Então seu modelo de dados precisa ser capaz de dizer não sei. No projeto final do curso, uma transferência cuja chamada ao parceiro dá timeout vai para o estado UNKNOWN. Nunca para FAILED."),
 (1, "No código, são três ramos. Sucesso marca concluída. Uma rejeição explícita do parceiro é resposta definitiva, então marca falhou. Timeout marca desconhecida."),
 (2, "Depois, um job pergunta ao parceiro o que aconteceu, e move a transferência para COMPLETED ou FAILED. Diferente da teoria, pagamentos podem ser corrigidos depois: você consulta o status, e uma cobrança errada pode ser estornada. Sistemas reais são construídos em cima de consulta de status e conciliação."),
])
def s5(c, p):
    c.title("Seu modelo precisa dizer “não sei”")
    c.box(100, 260, 320, 120, "PENDING", c=ACC)
    c.box(640, 230, 340, 100, "COMPLETED", c=GREEN, sz=30); c.box(640, 360, 340, 100, "FAILED", c=RED, sz=30)
    c.box(640, 490, 340, 100, "UNKNOWN", c=AMBER, sz=30)
    c.arrow(425, 300, 632, 280, label=""); c.arrow(425, 320, 632, 410); c.arrow(425, 345, 632, 530, c=AMBER); c.text((330, 470), "timeout", sz=28, c=AMBER, w="SemiBold")
    if p >= 2:
        c.box(1200, 490, 560, 100, "job consulta o parceiro", c=AMBER, sz=30)
        c.arrow(985, 540, 1192, 540, c=AMBER)
        c.arrow(1480, 485, 990, 290, c=GREEN); c.arrow(1450, 485, 990, 415, c=RED)
    if p >= 1:
        c.code(100, 660, ["switch (result.kind) {",
                          "  case 'success':  return markCompleted(transfer);",
                          "  case 'rejected': return markFailed(transfer, result.reason); // definitiva",
                          "  case 'timeout':  return markUnknown(transfer);  // perguntar depois",
                          "}"], sz=28, hl=[3])

# 6 escolher timeout
@scene("Escolher o timeout", [
 (0, "Como escolher o número? A Amazon faz assim: primeiro decide quantos timeouts falsos aceita. Timeout falso é desistir de uma chamada que teria dado certo. Por exemplo, um em mil."),
 (1, "Então define o timeout no percentil de latência correspondente. Um em mil é o p99.9. Se o parceiro responde noventa e nove vírgula nove por cento das chamadas em um vírgula oito segundo, um timeout de dois segundos desiste por engano de cerca de uma chamada em mil."),
 (2, "O trade-off corta para os dois lados. Curto demais, você transforma sucessos lentos em desconhecidos e aumenta a carga justamente quando o parceiro está mal. Longo demais, clientes e threads ficam presos esperando uma chamada que não volta."),
])
def s6(c, p):
    c.title("Timeout no percentil certo")
    import math
    x0, y0, x1, y1 = 160, 800, 1760, 280
    c.d.line((x0, y0, x1, y0), fill=LINE, width=3)
    pts = []
    for i in range(300):
        t = i / 299 * 3.0
        v = math.exp(-((math.log(t + 0.05) - math.log(0.6)) ** 2) / 0.35)
        pts.append((x0 + (x1 - x0) * t / 3.0, y0 - (y0 - y1) * v * 0.95))
    c.d.line(pts, fill=ACC, width=5)
    for s in [0, 1, 2, 3]: c.d.text((x0 + (x1 - x0) * s / 3, y0 + 20), f"{s} s", font=font(26), fill=MUTED, anchor="ma")
    c.text((x0, 230), "Latência das chamadas ao banco parceiro", sz=28, c=MUTED)
    if p >= 1:
        for val, lab, col in [(1.8, "p99.9 = 1,8 s", AMBER), (2.0, "timeout = 2 s", RED)]:
            x = x0 + (x1 - x0) * val / 3
            c.d.line((x, y1, x, y0), fill=col, width=4)
            c.d.text((x + 12, y1 + (0 if col == AMBER else 50)), lab, font=font(30, "SemiBold"), fill=col)
        c.text((x0, 880), "Meta: aceitar ~0,1% de timeouts falsos → timeout perto do p99.9", sz=34, w="SemiBold")
    if p >= 2:
        c.text((x0, 950), "Curto demais: sucessos lentos viram UNKNOWN.   Longo demais: threads presas.", sz=32, c=MUTED)

# 7 retries
@scene("Retry com segurança", [
 (0, "Agora, retries. A Builders' Library diz que retries são egoístas. Quem tenta de novo ocupa mais da capacidade do servidor para melhorar as próprias chances. Se todo mundo fizer isso durante um incidente, os retries viram o incidente."),
 (1, "Segundo: retry de algo com efeito colateral só é seguro se a API for idempotente. O EC2 usa um client token em cada requisição: a mesma requisição enviada duas vezes executa uma vez. As chaves de idempotência da Stripe, do módulo dois, são a mesma ideia."),
 (2, "Terceiro: backoff exponencial com jitter. Espere mais a cada tentativa, ponha um limite, e some um valor aleatório, para que milhares de clientes não voltem no mesmo instante."),
 (3, "Quarto: faça retry em uma camada só."),
 ("PAUSA", "Pergunta: a aplicação, o cliente HTTP e o load balancer fazem até três tentativas cada um. Um clique do usuário vira quantas chamadas?"),
 (4, "Vinte e sete. Três vezes três vezes três. Escolha um único lugar na stack para fazer retry."),
])
def s7(c, p):
    c.title("Quatro regras de retry")
    items = [("Retries são “egoístas”: em incidente, eles viram o incidente", ACC),
             ("Só com idempotência (client token do EC2, idempotency key da Stripe)", ACC),
             ("Backoff exponencial + limite + jitter", ACC),
             ("Retry em UMA camada só", ACC)]
    c.bullets(100, 250, items[:min(p + 1, 4)], sz=36, gap=80)
    if p >= 2:
        import random; random.seed(3)
        bx, by = 1080, 600
        c.text((100, 590), "Espera antes de cada tentativa", sz=28, c=MUTED)
        for i in range(5):
            base = min(2 ** i * 40, 520)
            c.d.rectangle((100, 650 + i * 50, 100 + base, 680 + i * 50), fill=LINE)
            j = random.randint(0, int(base * 0.6))
            c.d.rectangle((100 + base, 650 + i * 50, 100 + base + j, 680 + i * 50), fill=AMBER)
        c.text((100, 910), "cinza: backoff exponencial    amarelo: jitter aleatório", sz=26, c=MUTED)
    if p >= 4:
        c.box(1100, 600, 720, 330, "", c=RED, fill="#2a1215")
        c.d.text((1460, 690), "3 × 3 × 3 = 27", font=font(80, "Bold"), fill=FG, anchor="mm")
        c.d.text((1460, 790), "app · cliente HTTP · load balancer", font=font(30), fill=MUTED, anchor="mm")
        c.d.text((1460, 850), "1 clique → 27 chamadas", font=font(34, "SemiBold"), fill=RED, anchor="mm")

# 8 detecção e SLOs
@scene("Detecção de falhas e SLOs", [
 (0, "Você não enxerga outra máquina. Só detecta falhas com timeouts e heartbeats. No Cassandra, cada nó decide sozinho se um par está vivo ou morto, e dois nós podem discordar sem que nenhum esteja errado. De fora, um nó lento e um nó morto parecem iguais. Um detector de falhas só pode suspeitar."),
 (1, "E cuidado com a armadilha oposta. Na Amazon, um servidor de catálogo com disco cheio passou a devolver respostas vazias muito rápido. O load balancer entendeu rápido como saudável, mandou quase todo o tráfego para ele, e o site caiu."),
 (2, "Para falar de disponibilidade, use os noves. Noventa e nove vírgula nove por cento são umas oito horas fora do ar por ano. Quatro noves, uns cinquenta e três minutos."),
 (3, "E o vocabulário do Google. SLI é a medida, por exemplo a fração de transferências bem-sucedidas. SLO é a meta para essa medida. SLA é um contrato com consequência. Se nada acontece quando você não cumpre, é SLO, não SLA. E cem por cento é a meta errada: seu parceiro vai cair em algum momento, e o design precisa assumir isso."),
])
def s8(c, p):
    c.title("Lento e morto parecem iguais")
    c.bullets(100, 240, [("Detecção = timeouts + heartbeats; só dá para suspeitar", ACC)] +
              ([("“Responde rápido” ≠ “saudável” (disco cheio, respostas vazias)", RED)] if p >= 1 else []), sz=34, gap=70)
    if p >= 2:
        rows = [("99%", "≈ 3,7 dias"), ("99,9%", "≈ 8,8 horas"), ("99,99%", "≈ 53 min"), ("99,999%", "≈ 5,3 min")]
        c.text((100, 420), "Indisponibilidade por ano", sz=28, c=MUTED)
        for i, (a, b) in enumerate(rows):
            y = 470 + i * 90
            c.d.rounded_rectangle((100, y, 800, y + 75), radius=10, fill=CARD)
            c.d.text((140, y + 38), a, font=font(36, "Bold"), fill=FG, anchor="lm")
            c.d.text((760, y + 38), b, font=font(34), fill=MUTED, anchor="rm")
    if p >= 3:
        defs = [("SLI", "a medida (ex.: % de transferências OK)", ACC), ("SLO", "a meta (ex.: 99,9% em ≤ 300 ms, 30 dias)", GREEN),
                ("SLA", "contrato com consequência", AMBER)]
        for i, (k, v, col) in enumerate(defs):
            y = 470 + i * 125
            c.d.rounded_rectangle((900, y, 1820, y + 105), radius=12, fill=CARD, outline=col, width=3)
            c.d.text((940, y + 52), k, font=font(40, "Bold"), fill=col, anchor="lm")
            c.text((1080, y + 32), v, sz=30, maxw=720)
        c.text((900, 860), "100% é a meta errada.", sz=34, w="SemiBold", c=RED)

# 9 relógios
@scene("Relógios em que você não pode confiar", [
 (0, "Agora o tempo. Todo servidor tem seu próprio relógio, e todo relógio deriva. Eles se corrigem via NTP. A correção normal é o slewing: andar um pouco mais rápido ou mais devagar até alcançar. A outra é o stepping: pular de uma vez. E alguns programas quebram feio com esse pulo."),
 (1, "O caso famoso é da Cloudflare, no primeiro dia de dois mil e dezessete. Um leap second fez o relógio voltar. O código, escrito em Go, media a duração subtraindo o horário de início do horário atual. A duração saiu negativa. A média das durações ficou negativa. Esse valor foi passado para uma função de número aleatório que entra em pânico com argumento negativo. Resultado: horas de falhas no DNS."),
 (2, "A causa raiz, nas palavras deles: a crença de que o tempo não pode andar para trás. Por isso existem dois relógios. O de hora do dia, Date.now, diz a data, mas pode pular. Use para timestamps que pessoas leem. O monotônico, hrtime, só anda para frente. O valor absoluto não significa nada, mas a diferença entre duas leituras é uma duração confiável."),
 ("PAUSA", "Pergunta: qual relógio você usa para medir um timeout?"),
 (3, "O monotônico. Sempre. Hora do dia é para humanos lerem."),
])
def s9(c, p):
    c.title("O tempo pode andar para trás")
    if p < 1:
        c.bullets(100, 260, [("Todo relógio deriva (medido em ppm)", ACC), ("Slewing: corrige devagar (padrão do chrony)", GREEN),
                             ("Stepping: pula de uma vez → software quebra", RED)], sz=38, gap=90)
    if p >= 1:
        chain = ["leap second: relógio volta", "agora − início < 0", "média negativa", "rand.Int63n(neg) → panic", "DNS falhando por horas"]
        for i, t in enumerate(chain):
            x = 100 + i * 352
            c.box(x, 260, 320, 170, "", c=RED if i else AMBER)
            c.text((x + 160, 345), t, sz=28, anchor="mm", maxw=280, w="SemiBold")
            if i < 4: c.arrow(x + 322, 345, x + 350, 345, c=RED, w=4)
        c.text((100, 460), "Cloudflare, 1º de janeiro de 2017", sz=28, c=MUTED)
    if p >= 2:
        c.box(100, 540, 840, 330, "", c=AMBER)
        c.text((140, 570), "Hora do dia", sz=40, w="Bold", c=AMBER); c.text((140, 630), "Date.now()", sz=30, c=MUTED)
        c.text((140, 690), "Pode pular. Para timestamps que pessoas leem.", sz=32, maxw=760)
        c.box(980, 540, 840, 330, "", c=GREEN)
        c.text((1020, 570), "Monotônico", sz=40, w="Bold", c=GREEN); c.text((1020, 630), "process.hrtime.bigint()", sz=30, c=MUTED)
        c.text((1020, 690), "Só anda para frente. Para durações, timeouts e latência.", sz=32, maxw=760)
    if p >= 3: c.text((W / 2, 930), "Timeout → relógio monotônico. Sempre.", sz=42, w="Bold", c=GREEN, anchor="mm")

# 10 ordem de eventos
@scene("Ordenar eventos sem relógio de parede", [
 (0, "Se relógios derivam e pulam, comparar timestamps de duas máquinas pode inverter a ordem. A Cockroach Labs chama isso de causal reverse. O nó um tem o relógio certo. O nó dois está cem milissegundos atrasado."),
 (1, "A transação um faz commit no nó ene um, com timestamp cento e cinquenta. Cinquenta milissegundos depois, alguém que viu ela terminar inicia a transação dois no nó ene dois, que carimba cem. Ordenando por timestamp, a dois parece ter vindo antes da um. Mas ela começou depois."),
 (2, "Então de onde vem a ordem? De uma autoridade única. Mas cuidado: um id sequence do Postgres não serve. Ele tem buracos, e o valor é pego quando nextval roda, não no commit. O id onze pode fazer commit antes do dez."),
 (3, "A solução é fazer da própria linha da conta a autoridade. Dentro da transação, você incrementa um contador na linha da conta, o que trava a linha até o commit, e usa esse número no lançamento. A ordem por conta fica estrita e sem buracos. O created_at é para humanos. O seq é a ordem."),
])
def s10(c, p):
    c.title("A ordem vem de uma autoridade única")
    if p <= 1:
        c.text((100, 240), "N1 (relógio certo)", sz=30, c=ACC); c.text((100, 460), "N2 (100 ms atrasado)", sz=30, c=AMBER)
        c.d.line((100, 340, 1820, 340), fill=LINE, width=4); c.d.line((100, 560, 1820, 560), fill=LINE, width=4)
        if p >= 1:
            c.d.ellipse((700, 320, 740, 360), fill=ACC); c.text((720, 380), "T1 commit · ts = 150", sz=30, anchor="ma")
            c.d.ellipse((1100, 540, 1140, 580), fill=AMBER); c.text((1120, 600), "T2 começa depois · ts = 100", sz=30, anchor="ma")
            c.arrow(740, 350, 1100, 550, c=MUTED, w=3, label="+50 ms reais")
            c.box(100, 720, 1720, 160, "Ordenar por timestamp: T2 (100) “antes” de T1 (150). Errado.", c=RED, fill="#2a1215", sz=38)
    else:
        c.bullets(100, 240, [("Sequence do Postgres: ids únicos, com buracos, não é a ordem de commit", RED)], sz=34)
        if p >= 3:
            c.code(100, 360, ["BEGIN;",
                              "-- trava a linha da conta até o COMMIT",
                              "UPDATE accounts SET last_seq = last_seq + 1",
                              " WHERE id = $1 RETURNING last_seq;        -- ex.: 42",
                              "INSERT INTO ledger_entries (account_id, seq, amount_cents, created_at)",
                              "VALUES ($1, 42, -5000, now());   -- created_at: humanos · seq: ordem",
                              "COMMIT;"], sz=28, hl=[2, 3])
            c.text((100, 830), "Nunca: “last write wins” por timestamp para decidir um saldo.", sz=34, c=AMBER, w="SemiBold")

# 11 revisão rápida
@scene("Revisão relâmpago", [
 (0, "Hora da revisão relâmpago. São três perguntas, sem olhar."),
 ("PAUSA", "Pergunta um: quais são os três desfechos possíveis de um timeout?"),
 (1, "Não chegou. Aconteceu mas a resposta se perdeu. Ou ainda está em andamento. Por isso o estado é UNKNOWN, e um job consulta o parceiro."),
 ("PAUSA", "Pergunta dois: o que torna seguro fazer retry de um pagamento?"),
 (2, "Resposta: idempotência. Uma chave enviada em cada requisição, para que duas tentativas executem uma vez só. Mais backoff com jitter, em uma camada só."),
 ("PAUSA", "Pergunta três: por que não ordenar os lançamentos de uma conta pelo created_at?"),
 (3, "Porque relógios derivam e pulam. A ordem vem de uma autoridade única: um seq por conta, incrementado dentro da transação."),
])
def s11(c, p):
    c.title("Revisão relâmpago")
    qa = [("Os 3 desfechos de um timeout?", "Não chegou · aconteceu e a resposta se perdeu · ainda em andamento → UNKNOWN + consulta"),
          ("O que torna seguro o retry de um pagamento?", "Idempotência (chave por requisição) + backoff com jitter, em uma camada"),
          ("Por que não ordenar por created_at?", "Relógios derivam e pulam → seq por conta, na transação")]
    for i, (q, a) in enumerate(qa):
        y = 260 + i * 230
        c.text((100, y), f"{i+1}. {q}", sz=40, w="Bold")
        if p >= i + 1: c.text((140, y + 70), a, sz=32, c=GREEN, maxw=1650)

# 12 encerramento
@scene("O que anotar e próximo passo", [
 (0, "Antes de fechar, anote três coisas com as suas palavras. Os três desfechos de um timeout e o que seu sistema faz em cada um. Como você escolheria o timeout do banco parceiro, e em que camada ficam os retries. E um exemplo concreto de pagamento em que ordenar pelo relógio daria errado."),
 (1, "Depois, transforme as perguntas do Teste-se em flashcards no Anki. E se tiver tempo, leia o artigo do Gabrielson, Challenges with distributed systems, que é a fonte principal de hoje. Até a próxima aula."),
])
def s12(c, p):
    c.title("Anote com as suas palavras")
    c.bullets(100, 260, [("Os 3 desfechos de um timeout e a ação do sistema em cada um", ACC),
                         ("Como escolher o timeout do parceiro e onde ficam os retries", ACC),
                         ("Um exemplo de pagamento em que ordenar pelo relógio dá errado", ACC)], sz=38, gap=90)
    if p >= 1:
        c.box(100, 640, 1720, 260, "", c=GREEN)
        c.text((140, 670), "Próximo passo", sz=40, w="Bold", c=GREEN)
        c.text((140, 740), "Flashcards no Anki com as perguntas do “Teste-se”.", sz=34)
        c.text((140, 800), "Fonte principal: Gabrielson, “Challenges with distributed systems” (AWS Builders' Library).", sz=30, c=MUTED, maxw=1640)

PAUSE_SECS = 6

_K = None
def tts(text, path):
    global _K
    if os.path.exists(path): return
    import numpy as np, soundfile as sf
    from kokoro_onnx import Kokoro
    if _K is None:
        B = os.path.dirname(os.path.abspath(__file__)); _K = Kokoro(B + "/kokoro-v1.0.onnx", B + "/voices-v1.0.bin")
    marked = speak(text)
    sents = [x for x in re.split(r"(?<=[.?!])\s+", marked) if x.strip()]
    out = []; sr = 24000
    for snt in sents:
        ph = []
        for i, part in enumerate(re.split(r"\{([^}]*)\}", snt)):
            if part.strip(): ph.append(_K.tokenizer.phonemize(part, lang="en-us" if i % 2 else "pt-br"))
        a, sr = _K.create(" ".join(ph), voice=VOICE_ID, speed=SPEED, is_phonemes=True)
        out += [a, np.zeros(int(sr * 0.32), dtype=np.float32)]
    sf.write(path, np.concatenate(out), sr)

def dur(path):
    with wave.open(path) as w: return w.getnframes() / w.getframerate()

def main():
    segs = []; total = len(SCENES); n = 0; script = []
    for si, (section, fn, beats) in enumerate(SCENES):
        script.append(f"\n## {section}\n")
        step = 0
        for bi, (b, text) in enumerate(beats):
            n += 1; base = f"{OUT}/s{si:02d}_{bi:02d}"
            if b == "PAUSA":
                c = Canvas(section, si + 1, total); fn(c, step)
                ov = Image.new("RGBA", (W, H), (2, 6, 23, 225)); c.im = Image.alpha_composite(c.im.convert("RGBA"), ov).convert("RGB")
                c.d = ImageDraw.Draw(c.im)
                c.d.text((W / 2, 300), "PAUSE E RESPONDA", font=font(40, "Bold"), fill=AMBER, anchor="mm")
                c.text((W / 2, 480), re.sub(r"^Pergunta( um| dois| três)?: ", "", text), sz=54, w="SemiBold", anchor="mm", maxw=1500)
                tts(text, base + "_q.wav"); qd = dur(base + "_q.wav")
                img = base + ".png"; c.im.save(img)
                segs.append((img, base + "_q.wav", qd + PAUSE_SECS))
                script.append(f"> **Pausa:** {text}\n")
                continue
            step = b
            c = Canvas(section, si + 1, total); fn(c, step)
            img = base + ".png"; c.im.save(img)
            wav = base + ".wav"; tts(text, wav)
            segs.append((img, wav, dur(wav) + 0.6))
            script.append(text + "\n")
    # monta cada segmento e concatena
    parts = []
    for i, (img, wav, d) in enumerate(segs):
        mp4 = f"{OUT}/part{i:03d}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "25", "-i", img, "-i", wav,
                        "-af", f"apad,atrim=0:{d:.2f},aresample=44100", "-t", f"{d:.2f}",
                        "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p", "-r", "25",
                        "-c:a", "aac", "-b:a", "128k", "-ac", "1", mp4], check=True)
        parts.append(mp4)
    with open(f"{OUT}/list.txt", "w") as f:
        for p in parts: f.write(f"file '{p}'\n")
    final = f"{OUT}/m01-dia1-falhas-timeouts-e-tempo.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", f"{OUT}/list.txt", "-c", "copy",
                    "-movflags", "+faststart", final], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", final, "-vn", "-c:a", "libmp3lame", "-b:a", "96k",
                    f"{OUT}/m01-dia1-falhas-timeouts-e-tempo.mp3"], check=True)
    open(f"{OUT}/roteiro.md", "w").write("# Roteiro · M1 Dia 1 · Falhas, timeouts e tempo\n" + "\n".join(script))
    print("total s:", sum(d for _, _, d in segs))

if __name__ == "__main__":
    main()
