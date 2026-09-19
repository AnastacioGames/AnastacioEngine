# AnastacioEngine 0.1

## Pacote portátil para Windows

Distribua uma cópia limpa de `build/bin/` em um único ZIP, preservando esta estrutura:

```text
AnastacioEngine-0.1-windows-x64/
  RangeEngine.exe
  RangeRuntime.exe
  *.dll
  blender.crt/
    blender.crt.manifest
    *.dll
  2.79/
    datafiles/
    scripts/
```

Não distribua apenas `2.79/`: executáveis e DLLs ficam no diretório pai. `build/bin/` é a instalação
portátil real gerada pelo projeto; a pasta `install/` da raiz pode estar obsoleta. Não compacte a pasta
de build literalmente: exclua logs, arquivos `.pdb`/`.map`/`.lib`/`.exp`, ferramentas internas
(`datatoc`, `makesdna`, `makesrna`), cenas de teste, backups e configurações locais do ImGui.

**Runtime do Visual C++ (pasta `blender.crt/`):** `RangeEngine.exe`/`RangeRuntime.exe` têm um manifesto
embutido que declara dependência de uma assembly privada chamada `blender.crt` (mecanismo herdado do
Blender/UPBGE para versionar o runtime do VC++ via side-by-side). Essa assembly só é resolvida se existir
uma **subpasta `blender.crt/`** ao lado do `.exe`, contendo o `blender.crt.manifest` gerado pelo CMake
(`platform_win32_bundle_crt.cmake`) e os DLLs do runtime (`vcruntime140.dll`, `vcruntime140_1.dll`,
`msvcp140.dll`, `msvcp140_1.dll`, `msvcp140_2.dll`, `msvcp140_atomic_wait.dll`,
`msvcp140_codecvt_ids.dll`, `concrt140.dll`, `vcomp140.dll` e os `api-ms-win-*.dll` correspondentes,
todos já presentes em `build/bin/blender.crt/` após o build). **Copiar apenas os DLLs soltos ao lado do
`.exe` (sem a subpasta e sem o `.manifest`) não resolve a dependência** e produz exatamente o erro "Falha
na inicialização do aplicativo devido à configuração lado a lado incorreta" em uma instalação limpa do
Windows, mesmo com os DLLs presentes no diretório. `ucrtbase.dll` fica fora da pasta `blender.crt/`, solto
junto do `.exe` (não pode entrar no manifesto — ver comentário em `platform_win32_bundle_crt.cmake`).
Antes de publicar, valide em uma máquina sem o Visual Studio ou em uma instalação limpa, extraindo o ZIP
de fato (não apenas rodando a partir de `build/bin/`).

No GitHub, mantenha o código-fonte no repositório e anexe o ZIP à Release como
`AnastacioEngine-0.1-windows-x64.zip`. O diretório de build permanece ignorado pelo Git.

## Artefatos de Release em `build/dist/`

`build/dist/` é a área local de entrega. Ela é ignorada pelo Git e contém somente arquivos finais
prontos para anexar a uma GitHub Release; **nunca** deve ser commitada como código-fonte.

A partir da versão `0.3.0` (exemplo abaixo na `0.4.0`), os artefatos Windows são:

```text
build/dist/
  AnastacioEngine-0.3.0-windows-x64.zip
  RangeArmor-0.3.0-windows-x64.zip
  SHA256SUMS.txt
```

- `AnastacioEngine-<versao>-windows-x64.zip`: editor, runtime, DLLs, `2.79/` e licenças necessárias.
- `RangeArmor-<versao>-windows-x64.zip`: **asset separado**, não mais embutido no zip da engine — o
  painel, launcher, scripts de exportação e a licença MIT da ferramenta (© BGEmpire Studio). Publicado na
  mesma página/release do GitHub que a engine, mas como arquivo distinto, já que o código-fonte da
  RangeArmor não está neste repositório (`tools/RangeArmor-master/` é ignorado pelo Git). O painel (GUI,
  Godot) só roda no Windows; não existe nem é necessário um pacote `RangeArmor-<versao>-linux-x64`
  separado, porque o painel já exporta jogos para Linux x86_64 embutindo o launcher Rust compilado para
  `x86_64-unknown-linux-gnu` (ver `docs/rangearmor-modernization-plan.md`).
- `SHA256SUMS.txt`: hashes SHA-256 de todos os artefatos da release (Windows e Linux); publicar junto dos
  arquivos para permitir verificação de integridade por quem baixar.

Convenção anterior (até `0.2.0`): um único
`AnastacioEngine-<versao>-windows-x64-with-RangeArmor.zip` com a RangeArmor embutida. Descontinuada a
partir de `0.3.0` em favor do asset separado acima.

**Não copie `concrt140.dll`, `msvcp140*.dll`, `vcruntime140.dll` nem `vccorlib140.dll` soltos ao lado do `.exe`**: além de não resolverem a dependência, com eles presentes o `RangeRuntime.exe` encerra com código 11 ao abrir um `.range` (o `RangeEngine.exe` continua abrindo). A `0.3.0` foi publicada assim; a `0.4.0` usa só `blender.crt/` + `ucrtbase.dll`.

A criação dos ZIPs deve preservar o build original. Primeiro monte as pastas descartáveis em
`build/release-staging/`, valide que `RangeEngine.exe`, `RangeRuntime.exe` e, no pacote ampliado, o
`RangeArmor Panel.exe` e `release/launcher/Launcher.exe` existem. Depois compacte para `build/dist/`
e gere os hashes. Antes do upload, execute os binários a partir de uma cópia extraída do ZIP.

Quando disponível, o atlas legado da UPBGE deve ficar em:

```text
2.79/datafiles/icons/upbge_legacy/
  blender_icons16.png
  blender_icons32.png
```

Antes de publicar, confirme que `RangeEngine.exe` e `RangeRuntime.exe` iniciam a partir de uma cópia limpa
do pacote e que os scripts, datafiles e DLLs necessários continuam presentes.

## Linux x86_64

Publicado a partir da versão `0.3.0` como `AnastacioEngine-<versao>-linux-x64.tar.gz`, com o conteúdo
completo de `build-linux/bin/` e `SHA256SUMS.txt` na mesma release. Validado em máquina Linux limpa (fora
do WSL) antes da publicação — ver `docs/changelog.md` (entradas de 2026-09-15).
