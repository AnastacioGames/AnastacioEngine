Demo Destruicao
===============

Abra Destruction.range e aperte P (ou Play). A cena e a First Person com
objetos que quebram e explodem usando os recursos nativos da engine.

Controles:

    WASD, Shift, Espaco   andar, correr, pular
    Botao direito         pegar e soltar caixas
    Botao esquerdo        arremessar o que estiver na mao
    E                     explosao onde a mira aponta
    G                     arremessa uma granada (pavio de 2 s)

O que ver no editor (aba Physics):

    Crate.00..02   Destruction: os tres usam o mesmo grupo Crate.00_fragments,
                   quebram ao bater forte (Break on Collision) ou numa explosao
    BreakWall      Destruction num objeto Static: so a explosao quebra
    Barrel.00..02  Explosive com Explode on Impact e Chain Reaction
    Grenade        Explosive na layer 2 (inativa), Fuse 2 s; cada copia criada
                   com addObject tem o seu proprio pavio
    Explosion_fx   o Effect dos barris e da granada, tambem na layer 2

Os pedacos ficam na layer 2 e foram gerados pelo botao Generate Fragments...
do painel Destruction. O limite de pedacos vivos esta em
Scene > Game Physics > Max Debris.

O componente destruction_demo.ExplosionTester (texto interno, no Player) so
cuida das teclas E e G e mostra os callbacks: onExplode faz a camera tremer.
Nada nele e necessario para os objetos quebrarem ou explodirem.

API Python: KX_GameObject.shatter() e KX_Scene.explode() na referencia (source/doc/python_api/rst/bge_types).
