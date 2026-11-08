"""Roda dentro do jogo (AnastacioRuntime ou P no editor) e deixa o controle.py dirigir a partida.

Carregado pela engine via RANGE_CONTROL_SCRIPT: ela chama tique() no começo de cada frame,
com a primeira cena ativa. Mesmo protocolo do servidor.py: uma linha JSON por pedido.
"""
import json, os, secrets, socket, time, traceback
from Range import logic, events, render

ARQUIVO_SESSAO = os.environ['RANGE_CONTROL_SESSION']
TOKEN = secrets.token_hex(16)
ESTADO = {'escuta': None, 'conexao': None, 'buffer': b'', 'frame': 0,
          'soltar': [],      # (frame, código) de teclas a soltar
          'adiado': None,    # (frame, função) pedido que responde depois de alguns frames
          'inicio': time.time()}
ESPERA_CONEXAO = 60  # sem controle conectado nesse tempo, o jogo fecha: no desktop invisível ninguém o fecharia


def texto(valor):
    if valor is None or isinstance(valor, (bool, int, float, str)):
        return valor
    if isinstance(valor, dict):
        return {str(k): texto(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple, set)):
        return [texto(v) for v in valor]
    if hasattr(valor, 'to_list'):
        return valor.to_list()
    if hasattr(valor, '__len__') and hasattr(valor, '__getitem__'):
        try:
            return [texto(v) for v in valor]
        except Exception:
            pass
    return repr(valor)


def cena(nome=None):
    cenas = logic.getSceneList()
    return next(c for c in cenas if c.name == nome) if nome else cenas[0]


def codigo(tecla):
    """'W', 'SPACE', 'LEFTMOUSE' ou o número do events."""
    if isinstance(tecla, int):
        return tecla
    nome = tecla.upper()
    return getattr(events, nome if hasattr(events, nome) else nome + 'KEY')


def cmd_py(p):
    espaco = {'logic': logic, 'events': events, 'render': render, 'cena': cena, 'resultado': None}
    exec(p['codigo'], espaco)
    return texto(espaco['resultado'])


def cmd_estado(_p):
    return {'frame': ESTADO['frame'], 'fps': logic.getAverageFrameRate(),
            'cenas': [{'nome': c.name, 'objetos': len(c.objects), 'camera': c.active_camera.name if c.active_camera else None}
                      for c in logic.getSceneList()],
            'janela': [render.getWindowWidth(), render.getWindowHeight()]}


def cmd_tecla(p):
    """Aperta agora e solta depois de `frames` (padrão 2); `segurar` mantém apertada."""
    c = codigo(p['tecla'])
    logic._simulateInput(c, 1)
    if not p.get('segurar'):
        ESTADO['soltar'].append((ESTADO['frame'] + p.get('frames', 2), c))
    return c


def cmd_soltar(p):
    logic._simulateInput(codigo(p['tecla']), 0)
    return True


def cmd_mouse(p):
    """Move o mouse para x, y em pixels da janela (de cima para baixo)."""
    logic._simulateInput(events.MOUSEX, 0, p['x'], p['y'])
    return True


def cmd_esperar(p):
    return adiar(p.get('frames', 1), lambda: ESTADO['frame'])


def cmd_tela(p):
    render.makeScreenshot(p['arquivo'])  # gravado no fim do frame
    return adiar(3, lambda: os.path.exists(p['arquivo']) and p['arquivo'])


def cmd_fechar(_p):
    logic.endGame()
    return True


COMANDOS = {n[4:]: f for n, f in globals().items() if n.startswith('cmd_')}


class Adiado:
    def __init__(self, frames, funcao):
        self.frame, self.funcao = ESTADO['frame'] + frames, funcao


def adiar(frames, funcao):
    return Adiado(frames, funcao)


def atender(linha):
    try:
        pedido = json.loads(linha)
        if pedido.get('token') != TOKEN:
            return {'ok': False, 'erro': 'token inválido'}
        r = COMANDOS[pedido['cmd']](pedido)
        if isinstance(r, Adiado):
            ESTADO['adiado'] = r
            return None
        return {'ok': True, 'resultado': r}
    except Exception as erro:
        return {'ok': False, 'erro': str(erro), 'traceback': traceback.format_exc()}


def escuta():
    if ESTADO['escuta'] is None:
        s = socket.socket()
        s.bind(('127.0.0.1', 0))
        s.listen(4)
        s.setblocking(False)
        ESTADO['escuta'] = s
        with open(ARQUIVO_SESSAO + '.tmp', 'w') as f:
            json.dump({'porta': s.getsockname()[1], 'token': TOKEN, 'pid': os.getpid()}, f)
        os.replace(ARQUIVO_SESSAO + '.tmp', ARQUIVO_SESSAO)
    return ESTADO['escuta']


def responder(resposta):
    c = ESTADO['conexao']
    if c is not None:
        c.setblocking(True)
        c.sendall((json.dumps(resposta) + '\n').encode('utf-8'))
        c.setblocking(False)


def tique():
    e = ESTADO
    e['frame'] += 1
    for item in [s for s in e['soltar'] if s[0] <= e['frame']]:
        e['soltar'].remove(item)
        logic._simulateInput(item[1], 0)
    if e['adiado'] is not None:
        if e['frame'] < e['adiado'].frame:
            return
        try:
            responder({'ok': True, 'resultado': texto(e['adiado'].funcao())})
        except Exception as erro:
            responder({'ok': False, 'erro': str(erro)})
        e['adiado'] = None
        return
    if e['conexao'] is None:
        try:
            e['conexao'], _ = escuta().accept()
            e['conexao'].setblocking(False)
            e['buffer'] = b''
        except BlockingIOError:
            if time.time() - e['inicio'] > ESPERA_CONEXAO:
                logic.endGame()
            return
    try:
        dados = e['conexao'].recv(1 << 20)
        if not dados:
            logic.endGame()  # o controle desconectou (terminou ou caiu)
            e['conexao'].close()
            e['conexao'] = None
            return
        e['buffer'] += dados
    except BlockingIOError:
        pass
    except OSError:
        logic.endGame()
        e['conexao'] = None
        return
    # Vários pedidos por frame, até um que precise esperar frames.
    while b'\n' in e['buffer'] and e['adiado'] is None:
        linha, e['buffer'] = e['buffer'].split(b'\n', 1)
        resposta = atender(linha.decode('utf-8'))
        if resposta is not None:
            responder(resposta)
