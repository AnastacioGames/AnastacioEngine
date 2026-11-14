"""Monta o vídeo final do tutorial: vinheta + gravação em 1080p + narração + legenda.

    python tools/tutoriais/montar_video.py <pasta do tutorial> <pasta de saída> [vinheta.mp4]

Usa bruto.mp4, tempos.json e narracao/*.wav da pasta de saída (gravar_video.py e narrar.py).
Gera <nome>.mp4 (legenda queimada na imagem) e <nome>.srt (para o YouTube).
"""
import json, subprocess, sys
from pathlib import Path

pasta, saida = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
vinheta = Path(sys.argv[3]).resolve() if len(sys.argv) > 3 else None
roteiro = json.loads((pasta / 'roteiro.json').read_text(encoding='utf-8'))
tempos = json.loads((saida / 'tempos.json').read_text(encoding='utf-8'))
nome = pasta.name
FORMATO = 'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,setsar=1'


def rodar(*args):
    subprocess.run(['ffmpeg', '-v', 'error', '-y'] + [str(a) for a in args], check=True, cwd=str(saida))


def duracao(arquivo):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(arquivo)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout)


# Legenda: o texto curto de cada passo (o mesmo do painel da engine).
textos = {'abertura': roteiro['titulo'], 'encerramento': roteiro['encerramento']}
for i, p in enumerate(roteiro['passos'], 1):
    textos['%02d' % i] = '%d. %s' % (i, p['texto'])


def hora(s):
    return '%02d:%02d:%02d,%03d' % (s // 3600, s % 3600 // 60, s % 60, round(s % 1 * 1000) % 1000)


def escrever_srt(arquivo, atraso):
    linha = '%d\n%s --> %s\n%s\n\n'
    arquivo.write_text(''.join(linha % (i, hora(t['inicio'] + atraso), hora(t['fim'] + atraso - 0.1), textos[t['nome']])
                               for i, t in enumerate(tempos, 1)), encoding='utf-8')


escrever_srt(saida / 'corpo.srt', 0.0)  # queimada na imagem: aparece em qualquer player
# A gravação encolhe um pouco e a legenda fica numa faixa própria embaixo, sem tapar a interface.
CORPO = 'scale=1728:972,pad=1920:1080:(ow-iw)/2:0:color=0x16161c,fps=30,setsar=1'
ESTILO = 'FontName=Segoe UI,FontSize=11,Bold=1,PrimaryColour=&H00FFFFFF,BorderStyle=1,Outline=0,Shadow=0,Alignment=2,MarginV=9'

# 1. Corpo: gravação + narrações, cada uma no instante em que o passo começou.
entradas, filtros, nomes = ['-i', saida / 'bruto.mp4'], [], []
for i, t in enumerate(tempos, 1):
    entradas += ['-i', saida / 'narracao' / (t['nome'] + '.wav')]
    ms = int(t['inicio'] * 1000)
    filtros.append('[%d:a]aresample=48000,adelay=%d|%d[a%d]' % (i, ms, ms, i))
    nomes.append('[a%d]' % i)
filtros.append('%samix=inputs=%d:normalize=0,apad[fala]' % (''.join(nomes), len(nomes)))
filtros.append("[0:v]%s,subtitles=corpo.srt:force_style='%s'[v]" % (CORPO, ESTILO))
corpo = saida / 'corpo.mp4'
rodar(*entradas, '-filter_complex', ';'.join(filtros), '-map', '[v]', '-map', '[fala]', '-shortest',
      '-c:v', 'libx264', '-crf', '18', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ac', '2', corpo)

# 2. Vinheta no mesmo formato, com fade no fim.
atraso = 0.0
partes = [corpo]
if vinheta:
    atraso = duracao(vinheta)
    v = saida / 'vinheta.mp4'
    fade = max(0.0, atraso - 0.6)
    rodar('-i', vinheta, '-vf', '%s,fade=t=out:st=%.2f:d=0.6' % (FORMATO, fade), '-af', 'aresample=48000,afade=t=out:st=%.2f:d=0.6' % fade,
          '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ac', '2', v)
    atraso = duracao(v)
    partes.insert(0, v)

# 3. Legenda separada (para o YouTube), já contando a vinheta.
srt = saida / (nome + '.srt')
escrever_srt(srt, atraso)

# 4. Junta tudo.
lista = saida / 'partes.txt'
lista.write_text(''.join("file '%s'\n" % p.as_posix() for p in partes), encoding='utf-8')
final = saida / (nome + '.mp4')
rodar('-f', 'concat', '-safe', '0', '-i', lista, '-c', 'copy', final)
print('pronto:', final, '%.1f s' % duracao(final))
