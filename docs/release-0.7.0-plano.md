# Release 0.7.0: o que falta no Linux

O rascunho (draft) `v0.7.0` já existe no GitHub, criado pelo Windows. Notas: [release-notes-0.7.0.md](release-notes-0.7.0.md).
Procedimento geral: [distribution-0.1.md](distribution-0.1.md) e as dicas em [releases.md](releases.md).

O pacote testado antes (16 de 16 em `c1f62491`) não serve: faltam o splash final e as últimas correções. **Remonte.**

Num clone separado:

1. `git pull` no `main`, e confira que `gh release view v0.7.0` mostra o draft.
2. Recompile o runtime Web (preset `web-runtime-release`) com o `main` atual e confira o manifesto.
3. Monte o pacote: `VERSION=0.7.0 WEB_RUNTIME_DIR=/work/build-web-release/bin bash tools/linux/container-build.sh`.
   No `podman run`, passe `-e VERSION=0.7.0 -e WEB_RUNTIME_DIR=/work/build-web-release/bin`, porque a imagem traz valores antigos.
4. Teste: `bash tools/linux/testar-release.sh 0.7.0`. Tudo precisa dar OK.
5. RangeArmor: painel em `rust:1.95-bullseye` e `bash tools/linux/stage_rangearmor_linux.sh 0.7.0`
   (launcher registrado `3cb1ade9…`).
6. Com janela: o editor abre, mostra 0.7.0 e o splash da oficina com logo e título inteiros.
7. Suba:
   `sha256sum` dos dois arquivos em `SHA256SUMS-linux.txt` e
   `gh release upload v0.7.0 AnastacioEngine-0.7.0-linux-x86_64.tar.xz RangeArmor-0.7.0-linux-x86_64.tar.xz SHA256SUMS-linux.txt`.
8. Anote em `docs/releases.md` (seção 0.7.0) tamanhos, sha256 e resultados; commit + push.

**Não publique o release.** O Windows junta os hashes e publica. Se um teste falhar, corrija no `main` com commit
próprio e remonte; não suba pacote com teste falhando.
