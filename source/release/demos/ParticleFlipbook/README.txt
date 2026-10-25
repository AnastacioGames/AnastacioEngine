Demo Flipbook de Particulas (confete)
=====================================

Abra ParticleFlipbook.range e aperte P.

    Esquerda  "animado": cada particula toca os 16 quadros do atlas durante a
              vida (cor muda e a bolinha encolhe)
    Direita   "aleatorio": cada particula fica parada num quadro sorteado

A textura flipbook_atlas.png e um atlas 4 x 4; o quadro 0 fica no canto de
cima a esquerda. Ela precisa ficar ao lado do .range.

O que ver no editor:

    Empty selecionado > Properties > Particles > Texture:
        Columns, Rows, Cycles (vezes por vida; 0 = parado) e Random Start

Por Python:

    obj.particles.flipbook = (colunas, linhas, ciclos, aleatorio)
