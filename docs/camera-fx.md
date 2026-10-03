# Câmera do jogo: foco, rastreio, Camera FX e tremor

Recursos nativos da câmera no jogo, configurados no painel da câmera (Properties > Camera, só no motor
Range Game) e no Python (`KX_Camera`). Plano original: [camera-fx-plan.md](camera-fx-plan.md).

Tudo vem desligado. Uma câmera antiga continua igual: o foco é calculado, mas nada é desenhado nem movido.
Só a câmera ativa da cena é atualizada (uma vez por frame, depois da física e do scenegraph).

## Painel "Focus & Tracking"

**Focus** diz onde a câmera foca:

| Modo | Alvo |
|---|---|
| Manual | Distância fixa (`gpu_dof.focus_distance`) |
| Object | O objeto em "Object" (o mesmo `dof_object` da câmera) |
| Property | O objeto mais próximo com a propriedade de jogo verdadeira (bool true ou número diferente de 0) |
| Auto | O que estiver sob o ponto de mira ("Aim Point", 0..1 com Y de cima para baixo), por raio físico |

- **Range**: profundidade que fica nítida em volta do foco, em metros.
- **Smooth**: segundos para a distância de foco chegar ao novo valor.
- No modo Property, a cena é varrida no máximo a cada 0,5 s. O alvo guardado vale enquanto a propriedade
  continuar verdadeira. Se o objeto for removido, uma nova busca é feita na hora. Sem alvo, o foco volta
  para a distância manual.
- No modo Auto, se o raio não acerta nada, a última distância é mantida.

**Tracking** faz a câmera girar no próprio eixo para seguir o alvo. Só funciona com foco Object ou Property:

- **Look At**: só a rotação acompanha o alvo, suavizada. A posição não muda.
- **Drone**: Look At com a flutuação (hover) e a inclinação na curva (bank) do drone do Rolima Racer.
  A troca de alvo já é suave, porque a rotação é interpolada.
- **Track Smooth**: segundos (constante de tempo, `1 - exp(-dt/τ)`), com a mesma velocidade a 30 ou 144 FPS.
- **Angle Limit**: ângulo máximo em relação à orientação da câmera (0 = sem limite).
- **Dead Zone**: fração da tela em volta do centro dentro da qual a câmera não gira.
- **Framing Offset**: onde o alvo fica na tela (0,0 = centro; Y negativo põe o alvo mais para baixo).
- **Keep Horizon**: não rola a câmera.

O rastreio é um deslocamento aplicado por cima da orientação do objeto. `worldOrientation` continua sendo
a orientação que o parent e os scripts definem, então nada se acumula. A orientação desenhada fica em
`cam.trackOrientation`, e desligar o rastreio devolve a câmera ao normal.

## Painel "Camera Effects"

No máximo dois passes de filtro 2D, reservados logo depois do Lens Flare:

- **DOF** (`FILTERPASS_CAMERA_DOF`): Depth of Field em bokeh, com anéis (Low 2, Medium 3, High 5), raio
  máximo em pixels e lâminas do diafragma (`gpu_dof.blades`; menos de 3 dá disco).
- **Lens** (`FILTERPASS_CAMERA_LENS`), um passe único com:
  - Speed Blur radial a partir do ponto de foco na tela, que cresce com a velocidade da câmera (Full Speed = m/s para a força total);
  - Directional Blur na direção em que a câmera gira;
  - Protect Focus, que deixa a faixa de foco (o carro) fora dos dois borrões;
  - aberração cromática;
  - vinheta e olho de peixe;
  - grão de filme (Film Grain), animado e mais forte nos tons médios.

Cada passe só existe enquanto um efeito dele estiver ligado. Com tudo desligado, não há nenhum passe.
O shader compila só quando o passe aparece; ligar ou desligar outro efeito do mesmo passe não recompila nada.
Os filtros Python do jogo continuam depois deles: o índice reservado passou de 18 para 20.

