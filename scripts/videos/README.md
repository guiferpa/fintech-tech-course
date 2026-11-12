# Gerador das vídeo-aulas

Cada aula é um roteiro em Python (`specs/<id>.py`) com cenas, texto de tela e narração. `engine.py` desenha os slides (1920x1080, Pillow), narra com Kokoro TTS (voz `pm_alex`, termos técnicos em inglês com fonética en-us) e monta MP4 + MP3 + roteiro.md com ffmpeg.

## Requisitos

- Python 3 com `pillow`, `kokoro-onnx`, `soundfile`
- `ffmpeg`, `espeak-ng`, fontes Inter e DejaVu Sans Mono
- `kokoro-v1.0.onnx` e `voices-v1.0.bin` nesta pasta (releases do kokoro-onnx; ignorados pelo git)

## Uso

```sh
python3 engine.py preview specs/m10d3.py pv.png   # folha de contato; "avisos: []" = nada estourando
python3 engine.py specs/m10d3.py                  # gera em ../../videos
./runner.sh                                       # gera todos os que faltam
python3 index.py                                  # atualiza videos/README.md
```

`gerar-video-m01-dia1.py` é o piloto (M1 dia 1), anterior ao formato de specs.

## Formato do spec

`META` (id, file, label, title, subtitle), `EN_TERMS` (lidos em inglês), `EN_SAY` (pronúncia falada) e `SCENES`. Cada cena tem `type` (title, bullets, steps, table, cards, code, compare, flow, statement, recap) e `beats = [(passo, texto) | ("P", pergunta)]`. O passo k revela os k primeiros elementos; o callout entra depois do último item. `"P"` mostra a pergunta e deixa 6 s de silêncio.
