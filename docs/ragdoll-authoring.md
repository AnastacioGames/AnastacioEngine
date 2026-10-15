# Anastacio Ragdoll — autoria de caixas

Editor de corpos do novo ragdoll. O ragdoll atual do RolimaRacer continua nos seus
dois scripts corrigidos e validados. A versão 0.3 também prepara física e anexa o
[componente comum](ragdoll-runtime.md), com retorno livre/âncora e NPC permanente.

O addon antigo Easy Ragdoll foi retirado da distribuição por solicitação do usuário;
os componentes externos já usados no RolimaRacer foram preservados. O novo addon é
Python e não exige mudanças C++. O componente atende jogadores e NPCs, com recuperação
automática opcional e tempo configurável, tanto livre como em âncora.

## Usar no editor

1. Em User Preferences > Add-ons, procure **Anastacio Ragdoll** e habilite.
2. Selecione uma armature local, fora do Edit Mode. Abra Properties > Physics >
   **Anastacio Ragdoll — Autoria**.
3. Clique **Ler ossos / atualizar lista** e ative **Mostrar prévia**.
4. Marque os ossos que precisam de corpo. Controles sem deformação começam excluídos.
   O botão **Usar somente ossos selecionados** substitui a seleção da lista.
5. Selecione uma linha e ajuste largura X, profundidade Z, comprimento relativo ao
   osso, deslocamento e rotação locais. A linha ativa aparece laranja; demais caixas, ciano.
6. **Gerar / atualizar corpos** materializa as caixas. **Remover corpos gerados**
   apaga apenas a geração desta ferramenta. Ambas aceitam Desfazer/Refazer.

Prévia e geração usam a pose de repouso, mesmo com animação/pose ativa. Os campos
medem unidades locais da armature; escala mundial uniforme é incorporada. A prévia
não cria objetos, não modifica pose e pode ser desligada a qualquer momento.
Salvar o projeto preserva os campos; o addon precisa estar habilitado ao reabrir.

Selecione a armature em **Object Mode**: não é necessário selecionar um osso para
abrir o painel. Selecionar um corpo ou empty gerado também mostra as opções do seu
rig. A escolha **Rest Position / Pose Position** no painel controla a apresentação
do esqueleto; os cubos continuam definidos no repouso. Ajuste as dimensões nos campos
do addon. Edit Mode modifica o esqueleto, e edição direta das caixas será substituída
pela próxima geração.

## Organização no Outliner

Cada armature recebe uma collection `Ragdoll - <armature>`, dentro da collection da
armature quando houver. Corpos e empties ficam nessa pasta; o parenting dos pivôs
continua sendo o corpo correspondente. A armature não é movida nem recebe um novo pai.

Atualizar reutiliza a pasta, inclusive se ela foi renomeada. Os vínculos usam a
armature e o UID da collection na cena, sem depender do nome. Uma cópia de rig ganha
sua própria pasta depois de resolvidos os vínculos copiados. Remover limpa a pasta
quando vazia; objetos e subpastas do usuário são preservados. Se a pasta foi apagada
manualmente, a próxima geração cria outra. Arquivos da primeira versão são organizados
ao usar **Gerar / atualizar corpos**.

O novo exemplo em `debug-logs/ragdoll-collections-20261014/autoria-ragdoll.range`
mantém a constraint externa de regressão desativada para não deslocar o Root ao
entrar em Pose Mode. O primeiro exemplo tinha essa constraint ativa intencionalmente
para testar sua preservação; isso não é uma transformação aplicada pelo addon.

## Contrato desta versão

- Geração cria caixas e pivôs com referência de propriedade para a armature e chave
  por osso. Renomear esses objetos não perde a propriedade. Atualizar substitui a
  geração anterior; edite a geometria pelos campos, pois edição direta da malha será substituída.
- Constraints novas têm influência zero. A geração inicial de autoria tem `NO_COLLISION`.
  **Preparar física + componente** cria rigid bodies e cone-twist e anexa o runtime;
  depois disso atualizar preserva a execução. Corpos ficam em wireframe e não renderizam.
- Falha durante construção descarta os objetos novos e mantém a geração anterior.
  Não reutiliza uma constraint `Copy Transforms` do usuário.
- Atualização/remoção recusam filhos e referências externas de constraints/modificadores
  conhecidos que dependam dos corpos. Não use os objetos gerenciados como suporte
  para outras partes do jogo. Migração de referências arbitrárias ainda não existe.
- Rigs com Easy Ragdoll existente não são migrados. Para experimentar use uma
  armature de teste limpa. Cópias de rigs com vínculos para corpos do original
  precisam ter esses vínculos copiados removidos antes de gerar sua própria cadeia.
- Escala não uniforme, espelhamento, cisalhamento, osso ausente ou sem comprimento
  produzem erro explícito. Aplique transformações em uma cópia apropriada do rig.
  Após renomear um osso, desmarque a entrada antiga e leia os ossos novamente.
- Há três presets, massa distribuída, limites e damping por osso no painel. Ainda faltam
  visualização de eixos/limites articulares, sobreposição, cápsulas e blend de recuperação.
  Não existe portabilidade Web validada nesta etapa.

## Fonte e verificação

Fonte: `source/release/scripts/addons/anastacio_ragdoll.py`. A cópia de uso atual fica
em `build/bin/2.79/scripts/addons/`; o install da engine distribui o fonte.

`tools/debug/cenas/validar_autoria_ragdoll.py` gera uma cena isolada sem abrir o jogo.
Verifica coincidência entre prévia e caixas/pivôs, repetição sem duplicar, rollback,
preservação de constraints alheias, proteção de referências, dois rigs e persistência.
Modos de UI verificam Undo/Redo e callback de desenho no editor. O resultado explícito
é gravado em JSON; sucesso automatizado não substitui avaliação visual da prévia.
