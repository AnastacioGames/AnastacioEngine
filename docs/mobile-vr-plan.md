# VR no celular (Web, estilo Cardboard)

Criado em 2026-09-30. Objetivo: jogar no navegador do celular (ou no APK WebView) dentro de um visor barato,
com imagem dividida por olho e a câmera seguindo a cabeça. Sem headset dedicado: OpenXR fica adiado até haver
hardware para validar (o SDK já está em `lib/win64_vc15/openxr_sdk`, fora do build).

## O que já existe

- Estéreo Side-by-Side (`RAS_STEREO_SIDEBYSIDE`): viewport dividido, um render por olho, frustum assimétrico
  (`RAS_Rasterizer::GetFrustumMatrix`) e câmera deslocada pela metade da separação (`GetViewMatrix`).
- O player Web (`GPG_Ghost.cpp`) já lê `scene->gm.stereoflag/stereomode` do `.range`: ligar Stereo →
  Side-by-Side no editor vale no export.
- `bge.logic.motion` (`KX_PythonMotion`): giroscópio, acelerômetro, gravidade, `orientation` (alpha/beta/gamma
  do W3C), `tilt` e `calibrate()`, lidos de `Module.rangeMotion` (JS em `tools/web/package-web.py`).
- Página Web: tela cheia e trava em paisagem (`package-web.py`), pedido de permissão de sensores no iOS.

## Peças (uma por vez, com validação do usuário entre elas)

1. **Pose da cabeça.** O JS calcula o quaternion da câmera a partir do `deviceorientation`
   (`Rz(alpha)·Rx(beta)·Ry(gamma)·Rz(-ângulo da tela)`; os eixos do aparelho coincidem com os da câmera do
   Blender: x direita, y cima, -z para onde a câmera traseira olha) e entrega em `Module.rangeMotion.quat`.
   `KX_PythonMotion` ganha `headOrientation` (Matrix 3x3, com o yaw recentralizado) e `recenter()`.
   Teste: script que imprime/aplica a matriz; girar o celular.
2. **Head tracking automático.** Opção "VR Head Tracking" (Stereo) que aplica `headOrientation` só à
   view da câmera ativa (o objeto câmera continua sob controle do jogo: corpo/yaw pelo jogo, cabeça pelo
   sensor), com suavização leve. Raycast de olhar via helper Python.
3. **Distorção de lente + botão "Entrar em VR".** Filtro de barril por olho no Side-by-Side (intensidade
   ajustável); botão na página que entra em tela cheia, trava paisagem, pede permissão e recentraliza.
4. Depois: separação padrão 0,064 m no modo VR, mira por olhar (gaze) com seleção por tempo,
   `bge.render.setStereoMode`, sombras em cascata cobrindo os dois olhos.

## Limitações conhecidas

- Só rotação (3DoF), sem andar no espaço.
- Sensores exigem HTTPS (ou `localhost`); iOS pede permissão num toque. Safari: eixos do `rotationRate` não
  testados.
- Deriva do yaw depende do aparelho (bússola); `recenter()` corrige.

## Estado

- [x] Peça 1 (2026-09-30): código pronto, `RangeRuntime` nativo e `build-web-release` compilam; quaternion
  conferido no Node (retrato em pé olhando para o norte → frente +y; virado a oeste → frente -x).
  **Falta validar no celular** com o teste abaixo.
- [x] Peça 2 (2026-10-01): opção "VR Head Tracking" (flag da cena `GAME_VR_HEAD_TRACKING`, painel Stereo). A
  câmera ativa aplica `N·Rx(-90°)·H` na view (N = orientação do objeto, H = `headOrientation`); o primeiro valor
  do sensor vira o "frente" (auto-recenter). Validada no celular. Suavização e helper de gaze ficaram para depois.
- [x] Peça 3 (2026-10-01): flag `GAME_VR_LENS_DISTORTION` (painel Stereo), variante `LENS_DISTORT` do shader de
  frame buffer aplicada por olho na apresentação do Side-by-Side (k fixo 0,3) e botão "Entrar em VR" na página
  (tela cheia, wake lock). Sem correção de aberração cromática; intensidade ainda não configurável.
