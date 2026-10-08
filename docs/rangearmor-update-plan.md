# Plano de atualização do RangeArmor

Estado em 2026-10-08: integração inicial do cooking implementada; build Windows e testes
de segurança passaram. Validação do pacote extraído registrada abaixo; jogo real, Linux,
outra GPU e migração ampla de runtimes permanecem pendentes.
Complementa o [plano de renomeação](executable-rename-plan.md). A atualização deve acompanhar
os contratos atuais da engine, incluindo cooking; não se limita à troca de nome do editor.

## Base de trabalho

Recuperar em diretório isolado o fonte local do commit `69df19d9`, em
`tools/RangeArmor-master/RangeArmor-master/`, e comparar com a instalação distribuída.
O upstream é <https://github.com/rangeengine/RangeArmor>; preservar as adaptações locais
antes de incorporar mudanças externas. Conferir quais componentes de interface realmente
estão em uso: o snapshot contém painel Godot e fonte de GUI Rust.

Fonte recuperado nesta sessão em `tools/rangearmor/`, fora do caminho ignorado, para revisão
e versionamento. Os scripts instalados diferiam do snapshot; os originais foram preservados
no backup em `build/safety-backups/rangearmor-20261008-093834/`.

## Integração inicial executada

- Cook manual grava primeiro em diretório temporário; falha ou timeout mantém o cache anterior.
  Sucesso sem resultados remove o cache antigo, evitando reutilização involuntária.
- Exportador de release cozinha o `MainFile` protegido e prepara seu companheiro antes de copiar
  os dados. A preparação exige runtime do host; o export de um clique fornece o runtime instalado.
- Opção `Cook before export` no export de um clique, ligada por padrão. Desligada, passa
  `--no-cook` ao backend, que exclui `.cooked` da entrega sem apagar os caches de autoria.
  O painel independente cozinha por padrão; a opção sem cache também existe na CLI.
- Exportação pela engine verifica o resultado do save protegido e da gravação do JSON; não
  continua silenciosamente usando um snapshot antigo quando essa etapa falha.
- Entrega montada em staging. A entrega anterior permanece em pasta `.previous-*` após sucesso;
  falhas de preparo não a removem. ZIP usa caminhos com `/`; o formato é escolhido pelo alvo.
- Caminho do painel usa o diretório do editor, sem depender do comprimento de `RangeEngine.exe`.
- Launcher Windows instalado estava obsoleto e falhou no teste inicial. O fonte recuperado
  compilou e seus dois testes passaram. O template atualizado está instalado; hash do template
  antigo permite usar o novo na entrega de projetos legados, sem trocar o arquivo original
  do projeto nem launchers personalizados.
- Painel Rust posteriormente recompilado, com tratamento de exit code e logotipo ampliado.
  Exportação e falha pela GUI passaram em cena controlada, conforme as evidências abaixo.

Ainda não implementado: atualização automática de todos
os runtimes dos projetos antigos, mudança da marca da ferramenta, formato novo de cooking e caches
futuros de meshes/texturas. A renomeação dos executáveis continua no plano separado.

Validação Windows: sete testes Python de segurança, dois testes Rust, build do editor/runtime
e build release do launcher passaram. Cook e atualização do preset executados no editor.
ZIP gerado pelos scripts instalados foi extraído em outra pasta; o launcher retornou 0 e
o jogo de teste gravou um marcador confirmando execução de sua lógica. O pacote continha
o `.cooked` companheiro e `blender.crt/`. Isso não substitui a validação do jogo real.

## Achados sobre cooking

### Continuação: cópia dos runtimes (2026-10-08)

O script instalado ainda era legado: deduzia a instalação cortando o caminho do Python,
copiava uma lista fixa de DLLs e omitia `blender.crt/`. Foi substituído pelo script do
fonte recuperado, com backup em `build/safety-backups/rangearmor-runtime-copy-*/`.
Agora a cópia preserva a instalação do runtime e suas dependências, exclui os executáveis
dos editores antigo/novo e prepara tudo em staging antes da substituição. Runtime anterior
fica em `Windows64.previous-*` ou `Linux64.previous-*`; falha de cópia mantém o destino.
Destinos fora do projeto ou sobrepostos à origem são recusados.

