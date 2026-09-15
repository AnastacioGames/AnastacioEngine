#!/usr/bin/env bash
# Consulta o modelo de codigo local (Ollama) para tarefas de "grunt work"
# (resumir arquivos grandes, primeira varredura em codigo, boilerplate)
# antes de trazer so o essencial para o contexto do Claude Code.
#
# Uso:
#   tools/ask_local.sh "resuma o que essa funcao faz" < arquivo.cpp
#   tools/ask_local.sh "explique este trecho: $(cat arquivo.cpp)"

set -euo pipefail

MODEL="${OLLAMA_MODEL:-qwen2.5-coder:14b}"
PROMPT="$1"
STDIN_CONTENT=""
if [ ! -t 0 ]; then
  STDIN_CONTENT="$(cat)"
fi

FULL_PROMPT="$PROMPT"
if [ -n "$STDIN_CONTENT" ]; then
  FULL_PROMPT="$PROMPT

$STDIN_CONTENT"
fi

PYTHON_BIN="${PYTHON_BIN:-/c/Users/f_bro/AppData/Local/Programs/Python/Python310/python}"

PYTHONIOENCODING=utf-8 "$PYTHON_BIN" - "$MODEL" "$FULL_PROMPT" <<'PYEOF'
import io
import json
import sys
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

model = sys.argv[1]
prompt = sys.argv[2]

req = urllib.request.Request(
    "http://127.0.0.1:11434/api/generate",
    data=json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req) as resp:
    result = json.loads(resp.read().decode("utf-8"))
    print(result.get("response", ""))
PYEOF
