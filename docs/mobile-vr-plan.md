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
