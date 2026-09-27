# Como contribuir

Obrigado pelo interesse na AnastacioEngine. Este guia é curto de propósito: ele aponta para os documentos
que já explicam cada assunto.

## Reportar um bug

Abra uma [issue](https://github.com/AnastacioGames/AnastacioEngine/issues/new/choose) com o modelo
**Relatório de bug**. Ele pede versão, sistema e placa de vídeo, porque boa parte dos bugs de render e de
Cycles depende da GPU e do driver. Se puder, anexe um `.blend` pequeno que reproduza o problema.

## Entender a engine

Leia nesta ordem:

1. [Diagramas da arquitetura](docs/diagramas-arquitetura.md): visão geral desenhada.
2. [Arquitetura](docs/architecture.md): o mesmo em texto, com os caminhos do código.
3. [Roadmap](docs/roadmap.md): o que está aberto. Antes de começar algo grande, confira se já não está
   planejado ou decidido no [relatório de melhorias](relatorio-melhorias-anastacioengine.md).

Para achar código nos arquivos grandes, use os mapas em [docs/code-map-gameengine.md](docs/code-map-gameengine.md).

## Compilar

- **Windows:** [docs/build-notes.md](docs/build-notes.md). Precisa do Visual Studio (MSVC v142), da pasta
  `lib/win64_vc15` baixada à parte e do preset `v142-ninja`. O `ninja` só funciona depois do `vcvars64.bat`
  na mesma chamada.
- **Linux:** [docs/linux-build.md](docs/linux-build.md). O caminho curto é `bash tools/linux/quickstart-editor.sh`.
- **Web e Android:** [docs/web-deploy.md](docs/web-deploy.md) e [docs/build-dirs.md](docs/build-dirs.md).

## Regras que evitam os bugs mais comuns

Resumo do [guia de manutenção](docs/maintenance-guide.md), que traz a lista completa de arquivos por tipo
de mudança:

- **Mudou um `DNA_*.h` ou um header muito usado?** Faça rebuild limpo (`ninja -t clean`). O build
  incremental não percebe e o resultado é crash aleatório.
- **Teste no editor e no player.** Compile e rode `RangeEngine` e `RangeRuntime`: um bug pode aparecer só
  em um deles.
- **O player não tem o editor.** Se o código do jogo chamar uma função do editor, ela precisa de stub em
  `source/source/blenderplayer/bad_level_call_stubs/stubs.c`.
- **Shader do jogo também roda na Web** (GLSL ES 3.00): nada de `float == int` nem recursos só do desktop.
- **Texto novo na interface** precisa de tradução pt_BR, es e ru em
  `source/release/scripts/modules/range_web/translations_*.py`.
- **Opção nova de jogo** passa por painel Python, RNA, DNA, versioning e conversor
  ([diagrama 5](docs/diagramas-arquitetura.md#5-do-editor-para-o-jogo)).

## Como enviar uma mudança

1. Clique em **Fork** no topo desta página. Isso cria uma cópia do repositório na sua conta.
2. Na sua cópia, crie uma branch para a mudança (`git checkout -b corrige-sombra-csm`) e faça os commits nela.
3. Envie a branch para o seu fork (`git push origin corrige-sombra-csm`) e abra um **Pull Request** para o
   `main` deste repositório. Descreva o que muda, como testou e em qual sistema e placa de vídeo.
4. O mantenedor revisa. Pode pedir ajustes: basta fazer novos commits na mesma branch, e o Pull Request se
   atualiza sozinho. Quando aprovado, a mudança entra no `main` com o seu nome como autor.

Um Pull Request por assunto facilita a revisão. Para mudanças grandes, abra antes uma issue para combinar
a abordagem.

## Antes de enviar

1. Build e execução bem-sucedidos. Compilar não basta: rode a cena afetada.
2. Registre a mudança no topo de [docs/changelog.md](docs/changelog.md) e atualize o roadmap se fechou um item.
3. Rode `python tools/check_docs.py`. Ele avisa se algum link, referência `arquivo:linha` ou mapa de código
   ficou desatualizado; `--fix` corrige as linhas dos mapas.
4. Mensagens de commit curtas, em português, no estilo do histórico (`Area: o que mudou`).

## Licença

As regras de licença do projeto e das bibliotecas incluídas estão em [docs/licenca.md](docs/licenca.md).
