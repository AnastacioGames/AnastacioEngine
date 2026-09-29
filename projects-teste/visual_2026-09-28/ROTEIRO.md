# Testes visuais — 2026-09-28

Abrir o editor: `build-linux-editor/bin/RangeEngine`
Responda cada item com OK ou descreva o problema.

## 1. Drop de OBJ
- [ok] Arrastar `piramide.obj` do gerenciador de arquivos para a Vista 3D: a pirâmide entra sem diálogo.

## 2. Asset Browser (biblioteca: `assets/biblioteca.blend`)
- [ok] Adicionar a pasta `assets/` como biblioteca e trocar para o modo Assets.
- [ok] Arrastar o objeto `Macaco` para a Vista 3D.
- [ok] Arrastar o grupo `GrupoTeste` para a Vista 3D.
- [ok] Arrastar o material `Vermelho` para um objeto.
- [ok] O duplo clique num asset funciona.
- [ok] O toggle Append/Link muda o resultado (o Link fica com o nome em azul/ligado no Outliner).
- [ok] Window > Asset Browser abre a janela separada.
- [ok] "Generate Previews" mostra as miniaturas.

## 3. Painéis novos (com o motor em modo jogo)
- [ok] Render e Scene: os painéis Game Settings, os ajustes de FXAA e o LOD com Billboard/Invisible.
- [ok] Material > Transparency: o layout novo e os dois avisos (Mask/Raytrace + Opaque; Depth Transparency sem efeito).
- [ok] Material > Options: sem Invert Z e sem Exclusive, Light Group ativo fora do Halo, Z Offset sempre ativo, e o aviso de Instancing + GPU Skinning.
- [ok] Material > Subsurface Scattering: sem presets, o RGB Radius sem "m", e o efeito some ao desligar Diffuse na lâmpada.
- [ok] Material > Shading com Vertex/Fragment GLSL próprio: o jogo roda e o layout está correto.

## 4. Loop de tempo — cena `loop_tempo.blend`
Rodar: `build-linux/bin/RangeRuntime projects-teste/visual_2026-09-28/loop_tempo.blend`
Monitor a 60 Hz: `xrandr --output eDP-1 --rate 60` (para voltar: `--rate 144`).
Teclas: setas movem o cubo · Espaço soma em "teclas" · V alterna v-sync · P liga pico de 80 ms/s · R centraliza.
- [ok] V-sync ON: FPS perto de 60 (não trava em 30); cada Espaço soma 1; o cubo anda liso.
- [ok] V-sync OFF (V): o mesmo; o cubo anda na mesma velocidade.
- [ok] Pico ligado (P): o tranco aparece, mas nenhuma tecla se perde e o cubo não "pula" nem fica lento depois.
- [ ] Repetir a 144 Hz — pendente: precisa da GPU (no llvmpipe não passa de ~60 FPS).
