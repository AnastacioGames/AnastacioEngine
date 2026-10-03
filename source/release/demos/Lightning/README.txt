Demo Raio (emissor de raio em Empty)
====================================

Abra Lightning.range. Cada layer tem um exemplo, com o nome na barra N >
Layers. Troque o layer (teclas 1 a 5 do topo do teclado) e aperte P.

    Layer 1  Automatico (circulo)       raios caem sozinhos dentro do circulo
    Layer 2  Quadrado com janela        so cai entre 5 s e 20 s de jogo
    Layer 3  Target (origem e destino)  o raio vai do Empty ate a esfera
    Layer 4  Manual por logic brick     ESPACO solta o raio (Edit Object >
                                        Lightning Strike)
    Layer 5  Manual por Python          G solta o raio, F so o clarao
                                        (script raio_python.py)

O que ver no editor:

    Empty selecionado > Properties > Object Data > painel Lightning
    Logic Editor nos layers 4 e 5; Text Editor > raio_python.py e LEIA-ME

O clarao na tela precisa de World > Rain ligado (ja vem ligado na demo).
