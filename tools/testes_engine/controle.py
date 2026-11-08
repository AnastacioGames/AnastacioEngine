#!/usr/bin/env python3
"""Controla o editor da Anastacio Engine pela linha de comando ou como módulo.

  python tools/testes_engine/controle.py abrir [cena.range] [--visivel]
  python tools/testes_engine/controle.py listar ops mesh
  python tools/testes_engine/controle.py descrever mesh.primitive_cube_add
  python tools/testes_engine/controle.py op mesh.primitive_cube_add "{\"size\": 3}" --editor VIEW_3D
  python tools/testes_engine/controle.py ler "bpy.context.object.location"
  python tools/testes_engine/controle.py definir "bpy.context.object.name" "\"Teste\""
  python tools/testes_engine/controle.py py "resultado = len(bpy.data.objects)"
  python tools/testes_engine/controle.py tela D:/print.png --editor LOGIC_EDITOR
  python tools/testes_engine/controle.py clicar 425 707        (coordenadas do print)
  python tools/testes_engine/controle.py tecla A 800 400        (tecla com o mouse nesse ponto)
  python tools/testes_engine/controle.py fechar

Por padrão o editor abre num desktop Windows separado, invisível e com config própria.
"""
import argparse, ctypes, json, os, socket, subprocess, sys, tempfile, time
from ctypes import wintypes
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
AQUI = Path(__file__).resolve().parent
EDITOR = RAIZ / 'build/bin/AnastacioEngine.exe'
PASTA = Path(os.environ.get('ANASTACIO_CONTROLE_PASTA', RAIZ / 'artifacts/testes/controle'))
SESSAO = PASTA / 'sessao.json'
RUNTIME = RAIZ / 'build/bin/AnastacioRuntime.exe'
SESSAO_JOGO = PASTA / 'sessao_jogo.json'
DESKTOP = 'AnastacioTestes'


class STARTUPINFO(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('lpReserved', wintypes.LPWSTR), ('lpDesktop', wintypes.LPWSTR),
                ('lpTitle', wintypes.LPWSTR), ('dwX', wintypes.DWORD), ('dwY', wintypes.DWORD),
                ('dwXSize', wintypes.DWORD), ('dwYSize', wintypes.DWORD), ('dwXCountChars', wintypes.DWORD),
                ('dwYCountChars', wintypes.DWORD), ('dwFillAttribute', wintypes.DWORD),
                ('dwFlags', wintypes.DWORD), ('wShowWindow', wintypes.WORD), ('cbReserved2', wintypes.WORD),
                ('lpReserved2', ctypes.c_void_p), ('hStdInput', wintypes.HANDLE),
                ('hStdOutput', wintypes.HANDLE), ('hStdError', wintypes.HANDLE)]


class PROCINFO(ctypes.Structure):
    _fields_ = [('hProcess', wintypes.HANDLE), ('hThread', wintypes.HANDLE),
                ('dwProcessId', wintypes.DWORD), ('dwThreadId', wintypes.DWORD)]


def iniciar_invisivel(args, log, env):
    """Inicia no desktop separado, com a saída indo para `log`."""
    u32 = ctypes.WinDLL('user32', use_last_error=True)
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    u32.CreateDesktopW.restype = wintypes.HANDLE
    u32.CreateDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p, wintypes.DWORD,
                                   wintypes.DWORD, ctypes.c_void_p]
    if not u32.CreateDesktopW(DESKTOP, None, None, 0, 0x10000000, None):
        raise ctypes.WinError(ctypes.get_last_error())
    linha = 'cmd /c "%s > "%s" 2>&1"' % (subprocess.list2cmdline(args), log)
    si = STARTUPINFO(cb=ctypes.sizeof(STARTUPINFO), lpDesktop=DESKTOP)
    pi = PROCINFO()
    bloco = ''.join('%s=%s\0' % kv for kv in env.items()) + '\0'
    if not k32.CreateProcessW(None, ctypes.create_unicode_buffer(linha), None, None, False, 0x08000400,
                              ctypes.create_unicode_buffer(bloco, len(bloco)), str(RAIZ),
                              ctypes.byref(si), ctypes.byref(pi)):
        raise ctypes.WinError(ctypes.get_last_error())
    return pi.dwProcessId


