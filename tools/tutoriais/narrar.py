"""Gera a narração (um .wav por fala) e as legendas base de um tutorial, com o Piper (offline).

    <python do venv do Piper> tools/tutoriais/narrar.py <pasta do tutorial> <pasta de saída> <modelo.onnx>

A voz é pt-BR: termos em inglês da interface são trocados por uma grafia que ela lê direito
(só na fala; o texto da tela e a legenda continuam com o nome real do botão).
"""
import json, subprocess, sys
from pathlib import Path

PRONUNCIA = [
    ("UI Tree", "iu-ai trí"), ("Node Editor", "nôud éditor"), ("3D View", "três dê viu"),
    ("Setup Game Logic", "setâp gueim lódjic"), ("On Click", "on clíque"),
    ("New", "niú"), ("Start", "istárt"), ("UI", "iu-ai"), ("Text", "técst"),
]

pasta, saida, modelo = Path(sys.argv[1]), Path(sys.argv[2]) / 'narracao', sys.argv[3]
roteiro = json.loads((pasta / 'roteiro.json').read_text(encoding='utf-8'))
falas = [('abertura', roteiro['abertura'])]
falas += [('%02d' % i, p['narracao']) for i, p in enumerate(roteiro['passos'], 1)]
falas += [('encerramento', roteiro['encerramento'])]
saida.mkdir(parents=True, exist_ok=True)
for nome, texto in falas:
    for de, para in PRONUNCIA:
        texto = texto.replace(de, para)
    subprocess.run([sys.executable, '-m', 'piper', '-m', modelo, '-f', str(saida / (nome + '.wav'))],
                   input=texto.encode('utf-8'), check=True)
    print(nome, texto)
