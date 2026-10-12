# Plano: evolução do Fog - Volumetric

Base: commit f6b083fe (Fog - Volumetric aprovado visualmente). A neblina é uma lib GLSL só,
`gpu_shader_vfog_lib.glsl`, usada pelo filtro do jogo e pela 3D View. Os dados de cada frame vêm de
`KX_FillVolumetricFog` (KX_RenderPipeline.cpp) no jogo e de `gpu_vfog_fill` (gpu_compositing.c) na 3D View.
O layout de `vfog_data` está documentado no topo da lib. Quando ele mudar, mude também
`RAS_2DFilterData.h` (`VFOG_DATA_VEC4`) e `GPU_VFOG_DATA_VEC4`.

Cena de teste: `tools/debug/cenas/criar_cena_vfog.py` (uma variante por recurso, com FPS de ~10 s
gravado em `VFOG_FPS_LOG` e captura em `VFOG_SHOT`).

| # | Item | Status | Quem |
|---|------|--------|------|
| 1 | Vento e hora do dia | feito, aguarda aceite visual | Claude |
| 2 | Raios de sol (Sun Shafts) | feito, aguarda aceite visual | Claude |
| 3 | Fog Volumes melhores | feito, aguarda aceite visual | Claude |
| 4 | Controle por Python / Logic | feito (2ec9637b), aguarda aceite visual | Codex |
| 5 | Fumaça/vapor locais | pendente | |
| 6 | Neblina que abre ao passar | pendente | |
| 7 | Emission acendendo a névoa | pendente | |
| 8 | Nuvens + névoa contínuas | pendente | |
| 9 | Froxels | pendente | |
| 10 | Fogo/explosão volumétrico | pendente | |

## 1. Vento e hora do dia
- **Wind** (`vfog_use_wind`, `vfog_wind_direction` em graus em Z): o ruído é levado pelo vento.
  A velocidade é Rain Wind × 20 m/s. O deslocamento vai em `vfog_data[9].xy`.
- **Morning Fog** (`vfog_use_time_of_day`, `vfog_morning_boost`, padrão 2): a densidade é multiplicada
  por `1 + boost·m` e o falloff por `1 - 0.5·m`, com `m = exp(-((sun_hour-6)/1.5)²)`. `sun_hour` é a
  World Property. No jogo ela é lida a cada frame; na 3D View, da lista de propriedades do World.
- Arquivo antigo: `vfog_morning_boost == 0` marca o arquivo (readfile.c).
- Variantes da cena de teste: `medium_vento` e `medium_manha`.

## 2. Raios de sol (Sun Shafts)
- `vfog_use_sun_shafts` (padrão ligado), só em Medium/High. O Sun precisa de sombra (não Variance).
- Usa o mapa de sombra que alcança mais longe (a última cascata, se houver):
  `RAS_ILightObject::GetFarShadow`.
- Vai no 3º slot de sombra `vfog_shadow2` (unidade 22 no jogo, 8 na 3D View) e em `vfog_mats[6]`.
  `vfog_data[8].z/w` guardam o bias e a flag "tem sombra".
- No laço principal, o termo do sol é multiplicado por `vfogSunShadow(p)`. Low continua analítico, sem raios.
- Variante: `medium_sol`. A sombra do Sun precisa cobrir a cena (clip end, frustum size).

## 3. Fog Volumes melhores
- Propriedades de jogo opcionais no objeto com `fog_volume`:
  - `fog_shape` = `"sphere"` (padrão: caixa);
  - `fog_edge` (sobrepõe o Volume Edge do World).
- A cor do objeto (Object > Color, diferente de branco) tinge o volume.
- Dados:
  - `vfog_data[10][i]`: forma;
  - `vfog_data[11][i]`: borda;
  - `vfog_data[44+i]`: cor rgb e "tem cor".
- A borda é corroída por ruído, para o volume não parecer caixa ou bola.
- Onde volumes se sobrepõem, a cor é a média ponderada pela densidade de cada um.
- Variante: `medium_volumes` (esfera laranja + caixa verde).

## 4. Controle por Python / Logic (Codex)
- Python: identificadores `weather.vfog*` em `KX_WorldInfo::Set/GetWeatherRuntimeProperty`, que gravam
  nos campos `World->vfog_*`.
- Logic: World Properties `vfog_enabled` e `vfog_density` (`BKE_world_status_props_ensure`,
  `BL_ConvertProperties.cpp`), lidas a cada frame, e um grupo "Fog - Volumetric" em
  `BUILTIN_WORLD_PROPERTY_GROUPS`.
- Ligar em runtime quando o arquivo começou com a fog desligada: criar o filtro sob demanda, ou
  documentar a limitação.
- Não mexe no shader, em `KX_FillVolumetricFog` nem no DNA.
- Variante: `medium_script`.

## Itens pendentes (5-10)
5. **Fumaça/vapor locais:** volume esfera com ruído que sobe (chaminé, bueiro, chaleira).
6. **Neblina que abre ao passar:** até 4 "pushers" (objetos com propriedade) que reduzem a densidade
   num raio em volta deles.
7. **Emission acendendo a névoa:** materiais com Emission viram lâmpadas virtuais (ou um buffer de
   brilho em baixa resolução) que tingem a neblina.
8. **Nuvens + névoa contínuas:** a névoa de altitude encontra a base das Volumetric Clouds (descer
   da montanha para dentro da nuvem).
9. **Froxels:** grade 3D presa à câmera (por exemplo 160×90×64), com injeção de luz e integração em
   compute/RTT. Muitas lâmpadas a custo fixo; é o caminho para qualidade AAA.
10. **Fogo/explosão volumétrico:** volume com temperatura → cor (corpo negro) e ruído turbulento,
    ligado ao sistema de destruição/explosões.
