#!/usr/bin/env bash
# Gera resumos por area do engine usando o modelo local (Ollama), para que
# agentes (Claude, Codex) consultem esses resumos em docs/local-knowledge/
# antes de ler o codigo-fonte inteiro. Nao substitui leitura direta para
# mudancas reais - serve so como "por onde comecar".
#
# Uso:
#   tools/build_local_knowledge.sh              # regenera todas as areas
#   tools/build_local_knowledge.sh rendering     # regenera so uma area
#
# Variaveis opcionais:
#   MAX_FILES_PER_AREA (padrao 25)
#   MAX_LINES_PER_FILE (padrao 200) - trecho inicial de cada arquivo enviado ao modelo

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$ROOT/docs/local-knowledge"
ASK="$ROOT/tools/ask_local.sh"
MAX_FILES_PER_AREA="${MAX_FILES_PER_AREA:-25}"
MAX_LINES_PER_FILE="${MAX_LINES_PER_FILE:-200}"

mkdir -p "$OUT_DIR"

declare -A AREAS
AREAS[rendering]="source/source/gameengine/Rasterizer source/source/blender/gpu"
AREAS[physics]="source/source/gameengine/Physics source/source/blender/physics"
AREAS[logic-scripting]="source/source/gameengine/GameLogic source/source/gameengine/Expressions source/source/blender/python"
AREAS[scenegraph-converter]="source/source/gameengine/SceneGraph source/source/gameengine/Converter source/source/gameengine/Ketsji"
AREAS[dna-blend]="source/source/blender/makesdna source/source/blender/blenloader"

build_area() {
  local area="$1"
  local dirs="${AREAS[$area]:-}"
  if [ -z "$dirs" ]; then
    echo "Area desconhecida: $area (opcoes: ${!AREAS[*]})" >&2
    return 1
  fi

  local out_file="$OUT_DIR/$area.md"
  echo "== Gerando $out_file =="

  {
    echo "# Conhecimento local: $area"
    echo
    echo "> Gerado por \`tools/build_local_knowledge.sh\` via modelo local (Ollama)."
    echo "> Resumo raso para orientacao inicial - para decisoes reais, leia o arquivo completo."
    echo
  } > "$out_file"

  local count=0
  for dir in $dirs; do
    local full_dir="$ROOT/$dir"
    [ -d "$full_dir" ] || continue
    while IFS= read -r -d '' file; do
      [ "$count" -ge "$MAX_FILES_PER_AREA" ] && break 2
      local rel="${file#"$ROOT"/}"
      echo "  - $rel"
      local excerpt
      excerpt="$(head -n "$MAX_LINES_PER_FILE" "$file")"
      local summary
      summary="$("$ASK" "Em 3-5 linhas, resuma o papel deste arquivo dentro de um game engine C++ (fork do UPBGE/Blender 2.79): o que ele implementa e com que outros sistemas provavelmente interage." <<< "$excerpt" 2>/dev/null || echo "(falha ao consultar modelo local)")"
      {
        echo "## $rel"
        echo
        echo "$summary"
        echo
      } >> "$out_file"
      count=$((count + 1))
    done < <(find "$full_dir" -maxdepth 2 -type f \( -name '*.h' -o -name '*.cpp' \) -print0 | sort -z)
  done
  echo "  ($count arquivos resumidos)"
}

if [ $# -eq 0 ]; then
  for area in "${!AREAS[@]}"; do
    build_area "$area"
  done
else
  build_area "$1"
fi
