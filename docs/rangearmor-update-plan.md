# Plano de atualização do RangeArmor

Estado em 2026-10-08: auditoria estática inicial e plano; implementação e execução pendentes.
Complementa o [plano de renomeação](executable-rename-plan.md). A atualização deve acompanhar
os contratos atuais da engine, incluindo cooking; não se limita à troca de nome do editor.

## Base de trabalho

Recuperar em diretório isolado o fonte local do commit `69df19d9`, em
`tools/RangeArmor-master/RangeArmor-master/`, e comparar com a instalação distribuída.
O upstream é <https://github.com/rangeengine/RangeArmor>; preservar as adaptações locais
antes de incorporar mudanças externas. Conferir quais componentes de interface realmente
estão em uso: o snapshot contém painel Godot e fonte de GUI Rust.

## Achados sobre cooking

- `source/release/scripts/startup/bl_operators/anastacio_cook.py` gera o arquivo ao lado do
  projeto, com extensão `.cooked`, usando o runtime e `ANASTACIO_COOK`.
- `source/source/gameengine/Physics/Bullet/CcdCookedData.cpp` substitui a extensão do arquivo
  principal por `.cooked` para localizar o cache. Portanto `data/Jogo.rasec` precisa do
  companheiro `data/Jogo.cooked`; não do nome do launcher ou do editor.
- `source/release/scripts/addons/game_engine_save_as_runtime.py` já copia o `.cooked` no
  Export Game e remove o destino antigo quando não há fonte. Esse fluxo é diferente do RangeArmor.
- A integração RangeArmor em `source/release/scripts/startup/bl_operators/wm.py` regenera o
  `.rasec`, mas não contém tratamento explícito de `.cooked` na inspeção atual.
- No snapshot local, `release/scripts/build_release.py` copia `data/` inteira. Assim um
  `.cooked` já presente acompanha o jogo, mas essa cópia não garante preparo nem atualização.
  `build_data.py` também percorre arquivos, porém o próprio build de release marca o antigo
  `DataFile` como descontinuado; não presumir que compressão seja o fluxo ativo.
- O cache do jogo exportado é somente leitura; shaders específicos da GPU usam cache do
  usuário. O roadmap registra aquecimento na primeira abertura e tela de preparação pendente.

## Alterações planejadas

1. **Recuperar e identificar a versão efetiva.** Conferir painel, scripts, launcher compilado
   e templates instalados; registrar divergências antes de atualizar.
2. **Fechar o contrato do cooking com a engine em desenvolvimento.** Definir arquivos gerados,
   nomes, compatibilidade do formato, invalidação e dependências. Hoje o cabeçalho compara
   `sizeof(btScalar)`; não tratar isso como versionamento completo entre releases ou plataformas.
   Normais, buffers de malha e texturas futuras só entram quando implementados e validados.
3. **Preparar dados na exportação.** Integrar opção de cozinhar antes de exportar e opção de
   exportar sem cache, com resultado e erros visíveis. Garantir que o cache corresponda ao estado
   exportado, inclusive alterações ainda não salvas. Não considerar existência ou data do arquivo
   prova suficiente de que o conteúdo está atualizado. Evitar publicar cache antigo após falha.
4. **Empacotar os companheiros corretos.** Manter `.rasec` e `.cooked` com mesmo nome-base em
   `data/`, preservar caminhos de bibliotecas externas e conferir o comportamento real do LibLoad.
   Não presumir que cada biblioteca tem cache separado: o código atual abre o cache pelo principal.
   Conferir também o painel independente, além do Export de um clique da engine.
5. **Atualizar runtimes e launchers.** Conferir seleção Windows/Linux, cópia da instalação completa,
   bibliotecas e templates. Adaptar descoberta ao novo nome do editor; os caminhos do player
   continuam configuráveis. Atualizar projetos antigos com migração explícita, preservando scripts
   personalizados. Não distribuir caches pessoais de shaders junto com a engine.
6. **Verificar os demais contratos recentes.** Bibliotecas externas, scripts e versão Python,
   componentes nativos opcionais de Steam/multiplayer, assets e configuração de inicialização.
   Esta é uma lista de auditoria, não uma afirmação de que todos exigem alteração.
7. **Validar a distribuição.** Comparar o jogo exportado pelo painel e pelo botão da engine,
   em projeto novo e existente, com caminhos contendo espaços e acentos. Windows e Linux
   precisam de validação própria; Web/Android continuam com seus exportadores e contratos.

## Critérios de aceite

- Pacote extraído inicia o jogo com `.rasec` e seu `.cooked`, sem depender do diretório de desenvolvimento.
- Comparação de logs e tempo de carga confirma uso do cache e benefício, preservando o comportamento.
- Sem cache, cache incompatível e atualização de conteúdo têm comportamento previsível; o fallback
  continua funcionando e nenhuma exportação anuncia sucesso após erro de preparação.
- Outra GPU/driver consegue preparar seus shaders e iniciar; segunda abertura reutiliza o cache local.
  O ganho da máquina de autoria não é prometido para a primeira abertura de todas as GPUs.
- Instalação sem permissão de escrita permite cache no diretório do usuário. Atualizações do jogo
  não reutilizam shaders incompatíveis nem exigem escrita em `data/`.
- LibLoad e assets externos funcionam no jogo real; tempos de extração/inicialização do launcher
  são medidos separadamente do tempo de carga da engine.
- Antes de empacotar release Windows, ler `distribution-0.1.md` inteiro e manter `blender.crt/`.

Executar em peças pequenas: primeiro contrato e preparo dos arquivos, depois painel/scripts,
depois launcher apenas se necessário. O cooking ainda está em desenvolvimento; decisões de
formato permanecem pendentes até a consolidação dessa frente.
