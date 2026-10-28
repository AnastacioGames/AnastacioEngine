# Teste de timing no Linux nativo

Repete no Linux, com placa de vídeo, o teste do objeto andando em círculo (ajuste do Kitsuy, spin/sleep).

## Antes

- A placa de vídeo tem que estar ativa: `glxinfo -B | grep renderer` deve mostrar a placa, não `llvmpipe`.
- Pacotes: `sudo apt install wine mesa-utils python3-psutil`.
- Ter o `build/bin` do Windows acessível (ex.: disco D: montado em `/media/...`).

## Rodar

Na raiz do repositório (`git pull` antes):

    bash tools/timing_linux.sh /caminho/para/AnastacioEngine/build/bin

Com o build nativo de Linux também (serve de comparação sem Wine):

    bash tools/timing_linux.sh /caminho/windows/build/bin /caminho/linux/bin

Leva ~3 min (8 rodadas de 10 s, a 60 e a 120 fps). O resultado fica em `timing_linux_result.txt`;
mande esse arquivo para análise.

## Como ler

- `dist` ≈ `expected`: sem câmera lenta.
- `radius` ~5,3 em todos: física igual.
- `step_cv` baixo: movimento liso na tela.
- `drift` pequeno (< 1 m): a volta passa sempre no mesmo lugar.