- [x] Peça 4 (2026-10-01): separação 0,064 no modo VR, `KX_Camera.gazeDirection`, `bge.render.setStereoMode`, cascatas
  seguindo a view da cabeça. Sombra simples validada no celular; CSM no celular descartada (no celular vale uma sombra só, pequena). Seleção por tempo: exemplo em `source/release/scripts/templates_range/vr_gaze.py` (validado no celular com o First_Person). Correção: as câmeras de cada olho do estéreo recebem a rotação da cabeça (`CopyHeadView`).

- Ajustes (2026-10-01): `bge.render.setVRLensStrength(k)` (0 a 1, padrão 0,3) e `bge.logic.motion.smoothing` (segundos, padrão 0,04, 0 desliga; filtro só na view da cabeça). Exemplo: `templates_range/vr_tune.py`. O overlay de perfil só entra com `--perf` no `package-web.py`; o APK final sai sem ele.

## Gaze sem Python: sensor Ray com eixo "VR Gaze" (feito, 2026-10-01)

Em vez de um sensor novo, o sensor **Ray** ganhou o eixo **VR Gaze** (`SENS_RAY_GAZE`): o raio sai da câmera na direção da
cabeça (`gazeDirection`). Campo **Gaze Time** (ms, `bRaySensor.gaze_time`, 0 = instantâneo): só dispara depois de olhar
o mesmo objeto por esse tempo. Python: `sensor.gazeTime` (s) e `sensor.gazeProgress` (0..1, para barras). Propriedade,
material, X-Ray e máscara funcionam como no Ray normal. Usar na câmera ativa. Validado no celular (2026-10-01) com `vr_bricks.range`: Ray VR Gaze + Filter 2D Invert ao olhar o cubo por 1 s. Cuidado: não ligar o sensor ao mesmo controlador And da música (o And falso para o som). Próximos: VR Move, gatilho Cardboard, VR Head.

## VR Move: opção "VR Gaze" no atuador Motion (feito, 2026-10-01)

Em vez de um atuador novo, o Motion (modos Simple e Character) ganhou a opção **VR Gaze** (`ACT_DLOC_VR_GAZE`,
`use_vr_gaze`): o campo **Loc** passa a valer na direção do olhar da câmera ativa projetada no chão (Y = frente,
X = direita, Z = cima do mundo); o "L" fica ignorado. Olhando reto para cima/baixo, usa a frente do próprio objeto.
Uso: no corpo do jogador, Motion Simple com Loc Y = 0,05 e VR Gaze, ligado ao gatilho (toque) ou a um Always.
A conversão logic bricks → Python recusa essa opção por enquanto. Aceleração suave: com VR Gaze, o **Damping** (frames, ao lado da opção) faz a velocidade subir de 0 até o Loc
ao apertar e cair até 0 ao soltar (só no modo Simple; 0 = liga/desliga seco). Ainda sem teleporte.
Validado no celular (2026-10-01): anda para onde olha; a inclinação não muda a velocidade (é o esperado). Aceleração com Damping 45 e Loc Y 0,05 (~3 m/s) aprovada.

## Parâmetros VR no painel Stereo (feito, 2026-10-01)

Implementado com shorts no padding do `GameData` (`vr_lens_strength` em %, `vr_head_smoothing` em ms; 0 = padrão 30%/40 ms, então cenas antigas não precisam de versionamento). Lido em `LA_Launcher`. Plano original:

Hoje a intensidade da lente e a suavização só são ajustáveis por Python (`vr_tune.py`). Plano para levá-las ao
painel Render → Stereo, salvas na cena:

1. **DNA** (`GameData` em `DNA_scene_types.h`): `float vr_lens_strength` (0..1, padrão 0,3) e
   `float vr_head_smoothing` (segundos, 0..5, padrão 0,04). Usar o espaço de padding existente ou
   adicionar no fim da struct; conferir alinhamento.
2. **Versionamento**: no `versioning_*` do `.range`, preencher os padrões em cenas antigas (valor 0 não pode
   virar "lente zero" sem querer).
3. **RNA** (`rna_scene.c`): `game_settings.vr_lens_strength` e `vr_head_smoothing`, com range e descrição.
4. **UI** (`properties_game.py`, painel Stereo): dois campos abaixo dos checkboxes "VR Head Tracking" e
   "VR Lens Distortion", visíveis só com esses ligados.