def rodando(pid):
    saida = subprocess.run(['tasklist', '/FI', 'PID eq %d' % pid, '/NH'], capture_output=True, text=True, errors='replace').stdout
    return str(pid) in saida


def encerrar(pid, espera=0):
    """Espera `pid` sair sozinho por `espera` segundos; se não sair, mata ele e os filhos."""
    limite = time.time() + espera
    while time.time() < limite:
        if not rodando(pid):
            return
        time.sleep(0.2)
    subprocess.run(['taskkill', '/T', '/F', '/PID', str(pid)], capture_output=True)


ultimo_pid = None  # processo invisível aberto por último (o `cmd` que segura o programa)


def abrir(cena=None, visivel=False, espera=60, args_extra=()):
    global ultimo_pid
    PASTA.mkdir(parents=True, exist_ok=True)
    SESSAO.unlink(missing_ok=True)
    config = Path(tempfile.mkdtemp(prefix='config_', dir=PASTA))
    env = dict(os.environ, ANASTACIO_EVENT_SIMULATE='1', BLENDER_USER_CONFIG=str(config), BLENDER_USER_SCRIPTS=str(config / 'scripts'),
               BLENDER_USER_DATAFILES=str(config / 'datafiles'))
    args = [str(EDITOR), '--factory-startup', '--window-geometry', '0', '0', '1904', '1000'] + list(args_extra) + ([cena] if cena else [])
    args += ['--python-exit-code', '1', '--python', str(AQUI / 'servidor.py'), '--', str(SESSAO)]
    log = PASTA / ('editor_%d.log' % int(time.time() * 1000))
    if visivel:
        subprocess.Popen(args, env=env, cwd=RAIZ, stdout=log.open('w'), stderr=subprocess.STDOUT)
    else:
        ultimo_pid = iniciar_invisivel(args, log, env)
    limite = time.time() + espera
    while time.time() < limite:
        if SESSAO.exists():
            return json.loads(SESSAO.read_text())
        time.sleep(0.2)
    if not visivel:
        encerrar(ultimo_pid)
    raise TimeoutError('o editor não respondeu; veja ' + str(log))


def abrir_jogo(arquivo, visivel=False, espera=90, largura=1280, altura=720, env_extra=None, exportado=False):
    """Roda o .range no AnastacioRuntime com o servidor_jogo.py; devolve um Jogo conectado."""
    global ultimo_pid
    PASTA.mkdir(parents=True, exist_ok=True)
    SESSAO_JOGO.unlink(missing_ok=True)
    env = dict(os.environ, RANGE_CONTROL_SCRIPT=str(AQUI / 'servidor_jogo.py'), RANGE_CONTROL_SESSION=str(SESSAO_JOGO),
               RANGE_NO_CRASH_DIALOG='1', **(env_extra or {}))
    # exportado: `arquivo` é o próprio .exe do jogo, com a cena embutida
    janela = ['-w', str(largura), str(altura), '0', '0']
    args = [str(arquivo)] + janela if exportado else [str(RUNTIME)] + janela + [str(Path(arquivo).resolve())]
    log = PASTA / ('jogo_%d.log' % int(time.time() * 1000))  # um por execução: um jogo preso segura o seu
    if visivel:
        proc = subprocess.Popen(args, env=env, cwd=RAIZ, stdout=log.open('w'), stderr=subprocess.STDOUT)
    else:
        proc = None
        ultimo_pid = iniciar_invisivel(args, log, env)
    limite = time.time() + espera
    while time.time() < limite:
        if SESSAO_JOGO.exists():
            return Jogo()
        if proc and proc.poll() is not None:
            break
        time.sleep(0.2)
    if proc:
        proc.kill()
    else:
        encerrar(ultimo_pid)  # senão o jogo preso fica rodando depois do teste
    raise TimeoutError('o jogo não respondeu; veja ' + str(log))