**Cat Eye Lens**, as três opções (dá para ligar mais de uma):

1. **Bokeh**: o disco do bokeh vira "olho de gato" nas bordas da tela (precisa do DOF ligado).
2. **Aberration**: franjas de cor nas bordas; "Speed" faz crescer com a velocidade.
3. **Vignette / Fisheye**: cantos escuros e distorção de barril (positivo) ou almofada (negativo).

## Painel "Camera Shake"

`cam.shake(trauma, duration=0)` soma "trauma" (0..1). O deslocamento é `trauma² × Amplitude` por lens
shift, com um ruído na frequência dada. Com duration, o tremor some nesse tempo; sem ela, cai
`Decay` por segundo. **Shake Roll** também rola a câmera um pouco. Esse tremor soma com o terremoto do
World (Weather > Earthquake), sem um anular o outro.

## Python (`KX_Camera`)

| Atributo | Tipo | Descrição |
|---|---|---|
| `focusMode` | int 0..3 | 0 Manual, 1 Object, 2 Property, 3 Auto |
| `focusObject` | KX_GameObject/None | Alvo do modo Object |
| `focusProperty` | str | Propriedade do modo Property |
| `focusTarget` | KX_GameObject/None, RO | Objeto em foco neste frame |
| `focusValid` | bool, RO | Há um alvo/ponto de foco real |
| `focusPosition` | Vector, RO | Posição do foco no mundo |
| `focusDistance` | float, RO | Distância de foco suavizada, ao longo do eixo da câmera |
| `focusScreenPosition` | Vector 2D, RO | Foco na tela, 0..1, Y de cima para baixo (como `getScreenPosition`) |
| `focusManualDistance`, `focusRange`, `focusSmooth` | float | |
| `trackMode` | int 0..2 | 0 Off, 1 Look At, 2 Drone |
| `trackSpeed`, `trackLimit`, `trackDeadzone`, `trackScreenOffset`, `droneAmplitude`, `droneFrequency`, `trackBank`, `useTrackUpLock` | | Rastreio |
| `trackOrientation` | Matrix, RO | Orientação desenhada (base + rastreio + rolagem do tremor) |
| `useDof`, `useSpeedBlur`, `useDirectionalBlur`, `useBlurProtect`, `useCatEye`, `useChromatic`, `useChromaticSpeed`, `useVignette`, `useGrain` | bool | Liga/desliga cada efeito |
| `dofQuality` (0..2), `dofBlur`, `speedBlurStrength`, `speedBlurMaxSpeed`, `directionalBlurStrength`, `directionalBlurMax`, `catEyeStrength`, `chromaticStrength`, `vignetteStrength`, `vignetteRadius`, `fisheyeStrength`, `grainStrength` (0..1) | | Parâmetros |
| `cameraSpeed` | float, RO | Velocidade da câmera desenhada (m/s, suavizada) |
| `speedOverride` | float | ≥ 0 substitui `cameraSpeed` no Speed Blur e na aberração; -1 volta ao automático |
| `shakeAmplitude`, `shakeFrequency`, `shakeDecay`, `useShakeRoll` | | Tremor |
| `shakeTrauma` | float, RO | Trauma atual |
| `shake(trauma, duration=0.0)` | método | Soma tremor |

## Migração do Rolima Racer (feita em 2026-10-03)

O componente `scripts/camera_system/NativeCameraFX.py` do jogo substituiu `SpeedBlurFX`, `DirectionalBlurFX`,
`BokehDoF` e `NoiseFilterFX` nos empties de câmera. Ele liga os efeitos nativos na câmera ativa a partir
das opções do menu (`graphicsMotionBlur`, `graphicsNitroBlur`, `graphicsSlowmoDoF`, `graphicsNoiseFilter`).
O drone (`camera_change.py`) e o tremor (`camera_shake.py`) continuam em Python.
