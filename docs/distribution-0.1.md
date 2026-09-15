# AnastacioEngine 0.1

## Pacote portátil para Windows

Distribua uma cópia limpa de `build/bin/` em um único ZIP, preservando esta estrutura:

```text
AnastacioEngine-0.1-windows-x64/
  RangeEngine.exe
  RangeRuntime.exe
  *.dll
  2.79/
    datafiles/
    scripts/
```

Não distribua apenas `2.79/`: executáveis e DLLs ficam no diretório pai. `build/bin/` é a instalação
portátil real gerada pelo projeto; a pasta `install/` da raiz pode estar obsoleta. Não compacte a pasta
de build literalmente: exclua logs, arquivos `.pdb`/`.map`/`.lib`/`.exp`, ferramentas internas
(`datatoc`, `makesdna`, `makesrna`), cenas de teste, backups e configurações locais do ImGui.

**Runtime do Visual C++:** a máquina de desenvolvimento pode ter o runtime instalado e esconder uma
dependência ausente no pacote. Junto de `RangeEngine.exe` e `RangeRuntime.exe`, inclua as DLLs x64 do
Microsoft Visual C++ Redistributable usadas no build: `concrt140.dll`, `msvcp140*.dll`, `vccorlib140.dll`
e `vcruntime140*.dll`. Sem elas, uma instalação limpa do Windows pode mostrar o erro de configuração
"lado a lado" ao abrir a engine. Antes de publicar, valide em uma máquina sem o Visual Studio ou em uma
instalação limpa.

No GitHub, mantenha o código-fonte no repositório e anexe o ZIP à Release como
`AnastacioEngine-0.1-windows-x64.zip`. O diretório de build permanece ignorado pelo Git.

## Artefatos de Release em `build/dist/`

`build/dist/` é a área local de entrega. Ela é ignorada pelo Git e contém somente arquivos finais
prontos para anexar a uma GitHub Release; **nunca** deve ser commitada como código-fonte.

A partir da versão `0.3.0`, os artefatos Windows são:

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
  RangeArmor não está neste repositório (`tools/RangeArmor-master/` é ignorado pelo Git).
- `SHA256SUMS.txt`: hashes SHA-256 de todos os artefatos da release (Windows e Linux); publicar junto dos
  arquivos para permitir verificação de integridade por quem baixar.

Convenção anterior (até `0.2.0`): um único
`AnastacioEngine-<versao>-windows-x64-with-RangeArmor.zip` com a RangeArmor embutida. Descontinuada a
partir de `0.3.0` em favor do asset separado acima.

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

Publicado a partir da versão `0.3.0` como `AnastacioEngine-0.3.0-linux-x64.tar.gz`, com o conteúdo
completo de `build-linux/bin/` e `SHA256SUMS.txt` na mesma release. Validado em máquina Linux limpa (fora
do WSL) antes da publicação — ver `docs/changelog.md` (entradas de 2026-09-15).