class Editor:
    """Conexão com o editor aberto. Qualquer comando do servidor vira um método."""
    ARQUIVO = SESSAO

    def __init__(self):
        self.sessao = json.loads(self.ARQUIVO.read_text())
        self.socket = socket.create_connection(('127.0.0.1', self.sessao['porta']), timeout=120)
        self.canal = self.socket.makefile('rw', encoding='utf-8')

    def pedir(self, cmd, **dados):
        self.canal.write(json.dumps(dict(dados, cmd=cmd, token=self.sessao['token'])) + '\n')
        self.canal.flush()
        linha = self.canal.readline()
        if not linha:
            raise ConnectionError('o editor fechou ou caiu durante: ' + cmd)
        return json.loads(linha)


class Jogo(Editor):
    """Conexão com o jogo rodando: py, estado, tecla, soltar, mouse, esperar, tela, fechar."""
    ARQUIVO = SESSAO_JOGO

    def __getattr__(self, cmd):
        def chamar(**dados):
            r = self.pedir(cmd, **dados)
            if not r['ok']:
                raise RuntimeError(r.get('traceback') or r['erro'])
            return r['resultado']
        return chamar

    def fechar(self):
        try:
            self.pedir('fechar')
        except (ConnectionError, OSError):
            pass


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument('comando')
    p.add_argument('valores', nargs='*')
    p.add_argument('--editor')
    p.add_argument('--modo')
    p.add_argument('--visivel', action='store_true')
    a = p.parse_args()
    v = a.valores
    if a.comando == 'abrir':
        print(abrir(v[0] if v else None, a.visivel))
        return
    dados = {}
    if a.editor:
        dados['editor'] = a.editor
    if a.comando == 'listar':
        dados.update(tipo=v[0] if v else 'ops', filtro=v[1] if len(v) > 1 else '')
    elif a.comando == 'descrever':
        dados['nome'] = v[0]
    elif a.comando == 'op':
        dados.update(nome=v[0], args=json.loads(v[1]) if len(v) > 1 else {})
        if a.modo:
            dados['modo'] = a.modo
    elif a.comando == 'ler':
        dados['caminho'] = v[0]
    elif a.comando == 'definir':
        dados.update(caminho=v[0], valor=json.loads(v[1]))
    elif a.comando == 'py':
        dados['codigo'] = v[0]
    elif a.comando == 'tela':
        dados['arquivo'] = str(Path(v[0]).resolve())
    editor = Editor()
    if a.comando in ('clicar', 'mover'):
        x, y = int(v[0]), int(v[1])
        botao = v[2] if len(v) > 2 else 'LEFTMOUSE'
        passos = [('MOUSEMOVE', 'NOTHING')]
        if a.comando == 'clicar':
            passos += [(botao, 'PRESS'), (botao, 'RELEASE')]
        for tipo, valor in passos:
            resposta = editor.pedir('evento', tipo=tipo, valor=valor, x=x, y=y)
            time.sleep(0.15)  # tempo do editor tratar e desenhar o estado de hover
        print(json.dumps(resposta))
        sys.exit(0 if resposta['ok'] else 1)
    if a.comando == 'tecla':
        for valor in ('PRESS', 'RELEASE'):
            resposta = editor.pedir('evento', tipo=v[0], valor=valor, x=int(v[1]) if len(v) > 1 else 0,
                                    y=int(v[2]) if len(v) > 2 else 0, texto=v[3] if len(v) > 3 else '')
        print(json.dumps(resposta))
        sys.exit(0 if resposta['ok'] else 1)
    if a.comando == 'fechar':
        editor.canal.write(json.dumps({'cmd': 'fechar', 'token': editor.sessao['token']}) + '\n')
        editor.canal.flush()
        print('fechado')
        return
    resposta = editor.pedir(a.comando, **dados)
    print(json.dumps(resposta, ensure_ascii=False, indent=1))
    sys.exit(0 if resposta['ok'] else 1)


if __name__ == '__main__':
    main()
