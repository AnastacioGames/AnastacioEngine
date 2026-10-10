# Tesla Rhythm

Modo de ritmo em Python Component, sem mudanças em C++. A fonte cinematic é preservada;
saída: `build/bin/demos/TeslaPiano/TeslaPiano_Rhythm.range`.

## Contrato

- Cinco pistas A/S/D/F/G com notas simples e acordes, overlay via post_draw.
- Música original de 112 BPM, 16 compassos, 116 notas e entrada silenciosa de 3 segundos.
- WAV e mapa derivados dos mesmos timestamps. Relógio pela posição do áudio Audaspace;
  valor monotônico evita pequenas oscilações da estimativa entre buffers.
- Descida por tempo restante. Pressionamento julga uma nota; tecla segurada não repete.
- Perfeito até 45 ms; bom 90 ms; aceitável 140 ms. Erros quebram combo, multiplicador até 4x.
- Offset positivo atrasa o mapa em relação ao áudio. Setas ajustam em passos de 5 ms.
- Câmera alterna suavemente os lados frontais a cada 8 beats e olha ao Terminal.
  Fundo acompanha a câmera; blur de movimento desativado nesta variante.
- Espaço inicia/pausa/continua; R reinicia. Resultado mostra precisão e maior combo.
- Notas longas, MIDI e mapas de músicas externas são etapas futuras.

## Fontes e configurações

[Componente](../tools/tesla_rhythm/anastacio_tesla_rhythm.py),
[mapa e julgamento](../tools/tesla_rhythm/anastacio_rhythm_core.py),
[gerador](../tools/create_tesla_rhythm.py).

O gerador copia módulos editáveis ao lado do jogo e inclui os mesmos no Text Editor.
`anastacio_tesla_rhythm.AnastacioTeslaRhythm` está anexado à câmera. Painel expõe música,
tempo de descida, offset, volume, movimento de câmera e beats por alternância.
Trocar somente o WAV não gera mapa novo: é preciso sincronizar o mapa com a música.
Regenerar com o editor em background sobre a fonte cinematic e
`--python tools/create_tesla_rhythm.py` substitui a variante Rhythm e seu WAV.

## Validação

Núcleo passou limites de janela, prevenção de duplicatas, perdas, acordes e mapa completo.
[Sonda runtime](../tools/tesla_rhythm/validate_runtime.py) cria cena separada:
áudio, desenho do HUD, julgamento, orientação da câmera, pausa, resultado, reinício
e remoção do callback passaram. Resultado em `rhythm_probe_result.txt` na pasta da demo.
Aparência, enquadramento e latência percebida aguardam teste no jogo real.
