# Efeitos pré-calculados

Branch de trabalho: `feat/efeitos-precalculados-sombras`. Entregas pequenas, com validação antes de
avançar para a próxima: Lua, estrelas/constelações e lens flare. O reaproveitamento de sombras é
uma investigação separada; não introduzir atraso nas sombras junto com a preparação de texturas.

## Primeira etapa: superfície da Lua

Em World > Sky > Night, **Precomputed Surface** seleciona uma textura de 512 × 512 para as manchas
e crateras da Lua visual. Desligada por padrão; projetos antigos continuam no caminho procedural.
Posição, tamanho, brilho, contorno e halo continuam calculados durante a execução. A atmosfera e as
estrelas não são substituídas. A opção atende o World legado, sem nodes, nos céus Procedural e Atmospheric.

O recurso é gerado na CPU na primeira utilização, compartilhado pelos mundos e liberado no encerramento
da GPU. Não há geração por frame. A textura RGBA8 ocupa aproximadamente 1 MiB de GPU, sem mipmaps;
o buffer temporário de geração usa 4 MiB e é liberado depois do upload. Falha de criação da textura
preserva o caminho procedural. O checkbox persiste no `.range`, sem alteração do layout da struct World.

Esta etapa **não grava a textura no `.cooked`**. Ela valida a substituição dos cálculos de superfície antes
de ampliar o armazenamento. CPU e GPU podem produzir ruído diferente pela precisão do seno, e a textura
tem resolução finita; não prometer imagem idêntica. Não há ganho de desempenho validado em iGPU.

Gerador de comparação: `tools/debug/cenas/criar_cena_lua_precalculada.py`. Gera quatro arquivos, combinando
os dois tipos de céu e os dois modos de superfície. Usa uma Lua grande para expor diferenças. Com a
variável `ANASTACIO_MOON_RESULT` definida para um arquivo JSON, o player registra intervalos entre ticks
após aquecimento de 2 segundos e encerra após 8 segundos. Sem a variável, permanece aberto para inspeção.
Esses intervalos são uma medida de throughput do cenário, não um tempo exclusivo da Lua ou da GPU.

Evidências locais: `artifacts/moon-precomputed/`; build em `artifacts/moon-precomputed-build.log`.

## Próximas etapas, ainda não implementadas

- Validação visual da Lua pelo usuário, em movimento e em tamanhos diferentes.
- A/B repetido, incluindo iGPU: efeito/frame, carregamento, RAM/VRAM e aparência.
- Persistência dos recursos: chave com versão da fórmula, resolução, formato e parâmetros que afetam
  o conteúdo; gravação atômica, validação de tamanho e fallback se ausente/inválido. Separar texturas
  portáveis de binários de shaders específicos de GPU/driver. Não gravar posição/brilho no conteúdo
  quando só afetam a composição dinâmica.
- Estrelas: mapa na esfera celeste com rotação dinâmica, mantendo variantes de qualidade e estilo;
  avaliar resolução, estrelas pequenas, costuras, HDR e cintilação antes de escolher projeção/formato.
- Lens flare: pré-calcular componentes, mantendo ocultação e posição atuais; decidir como preservar
  animação, cor e escala sem congelar o efeito completo.
- Integrar exportação e a opção de preparação individual por efeito somente quando os respectivos
  caminhos de render estiverem validados. Não mostrar checkbox de um efeito ainda não implementado.

## Revisao da primeira etapa

A revisao corrigiu a transformacao da direcao de visao no ceu pre-calculado: espelhamento abaixo do horizonte no Procedural e ajuste de roughness no Atmospheric. A criacao do caminho pre-calculado agora independe do estado inicial de visibilidade da Lua, preservando o uniform dinamico de ativacao. Testes adicionais cobrem Lua inicialmente desligada e camera abaixo do horizonte; logs em `artifacts/moon-precomputed/`.

Moon Size agora aceita 0.001 a 1.0; a cena de comparacao usa 0.1. O valor padrao e os valores salvos permanecem iguais. A faixa vale para os dois modos; texturas grandes na tela podem revelar sua resolucao finita.
