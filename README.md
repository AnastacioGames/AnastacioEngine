# AnastacioEngine

Fork em C++ da Range Engine 1.6 Rev1, derivada da UPBGE 0.2.5b e do Blender 2.79.
O projeto concentra-se em performance, renderização e ferramentas de runtime.

## Começando

- [Índice da documentação](docs/README.md)
- [Roadmap atual](docs/roadmap.md)
- [Arquitetura](docs/architecture.md)
- [Build no Windows](docs/build-notes.md)
- [Build experimental no Linux](docs/linux-build.md)
- [Histórico técnico](docs/changelog.md)
- [Licença](docs/licenca.md)

Para agentes de código, as regras operacionais estão em [AGENTS.md](AGENTS.md).

## Download

A versão mais recente publicada é a `0.4.0`, disponível em
[Releases → v0.4.0](https://github.com/AnastacioGames/AnastacioEngine/releases/tag/v0.4.0):

- `AnastacioEngine-0.4.0-windows-x64.zip`: editor e runtime para Windows x64;
- `AnastacioEngine-0.4.0-linux-x64.tar.gz`: editor e runtime para Linux x86_64 (**ainda será anexado à release**; enquanto isso, o Linux 0.3.0 continua em [v0.3.0](https://github.com/AnastacioGames/AnastacioEngine/releases/tag/v0.3.0));
- `RangeArmor-0.4.0-windows-x64.zip`: ferramenta de empacotamento/exportação RangeArmor, publicada como
  asset separado (código-fonte de terceiros, não incluído neste repositório). O painel (GUI) roda somente
  no Windows, mas exporta jogos para **Windows e Linux x86_64**: o launcher Rust já é compilado para
  ambas as plataformas e o painel embute o binário Linux automaticamente no pacote `.tar.xz` quando
  `build-linux/bin` está disponível — não há (nem é necessário) um `RangeArmor Panel` separado para Linux;
- `SHA256SUMS.txt`: hashes para verificar a integridade dos arquivos acima.

## Exportação para Web (em desenvolvimento)

O perfil Web (Range) e o botão **Exportar Web** já existem no editor, mas a exportação para o navegador **ainda não está finalizada**: há validações e comportamentos em aberto (por exemplo, o normal map `.dds` aparece diferente do desktop) e o recurso não deve ser usado para projetos de produção. O estado atual está em [docs/roadmap.md](docs/roadmap.md).

## Executáveis

O build gera os artefatos atuais em `build/bin/` (Windows) e `build-linux/bin/` (Linux):

- `RangeEngine.exe`: editor;
- `RangeRuntime.exe`: player standalone para arquivos `.range`.

O Linux x86_64 já é suportado e validado nativamente (fora do WSL) a partir da versão `0.3.0` — ver
[docs/linux-build.md](docs/linux-build.md) e [docs/changelog.md](docs/changelog.md).

Consulte `docs/build-notes.md` antes de compilar. A pasta `install/` da raiz pode ser uma cópia antiga e
não deve ser usada para validar mudanças.
