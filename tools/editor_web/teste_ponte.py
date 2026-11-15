"""Teste da ponte ao vivo, sem navegador (rodar com o Python do sistema).

python tools/editor_web/teste_ponte.py [--modelo D:/AnastacioEditorWeb/prototipo/modelo.html]
Sobe a engine em -b com ponte.py --teste numa porta livre e fala WebSocket cru com ela.
"""
import base64, json, os, re, socket, subprocess, sys, threading, time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
EXE = RAIZ / 'build' / 'bin' / 'AnastacioEngine.exe'
MODELO = sys.argv[sys.argv.index('--modelo') + 1] if '--modelo' in sys.argv else r'D:\AnastacioEditorWeb\prototipo\modelo.html'

falhas = []


def conferir(nome, cond, extra=''):
    print(('OK     ' if cond else 'FALHOU ') + nome + ('  ' + str(extra) if extra else ''))
    if not cond:
        falhas.append(nome)


def livre():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


class WS:
    def __init__(self, porta, token, origem=None, caminho=None):
        self.s = socket.create_connection(('127.0.0.1', porta), timeout=20)
        chave = base64.b64encode(os.urandom(16)).decode()
        origem = origem or 'http://127.0.0.1:%d' % porta
        caminho = caminho or '/ws?t=' + token
        self.s.sendall(('GET %s HTTP/1.1\r\nHost: 127.0.0.1:%d\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                        'Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\nOrigin: %s\r\n\r\n'
                        % (caminho, porta, chave, origem)).encode())
        cab = b''
        while b'\r\n\r\n' not in cab:
            d = self.s.recv(4096)
            if not d:
                break
            cab += d
        self.status = cab.split(b'\r\n', 1)[0].decode()
        self.resto = bytearray(cab.split(b'\r\n\r\n', 1)[1]) if b'\r\n\r\n' in cab else bytearray()

    def envia(self, obj=None, op=1, dados=None, mascarar=True, fin=True):
        dados = dados if dados is not None else json.dumps(obj).encode()
        n = len(dados)
        b0 = (0x80 if fin else 0) | op
        if n < 126:
            cab = bytes([b0, (0x80 if mascarar else 0) | n])
        elif n < 65536:
            cab = bytes([b0, (0x80 if mascarar else 0) | 126]) + n.to_bytes(2, 'big')
        else:
            cab = bytes([b0, (0x80 if mascarar else 0) | 127]) + n.to_bytes(8, 'big')
        if mascarar:
            m = os.urandom(4)
            dados = bytes(x ^ m[i % 4] for i, x in enumerate(dados))
            cab += m
        self.s.sendall(cab + dados)

    def _ler(self, n):
        while len(self.resto) < n:
            d = self.s.recv(65536)
            if not d:
                raise EOFError
            self.resto += d
        out = bytes(self.resto[:n])
        del self.resto[:n]
        return out

    def frame(self):
        a, b = self._ler(2)
        n = b & 0x7F
        if n == 126:
            n = int.from_bytes(self._ler(2), 'big')
        elif n == 127:
            n = int.from_bytes(self._ler(8), 'big')
        return a & 0x0F, self._ler(n)

    def msg(self):
        while True:
            op, d = self.frame()
            if op == 1:
                return json.loads(d)
            if op == 8:
                return {'tipo': 'close', 'codigo': int.from_bytes(d[:2], 'big') if d else None}

    def ate(self, cond, limite=40):
        for _ in range(limite):
            m = self.msg()
            if cond(m):
                return m
        raise AssertionError('mensagem esperada não chegou')


def achar(no, caminho):
    if isinstance(no, dict):
        if no.get('rna') and no['rna'].get('caminho') == caminho:
            return no
        for f in no.get('itens', []) + ([no['cabecalho']] if 'cabecalho' in no else []):
            r = achar(f, caminho)
            if r:
                return r


def valor(msg, painel, caminho):
    n = achar(msg['paineis'][painel]['arvore'], caminho)
    return n and n.get('valor')


