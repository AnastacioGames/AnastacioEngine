# Plano de modernização da Range Armor

## Objetivo

Manter a Range Armor como ferramenta opcional de empacotamento para a
AnastacioEngine, com suporte real a Windows x86_64 e Linux x86_64. O pacote
do jogo não deve depender de um interpretador Python interno: o launcher deve
executar o `RangeRuntime` diretamente.

## Etapas

1. **Launcher direto — concluída no código.** O binário Rust lê
   `launcher/config.json`, resolve `EngineWindows64` ou `EngineLinux64`, muda
   para `data/` e executa o `MainFile` diretamente. Os campos `Python*`
   permanecem no JSON somente para compatibilidade com projetos antigos.
2. **Autor e interface — concluída no código.** Python continua sendo usado
   apenas para as tarefas de autoria (`build_data.py`, `build_release.py`). A
   interface aceita `python3`/`python` do sistema como fallback e não exige
   Python dentro de `engine/Linux64` para executar ou exportar Linux.
3. **Runtime e arquivos — concluída no código.** O painel copia todas as
   plataformas disponíveis: procura `build/bin` para Windows e `build-linux/bin`
   para Linux, inclusive quando este último foi produzido pelo WSL. Os caminhos
   explícitos `RANGEARMOR_ENGINE_DIR_WINDOWS64` e
   `RANGEARMOR_ENGINE_DIR_LINUX64` substituem essa descoberta. Linux conserva a
   permissão de execução e gera `.tar.xz`; Windows permanece em `.zip`.
4. **Build do launcher — concluída no código.** Os alvos são
   `x86_64-pc-windows-msvc` e `x86_64-unknown-linux-gnu`; UPX é opcional.
5. **Validação final — concluída.** O launcher Rust passou em
   seus 2 testes unitários, o painel passou em 25 testes, os scripts Python
   passaram em `py_compile`, e o binário Windows x86_64 de produção foi
   compilado e executado com `--help`. No Debian/WSL, o launcher foi
   compilado com Rust/Cargo, um projeto temporário recebeu
   `build-linux/bin` por `RANGEARMOR_ENGINE_DIR`, a release `.tar.xz` foi
   extraída sob `/tmp` e o jogo iniciou pelo launcher no pacote extraído.
   A cena de smoke test chegou à inicialização de hardware OpenGL. Validações
   futuras de `.rasec`, scripts e áudio dependem de conteúdo que use esses
   recursos.

## Cópia de runtimes no painel Windows

O botão **Copy Available Range Engine Files** copia Windows64 e Linux64 quando
as pastas convencionais `build/bin` e `build-linux/bin` existem no checkout.
Assim, um runtime Linux compilado pelo WSL no mesmo drive fica disponível no
painel Windows sem copiar arquivos manualmente.

Se os runtimes estiverem em outro local, defina antes de abrir o painel:

```powershell
$env:RANGEARMOR_ENGINE_DIR_WINDOWS64 = "D:\caminho\build\bin"
$env:RANGEARMOR_ENGINE_DIR_LINUX64 = "D:\caminho\build-linux\bin"
```

## Comando de cópia no Linux

No ambiente Linux que contém o runtime já instalado:

```bash
export RANGEARMOR_ENGINE_DIR=/caminho/para/build-linux/bin
python3 release/scripts/get_rangeengine_currentplatform.py --project /caminho/do/projeto/launcher/config.json
```

O diretório informado deve conter `RangeRuntime`.

## Critério de encerramento

A RangeArmor Linux está suportada para o fluxo validado: compilação do launcher,
cópia do runtime, criação de `.tar.xz`, extração fora da árvore de build e
inicialização do jogo pelo pacote. A validação foi feita em Debian/WSL com
Rust/Cargo 1.85 e Mesa/llvmpipe.
