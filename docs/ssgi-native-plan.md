# SSGI nativo

Implementação isolada em `D:/AnastacioEngine-ssgi`, branch `codex/native-ssgi`.

## Contrato e sequência

1. Quatro buffers explícitos do Principled opaco: normal em view space + validade; albedo difuso + elegibilidade
   do receptor; radiância difusa direta linear + validade; cor total linear antes do display transform.
   O quarto permite compor em linear e reaplicar Standard/Filmic sem inverter uma imagem já tonemapeada.
   O material conectado diretamente ao Material
   Output é o escopo inicial. Outros grafos recebem saídas zeradas, sem inferir albedo pelo frame final.
2. SSGI opcional antes de SSR/AO/bloom/tonemap, em meia resolução, com limite de alcance, teste de
   geometria e upscale bilateral. AO continua independente. Iluminação baked não é reamostrada como fonte.
   Receptores já cobertos pelo bake são excluídos por padrão para evitar adicionar novamente GI estática.
3. Validar compilação e execução dos buffers/passagens; usuário avalia aparência no jogo real.
4. Depois da validação: histórico temporal com rejeição de disoclusões e objetos móveis, Hi-Z e suporte
   a grafos mistos/legados. Não declarar ganho de desempenho sem medição de GPU.

Não altera DNA nem reserva buffers quando desligado. Configuração persistente por propriedades da Scene,
com painel e API de runtime. Desktop é o alvo inicial; Web/Android mantêm bake e não alocam SSGI.

## Validações necessárias

Parede vermelha sem ambiente; metal sem rebatimento difuso; bake + SSGI; fundo/sky; material não suportado;
MSAA ligado/desligado; resize; alternar efeito; câmera perspectiva/ortográfica; runtime e editor; custo GPU.

## Estado em 2026-10-11

V1 experimental implementada no worktree, com build completo de `RangeEngine` e `RangeRuntime`
e execução bem-sucedidos. Ainda não integrada ao checkout principal. Nenhuma validação visual concluída.

No editor deste build, use Game > Native SSGI (Experimental), logo abaixo de Shading, com Shading Nodes ligado e material
Principled ou Diffuse BSDF opaco ligado diretamente ao Material Output, ou material simples sem nós;
Shading Nodes da Scene continua obrigatório. Reinicie Play depois de ligar a opção da Scene.
Os últimos quatro slots de attachments precisam estar livres. Padrão: 4 raios, 8 passos, divisor 2,
raio 3, força 1, espessura 0,1. API: `scene.filterManager.changeSSGIValues(enabled, radius, strength,
rays, steps, thickness, divisor=0)`, onde divisor `0` preserva a resolução e `1/2/4` troca o buffer em runtime.
O painel oferece presets Low (4/8/divisor 4), Medium (6/12/divisor 2), High (8/16/divisor 1) e Ultra
(12/24/divisor 1); Ultra é opt-in para cenas desktop lentas/estáticas e custa mais GPU. Alterar um
controle avançado marca a Scene como Custom.
Em `Requirements & Limits`, expansível no próprio painel, estão os requisitos de material e attachments,
o comportamento de World/Sky, bake e as limitações de espaço de tela. Os textos do painel e da ajuda têm
traduções inglês, português, espanhol e russo.
Desligar por API mantém os buffers; para não alocá-los, desligue na Scene antes
de carregar o jogo. Não é possível criá-los por essa API depois de carregar com a opção desligada.

### Evidências e limitações

- Cenas geradas, salvas e reabertas por `tools/debug/cenas/criar_cena_ssgi.py` e `inspecionar_ssgi.py`.
  `ssgi_runtime_probe.py` faz leituras numéricas de buffers somente com `SSGI_TEST_LOG` ou benchmark
  com `SSGI_BENCH`; abrir a cena normalmente não altera câmera, resolução ou efeito.
- Standard e Filmic: diferenças positivas ao alternar SSGI; metal e material não suportado excluídos.
  Bake válido preservado ao reabrir: zero receptores elegíveis e diferença on/off zero.
  Resize, perspectiva/ortográfica, parâmetro NaN e opção desligada testados. Sem erros OpenGL.
- Os dois fragment shaders compilaram também com `#version 330 core` no driver real; isso não constitui
  validação de todo o runtime em core profile. MSAA e Play no editor ainda precisam de validação dedicada.
- RX 6800M, 640×480, padrão 4×8: filtros ~0,55 ms desligados com buffers, ~0,91 ms ligados
  (+0,36 ms). Incluindo render de câmera, ~0,28 ms sem recurso versus ~1,08 ms ligado (+0,80 ms).
  Medição pelo profiler existente, sem readback; jogo limitado a 60 FPS. Não extrapolar para iGPU/1080p.
- Os buffers de normal e albedo usam RGBA8; radiância direta e cor linear continuam RGBA16F. Isso acrescenta
  24 bytes/pixel por framebuffer antes de MSAA (era 32, redução de 25%); os framebuffers compartilhados
  duplicam esses attachments. VRAM total não foi medida.
- Não há histórico temporal nem Hi-Z nesta etapa: pode haver ruído espacial e instabilidade de enquadramento.
  Só fontes difusas diretas opacas Principled/Diffuse BSDF ou material simples; emissivos, grafos mistos,
  transparência e material legado com texturas/shader customizado não suportados.
  Receptores cobertos por lightmap/light volume ficam excluídos. Não substitui o bake nem ilumina fora da tela.

Próxima etapa: usuário conferir no jogo real; depois otimizar alocação e avaliar temporal/Hi-Z separadamente.