def checar_js():
    import shutil, tempfile
    html = Path(MODELO).read_text(encoding='utf-8')
    js = re.search(r'<script>(.*)</script>', html, re.S).group(1)
    if not shutil.which('node'):
        print('AVISO  node não encontrado; sintaxe do JS não conferida')
        return
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / 'modelo.js'
        f.write_text(js, encoding='utf-8')
        r = subprocess.run(['node', '--check', str(f)], capture_output=True, text=True)
    conferir('node --check do script de modelo.html', r.returncode == 0, r.stderr.strip()[:300])


def main():
    checar_js()
    porta = livre()
    proc = subprocess.Popen([str(EXE), '-b', '--factory-startup', '--python', str(AQUI / 'ponte.py'), '--',
                             '--porta', str(porta), '--modelo', MODELO, '--teste'],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
    linhas = []
    pronto = threading.Event()
    url = {}

    def ler():
        for l in proc.stdout:
            linhas.append(l.rstrip())
            m = re.search(r'PRONTO (\S+)', l)
            if m:
                url['u'] = m.group(1)
                pronto.set()
    threading.Thread(target=ler, daemon=True).start()
    t0 = time.time()
    if not pronto.wait(60):
        proc.kill()
        print('\n'.join(linhas[-30:]))
        sys.exit('ponte não subiu')
    print('ponte no ar em %.1f s: %s' % (time.time() - t0, url['u']))
    token = url['u'].split('?t=')[1]

    try:
        rodar_testes(porta, token)
    finally:
        try:
            proc.wait(15)
        except subprocess.TimeoutExpired:
            proc.kill()
            falhas.append('engine não saiu com sair')
        conferir('engine saiu (código %s)' % proc.returncode, proc.returncode == 0)
        print('--- log da engine (ponte) ---')
        print('\n'.join(l for l in linhas if '[ponte]' in l or 'Error' in l or 'Traceback' in l))
    print('\n%d falha(s)' % len(falhas), falhas)
    sys.exit(1 if falhas else 0)


def rodar_testes(porta, token):
    # Página HTTP
    s = socket.create_connection(('127.0.0.1', porta), timeout=10)
    s.sendall(('GET /?t=%s HTTP/1.1\r\nHost: 127.0.0.1:%d\r\n\r\n' % (token, porta)).encode())
    corpo = b''
    while True:
        d = s.recv(65536)
        if not d:
            break
        corpo += d
    conferir('GET / com token -> 200 e painéis injetados', corpo.startswith(b'HTTP/1.1 200') and b'OBJECT_PT_transform' in corpo,
             '%d bytes' % len(corpo))
    conferir('GET / injeta a lista da cena', b'/*CENA*/' not in corpo and b'"nome": "Cube"' in corpo)
    s = socket.create_connection(('127.0.0.1', porta), timeout=10)
    s.sendall(('GET /?t=x HTTP/1.1\r\nHost: 127.0.0.1:%d\r\n\r\n' % porta).encode())
    conferir('GET / sem token -> 403', s.recv(100).startswith(b'HTTP/1.1 403'))
    s = socket.create_connection(('127.0.0.1', porta), timeout=10)
    s.sendall(('GET /?t=%s HTTP/1.1\r\nHost: evil.com:%d\r\n\r\n' % (token, porta)).encode())
    conferir('Host estranho (DNS rebinding) -> 421', s.recv(100).startswith(b'HTTP/1.1 421'))
    s = socket.create_connection(('127.0.0.1', porta), timeout=10)
    s.sendall(b'GET / HTTP/1.1\r\nX: ' + b'a' * 9000)
    conferir('handshake > 8 KB -> 431', s.recv(100).startswith(b'HTTP/1.1 431'))

    # Rejeições de handshake
    conferir('WS token errado -> 403', WS(porta, 'errado').status.startswith('HTTP/1.1 403'))
    conferir('WS Origin errado -> 403', WS(porta, token, origem='http://evil.com').status.startswith('HTTP/1.1 403'))
    conferir('WS Origin localhost (não exato) -> 403',
             WS(porta, token, origem='http://localhost:%d' % porta).status.startswith('HTTP/1.1 403'))

    ws = WS(porta, token)
    conferir('WS handshake ok', ws.status.startswith('HTTP/1.1 101'), ws.status)
    outro = WS(porta, token)

    ws.envia({'cmd': 'ativar', 'objeto': 'Cube'})
    r = ws.ate(lambda m: m.get('tipo') in ('ok', 'erro'))
    conferir('ativar Cube', r.get('tipo') == 'ok', r)
    ws.ate(lambda m: m.get('tipo') == 'paineis')  # difusão após ativar
    t = time.time()
    ws.envia({'cmd': 'paineis'})
    p = ws.ate(lambda m: m.get('tipo') == 'paineis')
    ms = (time.time() - t) * 1000
    conferir('paineis: %d painéis, objeto %s, rev %d (%.0f ms)' % (len(p['paineis']), p['objeto'], p['rev'], ms),
             'OBJECT_PT_transform' in p['paineis'] and p['objeto'] == 'Cube')
    rev0 = p['rev']
    cena = p.get('cena') or []
    conferir('cena: lista de objetos com campos do Outliner (%d)' % len(cena),
             cena and all(set(o) >= {'nome', 'tipo', 'pai', 'ativo', 'selecionado'} for o in cena))
    conferir('cena: mesmos objetos que "objetos"', sorted(o['nome'] for o in cena) == sorted(p['objetos']))
    vistos = set()
    ordem_ok = True
    for o in cena:
        ordem_ok &= o['pai'] is None or o['pai'] in vistos
        vistos.add(o['nome'])
    conferir('cena: ordem hierárquica (pai antes do filho)', ordem_ok)
    conferir('cena: só Cube ativo e selecionado',
             [o['nome'] for o in cena if o['ativo']] == ['Cube'] and [o['nome'] for o in cena if o['selecionado']] == ['Cube'])
    conferir('cena: tipo MESH no Cube', any(o['nome'] == 'Cube' and o['tipo'] == 'MESH' for o in cena))
    conferir('location inicial', valor(p, 'OBJECT_PT_transform', 'location') == [0.0, 0.0, 0.0],
             valor(p, 'OBJECT_PT_transform', 'location'))
    rna = achar(p['paineis']['OBJECT_PT_transform']['arvore'], 'location')['rna']

    # Escrever location[0] = 2.5 (mensagem fragmentada em 2 frames)
    dados = json.dumps({'cmd': 'escrever', 'id': 1, 'rna': rna, 'valor': 2.5, 'indice': 0}).encode()
    ws.envia(op=1, dados=dados[:10], fin=False)
    ws.envia(op=9, dados=b'oi')  # ping no meio da fragmentação
    ws.envia(op=0, dados=dados[10:], fin=True)
    pong = ws.frame()
    conferir('pong ecoa o ping', pong == (10, b'oi'), pong[0])
    r = ws.msg()
    conferir('escrever ok (fragmentado)', r.get('tipo') == 'ok' and r.get('valor') == [2.5, 0.0, 0.0], r)
    conferir('undo_push feito', r.get('undo_push') is True)
    p = ws.ate(lambda m: m.get('tipo') == 'paineis')
    conferir('painéis re-enviados rev+1 com valor novo', p['rev'] == rev0 + 1 and
             valor(p, 'OBJECT_PT_transform', 'location') == [2.5, 0.0, 0.0], (p['rev'], valor(p, 'OBJECT_PT_transform', 'location')))
    p2 = outro.ate(lambda m: m.get('tipo') == 'paineis' and m['rev'] >= p['rev'])
    conferir('outro cliente também recebe', p2['rev'] == p['rev'])

    def erro(msg, nome, trecho=''):
        ws.envia(msg)
        r = ws.ate(lambda m: m.get('tipo') in ('ok', 'erro'))
        conferir(nome, r.get('tipo') == 'erro' and trecho in r.get('erro', ''), r.get('erro'))

    erro({'cmd': 'operador', 'op': 'wm.quit_blender'}, 'operador fora da whitelist', 'fora da lista')
    erro({'cmd': 'operador', 'op': 'ed.undo_push'}, 'operador parecido fora da whitelist', 'fora da lista')
    erro({'cmd': 'escrever', 'rna': rna, 'valor': 'abc', 'indice': 0}, 'valor string em FLOAT', 'tipo errado')
    erro({'cmd': 'escrever', 'rna': rna, 'valor': True, 'indice': 0}, 'valor bool em FLOAT', 'tipo errado')
    erro({'cmd': 'escrever', 'rna': rna, 'valor': 1.0, 'indice': 3}, 'índice fora', 'fora do array')
    erro({'cmd': 'escrever', 'rna': rna, 'valor': [1, 2]}, 'lista de tamanho errado', 'lista de 3')
    erro({'cmd': 'escrever', 'rna': dict(rna, caminho='type'), 'valor': 'MESH'}, 'prop só leitura (Object.type)', 'só leitura')
    erro({'cmd': 'escrever', 'rna': dict(rna, caminho='rotation_mode'), 'valor': 'NAOEXISTE'}, 'enum inválida', 'tipo errado')
    erro({'cmd': 'escrever', 'rna': dict(rna, caminho='location.__class__'), 'valor': 1}, 'caminho malicioso', '')
    erro({'cmd': 'escrever', 'rna': dict(rna, id_tipo='Text'), 'valor': 1}, 'bloco Text proibido', 'não permitido')
    erro({'cmd': 'sair2'}, 'comando desconhecido', 'desconhecido')
    erro({'cmd': 'ativar', 'objeto': 'Nada'}, 'ativar objeto inexistente', 'não está')

    # enum válida
    ws.envia({'cmd': 'escrever', 'rna': dict(rna, caminho='rotation_mode'), 'valor': 'QUATERNION'})
    r = ws.ate(lambda m: m.get('tipo') in ('ok', 'erro'))
    p = ws.ate(lambda m: m.get('tipo') == 'paineis')
    conferir('enum QUATERNION aceita e painel troca para rotation_quaternion',
             r['tipo'] == 'ok' and achar(p['paineis']['OBJECT_PT_transform']['arvore'], 'rotation_quaternion') is not None)

    # Undo: volta rotation_mode? e depois location?
    ws.envia({'cmd': 'operador', 'op': 'ed.undo'})
    r = ws.ate(lambda m: m.get('tipo') in ('ok', 'erro'))
    if r['tipo'] == 'ok':
        p = ws.ate(lambda m: m.get('tipo') == 'paineis')
        modo = achar(p['paineis']['OBJECT_PT_transform']['arvore'], 'rotation_mode')
        conferir('ed.undo em -b desfaz rotation_mode', modo and modo.get('valor') == 'XYZ', modo and modo.get('valor'))
        ws.envia({'cmd': 'operador', 'op': 'ed.redo'})
        r2 = ws.ate(lambda m: m.get('tipo') in ('ok', 'erro'))
        p = ws.ate(lambda m: m.get('tipo') == 'paineis') if r2['tipo'] == 'ok' else p
        modo = achar(p['paineis']['OBJECT_PT_transform']['arvore'], 'rotation_mode')
        conferir('ed.redo em -b refaz', r2['tipo'] == 'ok' and modo.get('valor') == 'QUATERNION', (r2, modo.get('valor')))
    else:
        print('LIMITACAO ed.undo em -b:', r.get('erro'))

    # Operador da whitelist: location_clear
    ws.envia({'cmd': 'operador', 'op': 'object.location_clear'})
    r = ws.ate(lambda m: m.get('tipo') in ('ok', 'erro'))
    if r['tipo'] == 'ok':
        p = ws.ate(lambda m: m.get('tipo') == 'paineis')
        conferir('object.location_clear zera location', valor(p, 'OBJECT_PT_transform', 'location') == [0.0, 0.0, 0.0],
                 valor(p, 'OBJECT_PT_transform', 'location'))
    else:
        print('LIMITACAO object.location_clear em -b:', r.get('erro'))

    # Ativar outro objeto da cena
    outro_obj = next(n for n in p['objetos'] if n != 'Cube')
    ws.envia({'cmd': 'ativar', 'objeto': outro_obj})
    r = ws.ate(lambda m: m.get('tipo') in ('ok', 'erro'))
    p = ws.ate(lambda m: m.get('tipo') == 'paineis')
    conferir('ativar %s troca painéis (%d)' % (outro_obj, len(p['paineis'])), r['tipo'] == 'ok' and p['objeto'] == outro_obj)
    conferir('cena acompanha ativar (ativo/selecionado = %s)' % outro_obj,
             [o['nome'] for o in p['cena'] if o['ativo']] == [outro_obj] and
             [o['nome'] for o in p['cena'] if o['selecionado']] == [outro_obj])

    testes_viewport(ws)

    # Frame sem máscara -> close 1002
    ruim = WS(porta, token)
    ruim.envia({'cmd': 'paineis'}, mascarar=False)
    m = ruim.msg()
    conferir('frame sem máscara -> close 1002', m == {'tipo': 'close', 'codigo': 1002}, m)
    # Mensagem > 1 MB -> close 1009 (só o cabeçalho anuncia o tamanho)
    gr = WS(porta, token)
    gr.s.sendall(bytes([0x81, 0x80 | 127]) + (2 * 1024 * 1024).to_bytes(8, 'big') + b'\0\0\0\0')
    m = gr.msg()
    conferir('mensagem > 1 MB -> close 1009', m == {'tipo': 'close', 'codigo': 1009}, m)
    # Close normal
    outro.envia(op=8, dados=(1000).to_bytes(2, 'big'))
    m = outro.ate(lambda m: m.get('tipo') == 'close', 100)
    conferir('close do cliente ecoado', m.get('codigo') == 1000, m)

    ws.envia({'cmd': 'sair'})
    r = ws.ate(lambda m: m.get('tipo') in ('ok', 'erro'))
    conferir('sair (--teste)', r['tipo'] == 'ok')


def retrato(ws):
    """Pede 'malhas' e junta as partes até a que tem fim=True."""
    ws.envia({'cmd': 'malhas'})
    malhas, ultima, partes = {}, None, 0
    while True:
        m = ws.ate(lambda m: m.get('tipo') == 'malhas' and m.get('completo'))
        malhas.update(m['malhas'])
        partes += 1
        if m.get('fim'):
            return malhas, m, partes


def resposta(ws):
    return ws.ate(lambda m: m.get('tipo') in ('ok', 'erro'))


def testes_viewport(ws):
    import struct
    malhas, fim, partes = retrato(ws)
    objs = {o['nome']: o for o in fim['objetos']}
    cubo = objs.get('Cube')
    conferir('malhas: retrato com objetos e malhas (%d objetos, %d malhas, %d parte(s))' % (len(objs), len(malhas), partes),
             cubo is not None and cubo['malha_id'] in malhas)
    mc = malhas[cubo['malha_id']]
    nidx = len(base64.b64decode(mc['i'])) // 4
    nv = len(base64.b64decode(mc['v'])) // 12
    idx = struct.unpack('<%dI' % nidx, base64.b64decode(mc['i']))
    conferir('Cube com 12 triângulos (%d índices, %d vértices)' % (nidx, nv),
             mc['tri'] == 12 and nidx == 36 and max(idx) < nv and len(base64.b64decode(mc['n'])) == nv * 12)
    conferir('matriz 4x4 com 16 números e cor RGB', len(cubo['matriz']) == 16 and len(cubo['cor']) == 3)
    sem = [o for o in fim['objetos'] if o['tipo'] in ('LAMP', 'CAMERA', 'EMPTY')]
    conferir('lâmpada/câmera sem malha (%s)' % ', '.join(o['nome'] for o in sem),
             sem and all(o['malha_id'] is None for o in sem))
    hashes = {k: m['h'] for k, m in malhas.items()}
    time.sleep(1.2)  # passa por 2 ciclos de detecção
    ws.envia({'cmd': 'paineis'})
    vistos = []
    ws.ate(lambda m: vistos.append(m.get('tipo')) or m.get('tipo') == 'paineis')
    malhas2, _, _ = retrato(ws)
    conferir('hash estável (nada reenviado sem mudança)', 'malhas' not in vistos and 'transformacoes' not in vistos
             and {k: m['h'] for k, m in malhas2.items()} == hashes, vistos)

    # escrever location -> só 'transformacoes' (leve), não 'malhas'
    rna = {'id_tipo': 'Object', 'id': 'Cube', 'caminho': 'location'}
    ws.envia({'cmd': 'escrever', 'rna': rna, 'valor': [1.0, 2.0, 3.0]})
    r = resposta(ws)
    m = ws.ate(lambda m: m.get('tipo') in ('malhas', 'transformacoes'))
    t = next((o for o in m.get('objetos', []) if o['nome'] == 'Cube'), None)
    conferir('escrever location -> transformacoes leve com a matriz nova',
             r['tipo'] == 'ok' and m['tipo'] == 'transformacoes' and t and [round(x - y - z, 5) for x, y, z in zip(t['matriz'][12:15], cubo['matriz'][12:15], [1.0, 2.0, 3.0])] == [0, 0, 0]
             and 'malhas' not in m, (m.get('tipo'), t and t['matriz'][12:15], cubo['loc']))

    # selecionar com adicionar (Shift+clique)
    def sel(nome, adicionar=False):
        ws.envia({'cmd': 'selecionar', 'nome': nome, 'adicionar': adicionar})
        r = resposta(ws)
        p = ws.ate(lambda m: m.get('tipo') == 'paineis')
        return r, sorted(o['nome'] for o in p['cena'] if o['selecionado']), p['objeto']
    r, s, a = sel('Cube')
    conferir('selecionar Cube', r['tipo'] == 'ok' and s == ['Cube'] and a == 'Cube', (s, a))
    r, s, a = sel('Camera', True)
    conferir('selecionar Camera com adicionar: Cube+Camera, ativo Camera', s == ['Camera', 'Cube'] and a == 'Camera', (s, a))
    r, s, a = sel('Camera', True)
    conferir('Shift+clique no ativo tira da seleção', s == ['Cube'], s)
    r, s, a = sel(None)
    conferir('clique no vazio limpa a seleção', r['tipo'] == 'ok' and s == [], s)
    ws.envia({'cmd': 'selecionar', 'nome': 'Cube', 'adicionar': 'sim'})
    conferir('selecionar com adicionar não-bool -> erro', resposta(ws)['tipo'] == 'erro')

    # Arrasto do gizmo: escritas sem_undo + final com undo_push = um passo só de undo
    sel('Cube')
    pushes = []
    for x in (1.5, 2.0, 2.5):
        ws.envia({'cmd': 'escrever', 'rna': rna, 'valor': x, 'indice': 0, 'sem_undo': True})
        pushes.append(resposta(ws).get('undo_push'))
    ws.envia({'cmd': 'escrever', 'rna': rna, 'valor': 3.0, 'indice': 0})
    final = resposta(ws)
    conferir('arrasto: meio sem undo_push, final com', pushes == [False] * 3 and final.get('undo_push') is True,
             (pushes, final.get('undo_push')))
    ws.envia({'cmd': 'operador', 'op': 'ed.undo'})
    r = resposta(ws)
    _, fim, _ = retrato(ws)
    loc = next(o['loc'] for o in fim['objetos'] if o['nome'] == 'Cube')
    conferir('um ed.undo desfaz o arrasto inteiro (location volta a [1,2,3])', r['tipo'] == 'ok' and loc == [1.0, 2.0, 3.0],
             (r.get('erro'), loc))


if __name__ == '__main__':
    main()
