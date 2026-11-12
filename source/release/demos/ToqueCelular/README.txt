Demo Controles de Toque - Corrida (celular)
===========================================

Carrinho visto de cima, painel que mostra cada entrada do controle e menu de
pausa. Serve para testar e explorar o layout de toque "Racing" no celular
(navegador ou APK).

No PC: abra ToqueCelular.range e aperte P.
    Setas = volante, gas e freio. Enter = Start (abre o menu).

No celular:
    1. Properties > Render > Web: "Touch controls" ja vem em
       "Racing (steer + pedals)". Exporte a Web, ou gere o APK no painel
       Android.
    2. Abra no celular. Os controles aparecem na tela:
         - volante: stick, setas ou inclinar o aparelho (o botao de trocar
           alterna entre os tres)
         - gatilho de cima = gas, de baixo = freio
         - A, B, X, Y, RB acendem no painel; II = Start
    3. Start abre a PAUSA. Toque em "Controles: ligados" para desligar:
       o toque passa a ser mouse e voce aperta "Voltar a corrida" ou
       "Reiniciar". Depois ligue os controles de novo.
    4. Gire o aparelho: a linha de cima mostra "deitado" ou "em pe".

O que olhar:
    - os numeros LX / LT / RT e as barras seguem o dedo e voltam a zero ao
      soltar (nada preso);
    - o carro sai por um lado da pista e entra pelo outro (conta voltas).

Para explorar: o script do jogo esta no Text Editor (toque_race.py). Ele le
logic.joysticks[0] (axisValues: 0 = volante, 4 = freio, 5 = gas;
activeButtons: 0 A, 1 B, 2 X, 3 Y, 6 Start, 10 RB), o mesmo que um controle
fisico entrega. O mesmo codigo vale para teclado, controle e toque.

A cena e gerada por tools/debug/cenas/criar_cena_toque_race.py.
