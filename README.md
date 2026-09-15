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

## Executáveis

O build gera os artefatos atuais em `build/bin/`:

- `RangeEngine.exe`: editor;
- `RangeRuntime.exe`: player standalone para arquivos `.range`.

O suporte a Linux x86_64 esta em preparacao: existe um preset isolado para o `RangeRuntime`, mas ainda nao
ha build ou pacote Linux oficialmente validado.

Consulte `docs/build-notes.md` antes de compilar. A pasta `install/` da raiz pode ser uma cópia antiga e
não deve ser usada para validar mudanças.
