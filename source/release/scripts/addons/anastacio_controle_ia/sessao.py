"""Arquivo de sessão do editor (porta, token, pid), compartilhado pelo MCP, pelo núcleo do editor e pelo complemento.

Fonte única: tools/criador/ no repo anastacio-docs. O complemento da engine leva uma cópia (sincronizar_addon.py).
Só biblioteca padrão: roda dentro do Python do editor e no do MCP.
"""
import json
import os
import sys
from pathlib import Path


def pasta_usuario():
    """Pasta de estado do usuário: o complemento escreve aqui e o MCP procura aqui."""
    if os.environ.get('ANASTACIO_CRIADOR_SESSAO_DIR'):  # testes automáticos não pisam na sessão real
        return Path(os.environ['ANASTACIO_CRIADOR_SESSAO_DIR'])
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local') / 'AnastacioEngine'
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support' / 'AnastacioEngine'
    else:
        base = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local' / 'state') / 'anastacio-engine'
    return base / 'criador'


def sessao_usuario():
    return pasta_usuario() / 'sessao_editor.json'


def pid_vivo(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    if sys.platform == 'win32':
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.OpenProcess.restype = ctypes.c_void_p
        h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        codigo = ctypes.c_ulong()
        ok = k32.GetExitCodeProcess(ctypes.c_void_p(h), ctypes.byref(codigo))
        k32.CloseHandle(ctypes.c_void_p(h))
        return bool(ok) and codigo.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def nome_processo(pid):
    """Nome do executável do processo (minúsculo, sem pasta) ou None se não der para saber."""
    try:
        if sys.platform == 'win32':
            import ctypes
            k32 = ctypes.windll.kernel32
            k32.OpenProcess.restype = ctypes.c_void_p
            h = k32.OpenProcess(0x1000, False, pid)
            if not h:
                return None
            buf = ctypes.create_unicode_buffer(1024)
            tam = ctypes.c_ulong(len(buf))
            ok = k32.QueryFullProcessImageNameW(ctypes.c_void_p(h), 0, buf, ctypes.byref(tam))
            k32.CloseHandle(ctypes.c_void_p(h))
            return os.path.basename(buf.value).lower() if ok else None
        return os.path.basename(os.readlink('/proc/%d/exe' % pid)).lower()
    except (OSError, ValueError, AttributeError):
        return None


def ler(arquivo):
    """Conteúdo da sessão se o arquivo existe e o processo dono ainda está vivo; senão None.

    O pid pode ser reaproveitado por outro programa depois de uma queda: se a sessão guardou o nome do
    executável e o processo de hoje tem outro nome, o arquivo é velho."""
    try:
        dados = json.loads(Path(arquivo).read_text())
    except (OSError, ValueError):
        return None
    if not pid_vivo(dados.get('pid')):
        return None
    esperado, atual = dados.get('programa'), nome_processo(dados['pid'])
    if esperado and atual and esperado != atual:
        return None
    return dados


def escrever(arquivo, dados):
    """Grava de forma atômica, só legível pelo dono (no Windows a pasta do usuário já é privada)."""
    arquivo = Path(arquivo)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    tmp = arquivo.with_name(arquivo.name + '.tmp')
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(dados, f)
    os.replace(str(tmp), str(arquivo))


def apagar(arquivo, so_se_pid=None):
    try:
        if so_se_pid is not None and json.loads(Path(arquivo).read_text()).get('pid') != so_se_pid:
            return
        Path(arquivo).unlink()
    except (OSError, ValueError):
        pass
