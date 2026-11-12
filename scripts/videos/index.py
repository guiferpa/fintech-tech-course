#!/usr/bin/env python3
"""Gera videos/README.md: um vídeo por slot de leitura da agenda (docs/sessions.json)."""
import json, re, glob, os, subprocess, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.normpath(HERE + "/../.."); V = ROOT + "/videos"
d = json.load(open(ROOT + "/docs/sessions.json"))
files = {"m01d1": ("m01-dia1-falhas-timeouts-e-tempo-v2", "m01-dia1-roteiro.md", "Falhas, timeouts e tempo")}
for p in glob.glob(HERE + "/specs/*.py"):
    spec = importlib.util.spec_from_file_location("s", p); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    files[m.META["id"]] = (m.META["file"], m.META["file"] + "-roteiro.md", m.META["title"])
def dur(f):
    try: return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f], capture_output=True, text=True).stdout)
    except Exception: return None
out = ["# Vídeo-aulas por slot da agenda", "",
       "Um vídeo para cada slot de leitura: dias 1 a 3 de cada módulo, mais o dia 1 do C2. Os dias de conclusão, os checkpoints e o projeto final são de prática e não têm vídeo.", "",
       "Cada aula tem três perguntas de abertura, diagramas revelados por partes, pausas \"pause e responda\", uma revisão relâmpago e o que anotar. O roteiro é o texto completo da narração. Para regerar, veja [scripts/videos](../scripts/videos/README.md).", "",
       "| Semana | Dia | Slot | Aula | Vídeo | Roteiro | Duração |", "|---|---|---|---|---|---|---|"]
for s in d["sessions"]:
    mm = re.search(r"lessons/(\d\d)-[^/]+/day-(\d)\.md", s["description"]["en"])
    key = f"m{mm.group(1)}d{mm.group(2)}" if mm else ("c2d1" if (s["module"] == "C2" and s["day"] == 1) else None)
    if key and key in files:
        f, r, t = files[key]; x = dur(f"{V}/{f}.mp4")
        out.append(f"| {s['week']} | {s['day']} | {s['module']} | {t} | [mp4]({f}.mp4) | [roteiro](roteiros/{r}) | {f'{x/60:.0f} min' if x else ''} |")
    else:
        out.append(f"| {s['week']} | {s['day']} | {s['module']} | {s['title']['pt-BR'].split('] ', 1)[-1]} | prática, sem vídeo | | |")
open(V + "/README.md", "w").write("\n".join(out) + "\n")
