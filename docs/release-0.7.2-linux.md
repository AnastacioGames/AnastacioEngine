# Release 0.7.2 — passo a passo para o Linux (notebook)

Instruções para a sessão do Claude no notebook Linux. A sessão Windows coordena a release: ela criou o
rascunho `v0.7.2` no GitHub, monta o Windows, junta os hashes e **publica**. O Linux só monta, testa e envia
os pacotes Linux para o rascunho. Leia antes [AGENTS.md](../AGENTS.md), a seção "Dicas comuns de montagem" de
[releases.md](releases.md) e a seção 0.7.1 de lá (mesmo fluxo).

## Regras

- **Não** rode `gh release create` (o rascunho já existe; `create` duplica). Confira com `gh release view v0.7.2`.
- **Não** publique o rascunho, não mude a tag e não edite o texto das notas.
- Não mexa na versão: já está 0.7.2 em `main` (`c7077d50d`). Se precisar corrigir código, commit pequeno com
  caminhos explícitos (`git add <arquivos>`, nunca `-a`), push no `main` e anote o hash no relatório.
- Abra janelas do editor/jogo só se o usuário pedir; valide em background.

## Passos

1. **Atualizar o clone de release** (clone separado do de trabalho, como na 0.7.1):
   `git fetch && git checkout main && git pull`. Confira `git log -1` = `c7077d50d` ou mais novo.
   Houve mudança em `DNA_*.h` desde a 0.7.1? (`git diff --stat v0.7.1 HEAD -- '*DNA_*'`) Se sim, build limpo.
2. **Runtime Web** (`emsdk` ativo): `cmake --preset web-runtime-release-linux -S source` e
   `cmake --build --preset web-runtime-release-linux`. Se não linkar por função do editor sem stub no player,
   adicione o stub (como em `507b7006` na 0.7.1).
3. **Container**: 
   `VERSION=0.7.2 WEB_RUNTIME_DIR=/work/build-web-release/bin bash tools/linux/container-build.sh`
   Saída: `build-linux/dist/AnastacioEngine-0.7.2-linux-x86_64.tar.xz` + `.sha256`.
4. **Testes**: `bash tools/linux/testar-release.sh 0.7.2` (pacote extraído em pasta limpa). Esperado: tudo OK
   (23/23 na 0.7.1). Depois, Export Web do pacote extraído com um projeto que tenha `3rd person.range` e
   `fase #2.range` (LibLoad), e exporte também Destruction e ImGui_example.
   Novidades da 0.7.2 para conferir no pacote: a pasta `2.79/scripts/ajuda/` e `startup/range_help.py`
   (botão Help) e os tutoriais existem; o editor carrega sem erro de Python em `-b --python-expr "import bpy"`.
5. **RangeArmor**: sem mudança desde a 0.7.1 (`git diff v0.7.1 HEAD -- tools/rangearmor` vazio). Reaproveite o
   conteúdo da 0.7.1 com a pasta renomeada para `0.7.2` e gere `RangeArmor-0.7.2-linux-x86_64.tar.xz`.
6. **Hashes**: `sha256sum AnastacioEngine-0.7.2-linux-x86_64.tar.xz RangeArmor-0.7.2-linux-x86_64.tar.xz > SHA256SUMS-linux.txt`
7. **Enviar ao rascunho**:
   `gh release upload v0.7.2 AnastacioEngine-0.7.2-linux-x86_64.tar.xz RangeArmor-0.7.2-linux-x86_64.tar.xz SHA256SUMS-linux.txt --clobber`
8. **Registrar**: na seção `## 0.7.2` de [releases.md](releases.md), adicione `### Linux (<data>, notebook Linux, main em <hash>)`
   com tamanhos, sha256, resultado de cada passo e problemas encontrados (modelo: seção 0.7.1). Commit só
   desse arquivo + push no `main`.
9. **Avisar o usuário** com um resumo curto: hashes, testes, commits feitos. A sessão Windows segue daí.

## Se algo falhar

Pare e relate a etapa, o comando e as últimas linhas do erro. Não tente contornar publicando parcial.