Oito testes Python passaram, incluindo cópia real de uma instalação simulada em caminho
com espaço e acento, preservação de CRT/Python/DLL, exclusão dos editores, falha de cópia
e retenção da versão anterior. Não houve migração automática de projetos existentes.
A cópia da instalação completa passou na continuação abaixo; o botão do painel no jogo
real ainda exige validação.

### Continuação: instalação real e execução (2026-10-08)

O script instalado copiou `build/bin/` para um projeto temporário com espaço e acento no
caminho. CRT, Python e player foram conferidos, sem os executáveis dos editores. O preparador
`prepare_cooked.py` instalado utilizou esse player para gerar `Game.cooked` (`ANACOOK2`).
Depois o player copiado abriu `Game.rasec`, carregou/usou o hull preparado, reutilizou
shaders e executou a lógica de encerramento da cena (`EXTRACTED_GAME_VALIDATED`).
Evidência local: `build/rangearmor-real-copy-validation.txt`; script de execução em
`build/validate_rangearmor_real_copy.py`. É uma cena controlada, não validação visual do jogo real.

Limitação observada: passar diretamente um destino com acento em `ANASTACIO_COOK` ao runtime
deixou apenas `.cooked.tmp`, com aviso de caminho não UTF no log. O preparador da RangeArmor
passou usando seu destino temporário e cópia Python para o projeto. Essa limitação nativa
não foi corrigida nesta etapa; diretórios temporários com caracteres fora de ASCII ainda
precisam de teste próprio. Não foram alterados projetos reais nem recompilado C++.

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

Continuação em 2026-10-08: script de cópia agora retorna código de erro para projeto
inválido, runtime ausente, plataforma não suportada ou falha na cópia. Antes ele imprimia
o diagnóstico, mas retornava sucesso ao chamador. Nove testes passaram, incluindo CLI
real com runtime ausente, recusa de Windows32 e falha injetada na publicação do staging,
com restauração do runtime anterior. Script instalado atualizado com backup em
`build/safety-backups/rangearmor-copy-errors-*/`; execução instalada sem config retornou 1.
O painel fonte consulta o retorno de `OS.execute`; sua interação visual permanece pendente.

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

Continuação em 2026-10-08: painel instalado iniciou, criou janela com título
`RangeArmor Panel` e respondeu ao fechamento normal, retornando 0. Evidência em
`build/rangearmor-panel-startup.json`; execução em `build/validate_rangearmor_panel.py`.
O painel atual é Rust/eframe; a GUI Godot está em `build/bin/rangearmor/godot_backup/`.
O teste inicial por `WaitForInputIdle` não serviu para esse executável; o teste conclusivo
enumerou a janela do processo e enviou fechamento à janela correta.
Nesse teste inicial não houve interação com botões; a validação posterior está abaixo.

A auditoria do fonte Rust mostrou que `runner.rs` usava somente mensagens `X ` para
detectar falhas. Corrigido nesta continuação: resultado considera também exit code e
espera a leitura de stdout/stderr antes de anunciar conclusão. Falha sem prefixo agora
é reconhecida, preservando o diagnóstico dos scripts legados.

26 testes Rust passaram, incluindo subprocesso que retorna 7 sem prefixo de erro,
streaming dos logs, projetos legados e campos de configuração. Rust 1.92 instalado
não satisfazia as dependências; toolchain 1.95.0 instalado separadamente, mantendo
o padrão da máquina. Testes e build release passaram com `cargo +1.95.0`, vcvars64
e VSLANG no mesmo processo. Build teve avisos de campos não lidos em `project.rs`.

Painel novo iniciou/fechou com exit 0 antes e depois da instalação. Hash SHA256 do
instalado confere com o compilado. Backup do painel anterior em
`build/safety-backups/rangearmor-panel-20261008-104444/`. Não foi publicado pacote.
Teste posterior da interface: projeto temporário abriu pelo botão Open Project e seletor
de pasta do Windows. Botão Export Windows64 gerou `.cooked` e entrega, com confirmação
de sucesso no painel. Launcher dessa entrega executou a lógica da cena e confirmou uso
do hull preparado. Segundo export com MainFile inexistente exibiu falha e preservou a
entrega anterior. Controles acionados por UIAutomation/BM_CLICK, não por chamada direta
do backend. Evidências em `build/armor-gui-export-failure.json` e
`build/armor-gui-delivery-runtime.log`; scripts de teste em `build/armor_gui_uia.ps1`,
`build/test_armor_gui.py` e `build/validate_armor_gui_delivery.py`.

