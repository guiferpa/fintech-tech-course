#!/bin/bash
# Fila: renderiza cada roteiro que ainda não tem vídeo. Para quando existir o arquivo STOP e a fila estiver vazia.
set -o pipefail
cd "$(dirname "$0")"; OUT=../../videos
while true; do
  did=0
  for s in specs/*.py; do
    f=$(python3 -c "import re;print(re.search(r'file=\"([^\"]+)\"',open('$s').read()).group(1))")
    if [ ! -f "$OUT/$f.mp4" ] && [ ! -f "$s.failed" ]; then
      echo "== $(date +%T) $s"; python3 engine.py "$s" "$OUT" 2>&1 | grep -v -i warn || touch "$s.failed"; did=1
    fi
  done
  [ $did = 0 ] && [ -f STOP ] && break
  [ $did = 0 ] && sleep 30
done
echo FIM