5. **Runtime**: no início da cena (GPG_Ghost / `KX_KetsjiEngine`, onde `gs.vr_*` já é lido), chamar
   `SetVRLensStrength` e definir `m_smoothing` do `KX_PythonMotion` a partir da cena. O Python
   (`setVRLensStrength`, `motion.smoothing`) continua valendo em tempo de execução e sobrescreve o painel.
6. **Docs/teste**: atualizar esta página e o changelog; compilar o editor e o runtime nativo e o Web; validar
   no celular com o `fp_vr.range`, tirando o `vr_tune.py`.

## Ideias para facilitar jogos VR (sugestões, 2026-10-01)

Ordem sugerida, da maior para a menor facilidade para quem faz o jogo:

1. **Sensor "VR Gaze" (logic brick).** Sem Python: raio do olhar com filtro por propriedade, saída positiva ao
   olhar (opção de tempo mínimo, 0 = instantâneo) e campo de progresso 0..1 para barras. Substitui o `vr_gaze.py`.
   Bônus: atuador de feedback (cor/escala ao ser olhado), com restauração ao sair.
2. **Atuador "VR Move" (andar para onde olha).** Move o corpo para a frente da `gazeDirection` (só no plano
   horizontal, opção de voo), com velocidade e botão/gatilho. Sem enjoo: aceleração suave e opção de "teleporte"
   (marca o ponto olhado e salta).
3. **Sensor "VR Head" (gestos).** Positivo em: olhar para cima/baixo além de um ângulo, balançar a cabeça
   (sim/não) e inclinar. Útil para menus e ações sem tela de toque.
4. **Gatilho do Cardboard.** Sensor para o toque na tela (o visor não tem botão) com opção de toque longo, e
   ligação com o gaze: "olhar + tocar" como clique.
5. **Mira/cursor VR.** Reticle de ponto na profundidade do objeto olhado, desenhado nos dois olhos (hoje o HUD
   2D não tem paralaxe). Opção na câmera: "VR Reticle".
6. **UI no espaço 3D.** Painéis curvos presos à cabeça ou ao mundo, com gaze nativo, já que overlays 2D
   ficam errados em estéreo.
7. **Conforto.** Vinheta ao girar/mover rápido (reduz enjoo), recentralizar pelo olhar (segurar o olhar para
   baixo por 2 s) e opção de snap-turn do corpo.
8. **Painel único "VR" no editor.** Agrupar flags, lente, suavização, separação e vinheta num painel só, com
   botão "Preparar cena VR" que liga Stereo, Side-by-Side, 0,064, head tracking e lente de uma vez.
9. **Exportação.** Preset "Cardboard" no `package-web.py`/`package-android.py` (paisagem, sem overlay, botão
   VR já visível, tela sempre ligada).

Itens 1, 2 e 4 dão o maior ganho: um jogo simples (olhar, andar, clicar) fica possível só com logic bricks.

**Pendência futura (anotada 2026-10-01):** quando os bricks de VR existirem, atualizar a conversão de logic
bricks para componente Python para cobrir os novos sensores/atuadores (VR Gaze, VR Move, gatilho Cardboard).
Não fazer agora.

## Teste da peça 1 (celular)

1. Na câmera do jogo, um sensor Always com pulso (True Level Triggering) ligado a um controlador Python em
   modo Module `vr_test.head`, e um sensor Mouse "Left Button" ligado a `vr_test.recenter`.
2. Render → Display → Stereo: **Stereo**, modo **Side-by-Side**, Eye Separation **0.064**.
3. Exportar Web, abrir no celular por HTTPS (ou no APK), tocar em Jogar e virar o celular de lado.

```python
# vr_test.py
import bge

def head(cont):
    m = bge.logic.motion
    cam = cont.owner
    if not m.available:
        return
    if not cam.get("vr_ok"):  # tenta até chegar a primeira leitura
        cam["vr_ok"] = m.recenter()
    # Câmera sem pai: orientação no mundo. Com pai (corpo do jogador), vale relativa a ele.
    cam.localOrientation = m.headOrientation

def recenter(cont):
    if cont.sensors[0].positive:
        bge.logic.motion.recenter()
```

Esperado: olhar para frente ao começar; virar o corpo, olhar para cima/baixo e inclinar a cabeça movem a
câmera no mesmo sentido; tocar na tela recentraliza para a frente.
