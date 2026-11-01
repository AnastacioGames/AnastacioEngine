# Personagem automático (Fuse → armature base) — plano

Status: planejado em 2026-11-01. Nada implementado ainda.

## Problema

Hoje cada personagem passa por: Fuse → Mixamo (site) → FBX → Blender → conversão → materiais → LOD →
ragdoll → grupo → jogo. Subir e baixar do Mixamo e refazer os mesmos passos à mão toma muito tempo.

## Ideia

Passar pelo Mixamo **uma vez só**. Um personagem já rigado vira a **base** (armature + malha com os pesos do
Mixamo). Personagens novos saem do Fuse em OBJ e um botão liga a malha na armature base, sem o site.
Todos ficam com o mesmo esqueleto: qualquer animação do Mixamo serve em todos, e ragdoll/LOD ficam previsíveis.

## Fluxo do botão "Ligar na armature base"

1. **Importar o OBJ do Fuse** e acertar escala/rotação (aplicar transformações).
2. **Escolher a base** mais parecida (altura e largura do quadril/ombro), quando houver mais de uma
   (ex.: homem, mulher, criança).
3. **Encaixar o esqueleto**: copiar a armature base e ajustar os ossos à malha nova, por pontos medidos
   na malha (altura total, quadril, ombros, cotovelos, punhos, joelhos, tornozelos, pescoço, cabeça).
   Primeira versão: escala por segmento (tronco, braços, pernas) a partir das caixas da malha;
   refinamento por cortes transversais se precisar.
4. **Copiar os pesos** da malha base para a nova com Data Transfer (vertex groups, vizinho mais próximo /
   face interpolada) em pose de repouso, e aplicar. Fallback: Automatic Weights do Blender.
5. **Ligar** a malha na armature (modificador Armature, parent).
6. **Materiais do Fuse**: cor, normal e especular ligados; transparência em cabelo, cílios e
   sobrancelhas; materiais iguais juntados.
7. **LOD**: reaproveitar `game.lod_generate_batch` (`anastacio_lod_auto.py`).
8. **Ragdoll**: preset de caixas para os nomes de ossos do Mixamo no addon Anastacio Ragdoll
   (`anastacio_ragdoll.py`), sem marcar osso por osso.
9. **Grupo** com o nome do personagem, pronto para Add Object.

Cada etapa é um operador separado (dá para rodar uma só) e o botão encadeia todas, com Undo.
Nomes de ossos: remover o prefixo `mixamorig:` na base para as animações casarem (ou manter e
documentar; decidir com o usuário).

## Arquivos necessários (usuário, 2026-11-02)

Em `tests/assets/personagem/`:

1. Um personagem já rigado pelo Mixamo (`.range` ou FBX) → vira a base.
2. O OBJ (com texturas) de outro personagem do Fuse, sem rig → teste.

## Decisões em aberto

- Quantos níveis de LOD e distâncias padrão.
- Ragdoll: componente novo (`ragdoll-runtime.md`) ou o do RolimaRacer.
- Padrão de nome do grupo e da collection.
- Uma base só ou várias (homem/mulher/criança).
- Prefixo `mixamorig:`: remover ou manter.

## Riscos

- Corpos muito diferentes da base: ombro/quadril podem precisar de ajuste manual (mitigação: várias bases).
- Roupa larga e cabelo: pesos podem esticar; retoque no Weight Paint.
- Aqui só há Blender sem janela; validação visual da deformação fica com o usuário.

## Ordem de implementação

1. Operadores de importar OBJ, copiar pesos e ligar (testáveis sem janela com os arquivos de exemplo).
2. Encaixe do esqueleto.
3. Materiais do Fuse.
4. LOD, preset de ragdoll Mixamo e grupo.
5. Botão único e painel; doc de uso.
