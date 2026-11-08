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

## Occluder automático (feito em 2026-11-07)

Opção **Automatic Occluders** em Scene > Culling, embaixo de Occlusion Culling (`use_auto_occlusion`, bit
`SCE_AUTO_OCCLUSION` em `GameData.lodflag`; desligada em arquivos antigos e novos).

- **Escolha no load** (`BL_IsAutoOccluder`, `BL_BlenderDataConversion.cpp`): malha estática (sem Dynamic/Rigid/
  Soft/Character/Sensor/Navmesh), visível, sem deformador, todos os materiais opacos, até 2048 triângulos, caixa
  no mundo com o 2º maior lado >= 1,5 m e a maior face >= 6 m². Liga só a flag interna de occluder: a física
  continua (o tipo "Occluder" da UI tira a colisão). Log: `auto occluders: N in scene X`.
- **Liga/desliga no jogo** (`KX_Scene::CalculateVisibleMeshes`): a cada 30 quadros o modo oposto roda só para
  contar objetos (callback sem efeito colateral, nada a mais é desenhado). Fica ligado se esconde >= 15% do que o
  frustum mantém e >= 8 objetos. Log: `auto occlusion on/off`.

Medido (`medir_visibilidade.py`, GPU 8x): prédio 5,1 → 3,75 ms (50 objetos, igual ao Occluder manual); cena aberta
desliga sozinho, culling igual ao sem auto.

Limites: objetos de LibLoad não entram na escolha; split screen divide a mesma média entre câmeras; pisos grandes
também viram occluders (custam raster mesmo escondendo pouco).
