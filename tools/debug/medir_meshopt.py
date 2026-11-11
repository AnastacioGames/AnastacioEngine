"""A/B do meshoptimizer (ordem dos índices para o cache de vértices) sem abrir janela na tela do usuário.

    python tools/debug/medir_meshopt.py <pasta das cenas> [rodadas] [natural,random]

Cenas geradas por tools/debug/cenas/criar_cena_meshopt.py (natural e random). Para cada cena roda o
AnastacioRuntime no desktop invisível do controle.py com RANGE_MESHOPT_OFF=1 (antes) e sem (depois),
alternando, `rodadas` vezes cada (padrão 2). Cada execução mede o tempo médio de quadro por 8 s depois
de 3 s de aquecimento (script da cena) e grava em meshopt_<modo>_result.txt. Também pega do log do
runtime as linhas "meshopt:" (ACMR antes/depois, com RANGE_MESHOPT_LOG=1).
Imprime "MESHOPT <modo> off=<0|1> frame_ms=..." e a média por condição.
"""

import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'tools/testes_engine'))
import controle  # noqa: E402

__import__('os').environ.pop('RANGE_MESHOPT_OFF', None)  # a rodada "depois" não pode herdar
PASTA = Path(sys.argv[1]).resolve()
RODADAS = int(sys.argv[2]) if len(sys.argv) > 2 else 2
MODOS = sys.argv[3].split(',') if len(sys.argv) > 3 else ['natural', 'random']


def rodar(modo, off):
    cena = PASTA / ('meshopt_%s.range' % modo)
    resultado = PASTA / ('meshopt_%s_result.txt' % modo)
    antes = resultado.read_text().splitlines() if resultado.exists() else []
    prof = PASTA / ('prof_%s_%d_%d.txt' % (modo, off, int(time.time() * 1000)))
    prof.unlink(missing_ok=True)
    log_inicio = tamanho_log()
    env = {'RANGE_MESHOPT_LOG': '1', 'RANGE_PROFILE': str(prof)}
    if off:
        env['RANGE_MESHOPT_OFF'] = '1'
    jogo = controle.abrir_jogo(cena, largura=1280, altura=720, env_extra=env)
    try:
        limite = time.time() + 60
        while time.time() < limite:
            linhas = resultado.read_text().splitlines() if resultado.exists() else []
            if len(linhas) > len(antes):
                time.sleep(0.5)
                return linhas[-1], prof, log_inicio
            time.sleep(0.5)
        return None, prof, log_inicio
    finally:
        try:
            jogo.fechar()
        except Exception:
            pass


LOG = Path(__import__('os').environ.get('TEMP', '.')) / 'range_runtime.log.txt'


def tamanho_log():
    return LOG.stat().st_size if LOG.exists() else 0


def acmr_da_rodada(inicio):
    """Linhas "meshopt:" do log do runtime desta rodada (vazio com .cooked, desligado ou só material
    transparente). O runtime recria o log a cada execução; `inicio` só vale se o arquivo cresceu."""
    if not LOG.exists():
        return []
    texto = LOG.read_bytes()
    if texto.startswith(b'AnastacioRuntime log started'):
        inicio = 0
    return [l.strip() for l in texto[inicio:].decode(errors='replace').splitlines() if 'meshopt:' in l]


def gpu_avg(prof):
    """Média das linhas AVG (120 frames cada) sem as duas primeiras (~4 s a 60 fps, cobre os 3 s de
    aquecimento da cena): {etapa gpu: ms}."""
    if not prof.exists():
        return {}
    avgs = [l for l in prof.read_text(errors='replace').splitlines() if l.startswith('AVG')][2:]
    soma = {}
    for l in avgs:
        if 'gpu:' not in l:
            continue
        for item in l.split('gpu:')[1].split():
            if '=' in item:
                k, v = item.split('=', 1)
                try:
                    soma[k] = soma.get(k, 0.0) + float(v)
                except ValueError:
                    pass
    return {k: v / len(avgs) for k, v in soma.items()} if avgs else {}


medias = {}
for modo in MODOS:
    for r in range(RODADAS):
        for off in (1, 0):
            linha, prof, log_inicio = rodar(modo, off)
            if not linha:
                print('MESHOPT %s off=%d INCOMPLETA (sem resultado em 60 s), descartada' % (modo, off))
                continue
            gpu = gpu_avg(prof)
            if 'render.cameras' not in gpu:
                print('MESHOPT %s off=%d sem render.cameras no perfil, descartada' % (modo, off))
                continue
            print('MESHOPT %s off=%d gpu render.cameras=%.3f ms' % (modo, off, gpu['render.cameras']))
            for l in acmr_da_rodada(log_inicio)[:2]:
                print('   ', l)
            medias.setdefault((modo, off), []).append(gpu['render.cameras'])
for (modo, off), v in sorted(medias.items()):
    print('MEDIA gpu render.cameras %s %s: %.3f ms (%s)' % (modo, 'antes' if off else 'depois', sum(v) / len(v),
                                       ', '.join('%.3f' % x for x in v)))
