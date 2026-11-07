# Plano: visibilidade pré-calculada (PVS) e portais

Estado: **PVS e portais descartados** em 2026-11-07 após a V0: não ganham do Occluder que já existe.
V1-V4 abaixo ficam só como registro. O trabalho seguiu para o Occluder automático (seção no fim).

## Resultado da V0 (2026-11-07)

Cena `tools/debug/cenas/criar_cena_visibilidade.py`: 36 salas, 1308 objetos, câmera olhando um corredor de
portas. Medidor `tools/debug/cenas/medir_visibilidade.py` (trabalho por quadro = soma do profile sem Sleeping).
RX 6800M; "8x" = `RANGE_WEAK_GPU=8`. Ruído entre rodadas ~±0,5 ms.

| Caso | Objetos desenhados | Draw calls | ms (desktop) | ms (8x) |
|---|---|---|---|---|
| Tudo, Auto Static Batch (padrão) | 553 | 13 | 1,5-1,6 | 4,7-5,4 |
| Tudo, sem batch | 553 | 553 | 2,8-3,0 | 4,8-5,1 |
| Occluder nas paredes, sem batch | 50 | 50 | 1,7-1,8 | 3,9-4,1 |
| Occluder nas paredes + batch | 50 | 29 | 1,65 | 3,8 |
| PVS ideal por sala (salas invisíveis escondidas à mão), sem batch | 239 | 239 | 1,8-2,3 | 4,2-5,4 |

Leitura:
- O Auto Static Batch já tira quase todo o custo de CPU das salas escondidas (13 draw calls).
- O Occluder herdado corta mais que um PVS por sala perfeito (50 x 239 objetos), porque também esconde o
  que está atrás de móveis e fora do recorte da porta. Custa ~+0,25 ms de CPU no culling.
- Ganho real só aparece com GPU fraca: Occluder + batch ~20-27% menos tempo que o padrão.
- O PVS por bake teria culling mais barato (0,15 ms), mas não desenharia menos que o Occluder. Não compensa
  o bake, a memória e o risco de popping.

Achado à parte: no runtime atual `use_frame_rate = False` não solta o FPS (a espera em
`KX_KetsjiEngine::UpdateSleepTime` segue a taxa de lógica). As cenas de medição sobem a lógica para 1000 Hz;
as medições antigas de FSR (`artifacts/fsr`) ficaram presas em 60 FPS.

## Nova direção: Occluder automático

O ganho existe, mas hoje exige marcar paredes como Occluder à mão. Proposta:
1. Botão "Auto Occluders" (Game > Performance): marca como Occluder malhas estáticas grandes e fechadas
   (paredes, pisos, prédios) por regra de tamanho/espessura/opacidade; desfazível.
2. Scene Doctor: cena com muitos objetos e nenhum Occluder → dica com o botão.
3. Medir em cena aberta (RolimaRacer-like) para garantir que os +0,25 ms de culling não pioram cenas sem
   paredes; se piorar, a regra só sugere em interiores.

## Problema

Em interiores (casas, cavernas, túneis, prédios) a engine desenha salas inteiras escondidas atrás de paredes.
O que existe hoje não resolve bem esse caso:

- **Frustum culling**: corta o que está fora da tela, não o que está atrás de parede.
- **HLOD / LOD**: simplifica o que está longe; não remove o que está perto e escondido.
- **Occluder** (herdado da Range/UPBGE, `KX_GameObject::m_bOccluder` + buffer de oclusão do DBVT): é automático no
  jogo, mas exige marcar à mão os objetos que tapam, roda na CPU a cada quadro e custa caro com muitos occluders.

Inspiração: PVS do Quake (bake automático) e portais/áreas do Doom 3 (manual, dinâmico).

## Decisão de desenho

1. **Principal: PVS por bake, automático.** Botão "Bake Visibility", como Lightmap e Probes. Nada para marcar.
2. **Complemento opcional: portais manuais** só para portas que abrem e fecham.
3. Fora do escopo: occlusion query na GPU (atraso de 1 quadro, ganho pequeno na iGPU).

## Etapas

### V0. Cena de teste e medição
- Script em `tools/debug/cenas/` gerando um prédio com N salas e corredores, objetos em cada sala.
- Medir no Performance Report: draw calls, objetos enviados, ms de CPU e GPU (rodadas ~10 s, PC fraco simulado).
- Critério para seguir: ganho medido na cena controlada, nunca no jogo.

### V1. Bake do PVS (editor, Python + C)
- Grade de células sobre o AABB dos objetos estáticos (tamanho configurável, padrão ~2 m), só células com chão
  ou alcançáveis (descartar células dentro de paredes).
- De cada célula, lançar raios para amostras dos AABB dos objetos/grupos; visível se algum raio chega.
- Raycast: Bullet do editor primeiro; Embree só se o tempo de bake passar do aceitável (Embree já está em `lib/`,
  mas fica só no editor, nunca no runtime nem na Web).
- Resultado: bitset célula → objetos visíveis, comprimido (RLE), guardado na cena e no `.cooked`.
- Margem conservadora: dilatar 1 célula para não sumir objeto ao cruzar fronteira.

### V2. Uso no jogo (C++)
- Câmera → célula → bitset → marca objetos invisíveis antes do frustum culling (custo O(1) por quadro).
- Objetos dinâmicos: entram sempre (ou pela célula onde estão, se houver tempo).
- Integra com sombras: casters fora do PVS da célula da luz podem ser cortados (fase posterior).
- Fallback: câmera fora da grade → desenha tudo, como hoje.

### V3. Portais manuais para portas
- Objeto "Portal" (plano) ligado a uma porta; Python `portal.open = False` desliga a passagem.
- No bake, células dos dois lados guardam a dependência do portal; com ele fechado, o que só é visto por ele some.

### V4. Ferramentas
- Scene Doctor: cena interior grande sem PVS → dica; PVS desatualizado (estáticos movidos) → aviso.
- Overlay no editor mostrando células e o que é visível da célula selecionada.
- Docs e site.

## Riscos
- Tempo de bake em cenas grandes (mitigar com grupos por HLOD em vez de objetos soltos).
- Objeto sumindo indevidamente (popping): margem de células e teste visual com janela.
- Memória do bitset: N células × M objetos bits; usar grupos e RLE.
- Pouco ganho em cenas abertas (RolimaRacer): o Scene Doctor só sugere em interiores.
