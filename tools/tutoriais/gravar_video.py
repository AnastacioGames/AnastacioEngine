"""Grava o vídeo de um tutorial a partir do roteiro.json + acoes.py da pasta dele.

    python tools/tutoriais/gravar_video.py <pasta do tutorial> <pasta de saída> [--ensaio]

Normal: abre o editor VISÍVEL em tela cheia, grava com o Screencast usando o mouse e o teclado
de verdade (o Screencast desenha o cursor real do sistema) e anota em tempos.json quando cada
passo começou.  NÃO mexa no mouse durante a gravação.

--ensaio: editor invisível, eventos simulados, sem gravar; salva um print por passo
(ensaio_NN.png) para conferir as coordenadas.

A duração de cada passo vem da narração (narracao/NN.wav, feita antes por narrar.py).
"""
import ctypes, importlib.util, json, os, sys, time, wave
from pathlib import Path

AQUI = Path(__file__).resolve().parent
# Pasta de sessão própria: outro agente pode estar usando o controle ao mesmo tempo.
os.environ.setdefault('ANASTACIO_CONTROLE_PASTA', str(AQUI.parents[1] / 'artifacts/testes/controle_tutorial'))
sys.path.insert(0, str(AQUI.parent / 'testes_engine'))
import controle

ESCALA_UI = 1.5
U = ctypes.windll.user32
BOTOES = {'LEFTMOUSE': (0x0002, 0x0004), 'RIGHTMOUSE': (0x0008, 0x0010)}
TECLAS = {'RET': 0x0D, 'ESC': 0x1B, 'HOME': 0x24}


class Mao:
    """Mouse e teclado do tutorial: reais na gravação, simulados no ensaio."""

    def __init__(self, editor, real):
        self.ed, self.real = editor, real
        self.x, self.y = 1280, 500
        if real:
            U.SetProcessDPIAware()
            U.SetCursorPos(self.x, self.y)

    def pedir(self, cmd, **dados):
        r = self.ed.pedir(cmd, **dados)
        if not r['ok']:
            raise RuntimeError(r.get('traceback') or r.get('erro'))
        return r.get('resultado')

    def py(self, codigo):
        return self.pedir('py', codigo=codigo)

    def _sim(self, tipo, valor, **k):
        self.pedir('evento', tipo=tipo, valor=valor, x=self.x, y=self.y, **k)

    def esperar(self, segundos):
        time.sleep(segundos if self.real else min(segundos, 0.2))

    def mover(self, x, y, segundos=0.9):
        x0, y0 = self.x, self.y
        passos = max(2, int(segundos * 40)) if self.real else 2
        for i in range(1, passos + 1):
            t = i / passos
            t = t * t * (3 - 2 * t)  # sai e chega devagar, como a mão
            self.x, self.y = int(x0 + (x - x0) * t), int(y0 + (y - y0) * t)
            if self.real:
                U.SetCursorPos(self.x, self.y)
                time.sleep(segundos / passos)
            else:
                self._sim('MOUSEMOVE', 'NOTHING')
        self.esperar(0.25)

    def clicar(self, x, y, botao='LEFTMOUSE', segundos=0.9):
        self.mover(x, y, segundos)
        if self.real:
            U.mouse_event(BOTOES[botao][0], 0, 0, 0, 0)
            time.sleep(0.18)
            U.mouse_event(BOTOES[botao][1], 0, 0, 0, 0)
        else:
            self._sim(botao, 'PRESS')
            time.sleep(0.15)
            self._sim(botao, 'RELEASE')
            time.sleep(0.15)
        self.esperar(0.5)

    def rolar(self, cliques):
        """Roda do mouse: positivo desce."""
        for _ in range(abs(cliques)):
            if self.real:
                U.mouse_event(0x0800, 0, 0, -120 if cliques > 0 else 120, 0)
                time.sleep(0.04)
            else:
                self._sim('WHEELDOWNMOUSE' if cliques > 0 else 'WHEELUPMOUSE', 'PRESS')
        self.esperar(0.4)

    def tecla(self, nome):
        """Uma tecla: letra ('P') ou RET/ESC/HOME."""
        if self.real:
            vk = TECLAS.get(nome) or ord(nome.upper())
            U.keybd_event(vk, 0, 0, 0)
            time.sleep(0.08)
            U.keybd_event(vk, 0, 2, 0)
        else:
            self._sim(nome, 'PRESS')
            self._sim(nome, 'RELEASE')
        self.esperar(0.3)

    def digitar(self, texto):
        for letra in texto:
            if self.real:
                codigo = U.VkKeyScanW(ord(letra))
                shift = codigo & 0x100
                if shift:
                    U.keybd_event(0x10, 0, 0, 0)
                U.keybd_event(codigo & 0xFF, 0, 0, 0)
                U.keybd_event(codigo & 0xFF, 0, 2, 0)
                if shift:
                    U.keybd_event(0x10, 0, 2, 0)
                time.sleep(0.12)
            else:
                self._sim(letra.upper(), 'PRESS', texto=letra, shift=letra.isupper())
                self._sim(letra.upper(), 'RELEASE')
        self.esperar(0.3)


def duracao(wav):
    with wave.open(str(wav)) as w:
        return w.getnframes() / w.getframerate()


def main():
    pasta, saida = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    ensaio = '--ensaio' in sys.argv
    roteiro = json.loads((pasta / 'roteiro.json').read_text(encoding='utf-8'))
    spec = importlib.util.spec_from_file_location('acoes', pasta / 'acoes.py')
    acoes = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(acoes)
    saida.mkdir(parents=True, exist_ok=True)
    video = saida / 'bruto.mp4'

    controle.abrir(str(pasta / roteiro['cena_inicial']), visivel=not ensaio, args_extra=('--window-fullscreen',))
    ed = controle.Editor()
    mao = Mao(ed, real=not ensaio)
    tempos = []
    try:
        mao.py("bpy.context.user_preferences.view.ui_scale = %r" % ESCALA_UI)
        time.sleep(1.0)
        acoes.preparar(mao, ed)  # eventos simulados, fora do vídeo
        time.sleep(1.0)
        if not ensaio:
            mao.pedir('op', nome='screen.screencast', args={'filepath': str(video), 'full': True, 'audio': False})
        inicio = time.time()

        def falar(nome, acao=None):
            wav = saida / 'narracao' / (nome + '.wav')
            fala = duracao(wav) if wav.exists() and not ensaio else 0.0
            t0 = time.time()
            tempos.append({'nome': nome, 'inicio': t0 - inicio})
            if acao:
                mao.esperar(min(1.5, fala * 0.3))
                acao(mao)
            resto = fala + 0.7 - (time.time() - t0)
            if resto > 0:
                time.sleep(resto)
            tempos[-1]['fim'] = time.time() - inicio
            if ensaio:
                mao.pedir('tela', arquivo=str(saida / ('ensaio_%s.png' % nome)))

        time.sleep(0.5 if ensaio else 0.8)
        falar('abertura')
        for i, _passo in enumerate(roteiro['passos'], 1):
            falar('%02d' % i, getattr(acoes, 'passo_%d' % i, None))
        falar('encerramento')
        time.sleep(0.5)
        if not ensaio:
            mao.pedir('op', nome='screen.screencast')
            time.sleep(1.5)
            (saida / 'tempos.json').write_text(json.dumps(tempos, indent=1), encoding='utf-8')
    finally:
        ed.canal.write(json.dumps({'cmd': 'fechar', 'token': ed.sessao['token']}) + '\n')
        ed.canal.flush()
    print('ok:', saida)


if __name__ == '__main__':
    main()