Cabeçalho da tela inicial: logotipo passa a ocupar 280 × 84 pontos, preservando proporção,
em vez do limite de altura anterior que deixava a marca pequena. Build release passou e
painel instalado foi aberto para conferir o resultado. Imagem em
`build/rangearmor-logo-validation.png`; painel anterior preservado em
`build/safety-backups/rangearmor-logo-20261008-105253/`.

Preferências/lista de recentes do painel foram restauradas byte a byte após o teste.
Nenhum projeto real foi alterado. Export pela GUI passou em cena controlada; jogo real,
LibLoad, Linux/outra GPU e APK em aparelho continuam pendentes. Export comprimido pela
GUI passou na continuação abaixo.

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

### Confirmação manual posterior — 2026-10-08

Usuário confirmou que o jogo rodou e autorizou continuação. Essa confirmação não
identifica pacote/plataforma nem comprova tempo de carga, cache, LibLoad ou outra GPU;
essas verificações específicas permanecem abertas.

### Export comprimido pela GUI e documentação — 2026-10-08

Opção `ExportCompress` ativada somente no projeto temporário. Botão Export Windows64
gerou ZIP e mostrou sucesso; entrega anterior preservada. ZIP com 5.410 arquivos,
caminhos `/` e integridade CRC verificada. Extraído em pasta com espaços fora do build,
launcher retornou 0; log confirmou execução da cena e uso do hull preparado.
`.cooked` ANACOOK2 e assembly `blender.crt/` presentes; editor não incluído.

Evidências: `build/armor-gui-zip-success.json`, `build/armor-gui-zip-validation.json` e
`build/armor-gui-zip-runtime.log`; verificador em `build/validate_armor_gui_zip.py`.
ZIP tem 701.214.344 bytes: runtime de desenvolvimento inclui símbolos e outros arquivos
que devem ser filtrados no staging de um release público. Não houve publicação.
Preferências do painel restauradas byte a byte; projeto real não alterado.

Suíte completa Web/Android: 132 testes passaram. Segurança/cópia da RangeArmor: nove
testes passaram. `check_docs.py --fix` atualizou 91 referências/contagens do mapa;
checagem posterior retornou zero erros e zero avisos. O verificador local do ZIP usou
hash SHA256 por streaming para ser compatível com Python 3.10.

## Integração com AnastacioRuntime.exe — 2026-10-08

Player Windows renomeado por autorização do usuário. Engine, painel, launcher e scripts
preferem o nome novo nos projetos novos; caminhos antigos continuam aceitos quando o
executável equivalente está na mesma pasta. Caminhos existentes e personalizados têm prioridade.
O config original do projeto não é alterado pela exportação: a entrega recebe o nome
real do player copiado. Templates antigos conhecidos por SHA256 usam o launcher atualizado
no Run/Export; personalizados permanecem intactos. Instalação portátil encontrada pela
posição dos scripts, sem depender de variáveis de ambiente ou diretórios de build.

Builds editor/player, launcher e painel passaram; 12 testes Python, três testes do launcher,
26 testes do painel em release e 132 testes Web/Android passaram. Cook, standalone e export
nativo pelo editor executaram a cena e usaram hull preparado. Pacotes Windows atualizados
em `build/dist/validation-20261008-113829/`; evidência de extração/execução em
`build/current-windows-packages.json`. Escopo e limites na seção 14 do
[plano de migração](executable-rename-plan.md#14-player-windows-renomeado--2026-10-08).
Marca RangeArmor e nomes Linux/Web/Android preservados. Usuário confirmou funcionamento
do jogo após a migração Windows. Windows limpo, Linux/outra GPU e aparelho Android ainda
precisam de validação própria; esses testes não impedem a conclusão da implementação Windows.
