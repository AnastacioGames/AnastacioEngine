Demo Efeitos de Render
======================

Abra RenderEffects.range e aperte P. A camera vai e volta na frente da cena.

    Esfera espelhada / piso  Screen Space Reflection (SSR)
    Esfera dourada           reflexo rugoso (GGX)
    Cantos e escada          Ambient Occlusion (SSAO)
    Parede vermelha          luz rebatida (SSGI) no chao e na parede clara
    Bloco laranja            Bloom
    Ar da cena               Volumetric Fog (World > Weather)

Teclas no jogo:

    C        pausa/retoma a camera
    1 2 3    preset de qualidade Low, Medium e High (a cena reinicia)

O que ver no editor:

    Properties > Scene > Post Processing: Quality Preset no topo e cada efeito
    Text Editor > teste_efeitos.py: troca de preset por Python
                 (scene.setQualityPreset / getQualityPreset)
