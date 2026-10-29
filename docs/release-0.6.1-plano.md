# Release 0.6.1: divisão do trabalho Windows / Linux

Código fechado no `main` (versão `0.6.1` no executável). Notas da página: [release-notes-0.6.1.md](release-notes-0.6.1.md).
Cada máquina monta, testa e **sobe os próprios arquivos** num release rascunho (draft) `v0.6.1` no GitHub,
criado pelo Windows. O release só é publicado quando os dois lados terminarem.

Procedimento geral: [distribution-0.1.md](distribution-0.1.md) e as dicas em [releases.md](releases.md).

## Windows (Claude no PC Windows)

1. Criar o release rascunho `v0.6.1` com o texto de `release-notes-0.6.1.md`
   (`gh release create v0.6.1 --draft --target main --title "AnastacioEngine 0.6.1" -F docs/release-notes-0.6.1.md`).
2. Build incremental do `main` + `ninja install`; runtime Web em `build-web-release` (vcvars64 + `emsdk_env.bat`).
3. `python tools/stage_release_windows.py 0.6.1 --no-zip`, `stage_release_web.py` na pasta, depois `--zip-only`.
4. RangeArmor: `python tools/stage_rangearmor_windows.py 0.6.1 <zip RangeArmor 0.6.0>`.
5. Testar os zips **extraídos numa pasta limpa**: `blender.crt/`, `0.6.1` no executável, runtime roda a cena de
   teste, editor `-b` abre. `python tools/check_docs.py`.
6. Subir: `gh release upload v0.6.1 AnastacioEngine-0.6.1-windows-x64.zip RangeArmor-0.6.1-windows-x64.zip SHA256SUMS-windows.txt`.
7. Quando o Linux terminar: juntar `SHA256SUMS-windows.txt` + `SHA256SUMS-linux.txt` em `SHA256SUMS.txt`
   (apagar os dois parciais do release), trocar os links do README para 0.6.1, atualizar `releases.md` e
   publicar o release (`gh release edit v0.6.1 --draft=false`).

## Linux (Claude no PC Linux)

Num clone separado com o `main` atualizado (`git pull`), conferir antes que o draft `v0.6.1` existe
(`gh release view v0.6.1`).

1. Runtime Web: recompilar o preset `web-runtime-release` com o `main` atual e conferir o manifesto.
2. `VERSION=0.6.1 WEB_RUNTIME_DIR=/work/build-web-release/bin bash tools/linux/container-build.sh`
   (passar `-e VERSION=0.6.1 -e WEB_RUNTIME_DIR=...` no `podman run`, a imagem traz valores antigos).
3. `bash tools/linux/testar-release.sh 0.6.1`: todos OK (ldd, arquivos, Python 3.11, `tools/test_*.py`,
   runtime e teste modal com `xvfb-run`).
4. RangeArmor Linux: painel em `rust:1.95-bullseye` e `bash tools/linux/stage_rangearmor_linux.sh 0.6.1`
   (launcher registrado `3cb1ade9…`); `test_universal_linux.py --run`.
5. Com janela: editor abre e mostra 0.6.1; um jogo roda no modo Fixed (movimento liso).
6. Opcional: teste do Wine com o pacote `wine_timing` do disco D: (`bash rodar.sh`), resultado em
   `timing_linux_result.txt`.
7. Subir: `sha256sum` dos dois arquivos em `SHA256SUMS-linux.txt` e
   `gh release upload v0.6.1 AnastacioEngine-0.6.1-linux-x86_64.tar.xz RangeArmor-0.6.1-linux-x86_64.tar.xz SHA256SUMS-linux.txt`.
8. Anotar em `docs/releases.md` (seção 0.6.1) tamanhos, sha256 e resultados dos testes; commit + push.
   **Não publicar** o release: o Windows publica depois de juntar os hashes.

Se algum teste falhar, corrigir no `main` com commit próprio, avisar na seção 0.6.1 de `releases.md` e
remontar o pacote; não subir pacote com teste falhando.
