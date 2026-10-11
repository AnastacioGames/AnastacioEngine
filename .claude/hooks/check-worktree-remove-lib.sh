#!/usr/bin/env bash
# Bloqueia "git worktree remove <path>" quando <path>/lib for um link
# (symlink/junction) para a lib real. No Windows, remover um worktree assim
# pode varrer o conteudo real da lib atraves do link (ja aconteceu antes:
# feedback_worktree_lib_junction.md). O link deve ser removido sozinho,
# com `cmd //c rmdir`, antes do worktree remove.
set -u

input=$(cat)
# jq pode nao estar no PATH deste shell; extrai "command" na mao (sem
# dependencia externa). Funciona para o JSON de hook de tool_input simples.
if command -v jq >/dev/null 2>&1; then
  cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // ""' 2>/dev/null)
else
  cmd=$(printf '%s' "$input" | grep -o '"command"[[:space:]]*:[[:space:]]*"\([^"\\]\|\\.\)*"' | head -1 \
    | sed -E 's/^"command"[[:space:]]*:[[:space:]]*"//; s/"$//' \
    | sed 's/\\"/"/g; s/\\\\/\\/g')
fi

case "$cmd" in
  *"worktree remove"*) ;;
  *) exit 0 ;;
esac

# Primeiro token depois de "remove" que nao seja --force/--force=... etc.
path=""
rest=$(printf '%s' "$cmd" | sed -E 's/.*worktree[[:space:]]+remove//')
for tok in $rest; do
  case "$tok" in
    --*) continue ;;
    *) path="$tok"; break ;;
  esac
done
# Tira aspas simples/duplas ao redor, se houver.
path="${path%\"}"; path="${path#\"}"
path="${path%\'}"; path="${path#\'}"

if [ -z "$path" ]; then
  exit 0
fi

win_path=$(cygpath -w "$path/lib" 2>/dev/null || echo "$path/lib")

# -L pega symlink de verdade; LinkType via PowerShell pega tambem junction
# (mklink /J), que o bash do MSYS enxerga como diretorio comum.
link_type=""
if [ -L "$path/lib" ]; then
  link_type="SymbolicLink"
else
  link_type=$(powershell.exe -NoProfile -NonInteractive -Command \
    "if (Test-Path -LiteralPath '$win_path') { (Get-Item -LiteralPath '$win_path' -Force).LinkType }" \
    2>/dev/null | tr -d '\r\n')
fi

if [ -n "$link_type" ]; then
  reason="BLOQUEADO: '$path/lib' e um link ($link_type) para a lib real. No Windows, git worktree remove pode varrer o conteudo real atraves do link (ja aconteceu, veja feedback_worktree_lib_junction.md). Remova so o link primeiro com: cmd /c rmdir \"$win_path\" -- depois repita o git worktree remove."
  escaped=$(printf '%s' "$reason" | sed 's/\\/\\\\/g; s/"/\\"/g')
  printf '%s' "{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\",\"permissionDecision\":\"deny\",\"permissionDecisionReason\":\"$escaped\"}}"
  exit 0
fi

exit 0
