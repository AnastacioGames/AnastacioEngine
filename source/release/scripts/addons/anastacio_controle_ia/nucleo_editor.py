"""Núcleo do servidor do editor: deixa o MCP do criador controlar o editor da Anastacio Engine por TCP local.

Usado de dois jeitos: pelo servidor_editor.py (o MCP abre o editor com --python) e pelo complemento
"Controle por IA" (o usuário liga num editor já aberto). Fonte única; o complemento leva uma cópia
(sincronizar_addon.py).

Protocolo: uma linha JSON por pedido, com "token"; uma linha JSON por resposta.
Segurança: só escuta em 127.0.0.1; `ler`/`definir` aceitam apenas caminhos bpy.* sem chamadas (caminhos.py);
`py` exige ANASTACIO_CRIADOR_PY=1 no ambiente do editor; no modo "observar" só comandos de leitura passam.
"""
import json, os, re, secrets, socket, sys, time, traceback
import bpy

try:
    from . import caminhos, sessao
except ImportError:  # carregado como módulo solto (servidor_editor.py)
    import caminhos, sessao

VERSAO = 2
PY_LIBERADO = os.environ.get('ANASTACIO_CRIADOR_PY') == '1'
LIMITE_OBJETOS = 500
# Comandos que só leem (ou gravam cópia de segurança). O resto exige o modo "controle".
SO_LEITURA = {'ping', 'cena', 'objeto', 'listar', 'descrever', 'ler', 'tela', 'backup'}

CONFIG = {'arquivo_sessao': None, 'observar': False, 'token': None, 'ligado': False}
ESTADO = {'escuta': None, 'conexao': None, 'buffer': b''}

class TrocouEditor(Exception):
    """O pedido volta para a fila e roda de novo no próximo tique."""


def contexto(editor=None):
    janela = bpy.context.window_manager.windows[0]
    tela = janela.screen
    area = None
    if editor:
        area = next((a for a in tela.areas if a.type == editor), None)
    if area is None:
        area = max(tela.areas, key=lambda a: a.width * a.height)
        if editor:
            area.type = editor
            raise TrocouEditor()
    regiao = next(r for r in area.regions if r.type == 'WINDOW')
    return {'window': janela, 'screen': tela, 'area': area, 'region': regiao,
            'scene': tela.scene, 'blend_data': bpy.data}


def so_janela(ctx):
    return {'window': ctx['window'], 'screen': ctx['screen']}


def texto(valor):
    if valor is None or isinstance(valor, (bool, int, float, str)):
        return valor
    if isinstance(valor, (set, frozenset)):
        return sorted(texto(v) for v in valor)
    if isinstance(valor, dict):
        return {str(k): texto(v) for k, v in valor.items()}
    if hasattr(valor, 'to_list'):
        return valor.to_list()
    if hasattr(valor, '__len__') and hasattr(valor, '__getitem__') and not hasattr(valor, 'bl_rna'):
        return [texto(v) for v in valor]
    if hasattr(valor, 'keys') and hasattr(valor, 'bl_rna') and hasattr(valor, 'values') and hasattr(valor, 'find'):
        return list(valor.keys())
    return repr(valor)


def operador(nome):
    modulo, funcao = nome.split('.', 1)
    return getattr(getattr(bpy.ops, modulo), funcao)


def propriedades(rna):
    saida = []
    for p in rna.properties:
        if p.identifier == 'rna_type':
            continue
        item = {'nome': p.identifier, 'tipo': p.type, 'descricao': p.description}
        if p.type == 'ENUM':
            item['opcoes'] = [e.identifier for e in p.enum_items]
        saida.append(item)
    return saida


def resumo_objeto(o, completo=False):
    d = {'nome': o.name, 'tipo': o.type, 'posicao': texto(o.location), 'rotacao': texto(o.rotation_euler),
         'escala': texto(o.scale), 'pai': o.parent.name if o.parent else None,
         'dados': o.data.name if getattr(o, 'data', None) else None}
    if completo:
        try:
            d['propriedades_de_jogo'] = [{'nome': p.name, 'tipo': p.type, 'valor': texto(p.value)}
                                         for p in o.game.properties]
        except Exception:
            d['propriedades_de_jogo'] = None
        d['materiais'] = [s.material.name for s in o.material_slots if s.material]
        d['filhos'] = [f.name for f in o.children]
    return d


def cmd_ping(_p):
    return {'versao': VERSAO, 'arquivo': bpy.data.filepath, 'py_liberado': PY_LIBERADO,
            'modo': 'observar' if CONFIG['observar'] else 'controle'}


def cmd_cena(_p):
    cena = bpy.context.scene
    objetos = list(cena.objects)
    return {'cena': cena.name, 'arquivo': bpy.data.filepath, 'total': len(objetos),
            'cenas': [c.name for c in bpy.data.scenes],
            'camera': cena.camera.name if cena.camera else None,
            'objetos': [resumo_objeto(o) for o in objetos[:LIMITE_OBJETOS]],
            'cortado': len(objetos) > LIMITE_OBJETOS}


def cmd_objeto(p):
    return resumo_objeto(bpy.data.objects[p['nome']], completo=True)


def cmd_listar(p):
    filtro = p.get('filtro', '')
    nomes = (m + '.' + f for m in dir(bpy.ops) for f in dir(getattr(bpy.ops, m)))
    return sorted(n for n in nomes if filtro in n)[:int(p.get('limite', 200))]


def cmd_descrever(p):
    rna = operador(p['nome']).get_rna_type()
    return {'nome': p['nome'], 'descricao': rna.description, 'propriedades': propriedades(rna)}


# Operadores que trocam o arquivo inteiro. Com o contexto montado antes (janela, tela, área), o editor
# fecha tudo ao carregar e o contexto passa a apontar para memória liberada: derruba o editor.
CARREGAM_ARQUIVO = {'wm.open_mainfile', 'wm.revert_mainfile', 'wm.read_homefile',
                    'wm.read_factory_settings', 'wm.recover_last_session', 'wm.recover_auto_save'}


def cmd_op(p):
    op = operador(p['nome'])
    if p['nome'] in CARREGAM_ARQUIVO:
        return {'estado': sorted(op('EXEC_DEFAULT', **p.get('args', {})))}
    ctx = contexto(p.get('editor'))
    if p.get('modo'):
        bpy.ops.object.mode_set(ctx, mode=p['modo'])
    if not op.poll(ctx):
        return {'estado': 'sem_contexto'}
    return {'estado': sorted(op(ctx, 'EXEC_DEFAULT', **p.get('args', {})))}


def cmd_ler(p):
    return texto(caminhos.ler(p['caminho'], bpy))


def cmd_definir(p):
    return texto(caminhos.definir(p['caminho'], p['valor'], bpy))


def cmd_py(p):
    if not PY_LIBERADO:
        raise PermissionError('py está desligado: defina ANASTACIO_CRIADOR_PY=1 para o MCP liberar código livre')
    espaco = {'bpy': bpy, 'contexto': contexto, 'resultado': None}
    exec(p['codigo'], espaco)
    return texto(espaco['resultado'])


def cmd_backup(_p):
    """Grava uma cópia do projeto em <projeto>.backups/ sem trocar o arquivo aberto."""
    atual = bpy.data.filepath
    if not atual:
        return {'backup': None, 'aviso': 'projeto ainda não foi salvo; salve antes de a IA editar'}
    pasta = os.path.splitext(atual)[0] + '.backups'
    os.makedirs(pasta, exist_ok=True)
    destino = os.path.join(pasta, time.strftime('%Y%m%d-%H%M%S') + os.path.splitext(atual)[1])
    bpy.ops.wm.save_as_mainfile(filepath=destino, copy=True)
    return {'backup': destino}


def cmd_salvar(_p):
    if not bpy.data.filepath:
        raise ValueError('projeto sem nome: salve pelo editor uma primeira vez')
    bpy.ops.wm.save_mainfile()
    return bpy.data.filepath


def cmd_tela(p):
    ctx = so_janela(contexto(p.get('editor')))
    bpy.ops.wm.redraw_timer(ctx, type='DRAW_WIN_SWAP', iterations=1)
    bpy.ops.screen.screenshot(ctx, filepath=p['arquivo'], full=True)
    return p['arquivo']


def cmd_evento(p):
    janela = bpy.context.window_manager.windows[0]
    janela.event_simulate(p['tipo'], p['valor'], p['x'], janela.height - 1 - p['y'],
                          shift=p.get('shift', False), ctrl=p.get('ctrl', False),
                          alt=p.get('alt', False), text=p.get('texto', ''))
    return True


def cmd_fechar(_p):
    os._exit(0)  # sem wm.quit: não grava quit.blend nem mexe no projeto


COMANDOS = {n[4:]: f for n, f in globals().items() if n.startswith('cmd_')}


def atender(linha):
    try:
        pedido = json.loads(linha)
        if pedido.get('token') != CONFIG['token']:
            return {'ok': False, 'erro': 'token inválido'}
        if CONFIG['observar'] and pedido['cmd'] not in SO_LEITURA:
            return {'ok': False, 'erro': 'o editor está no modo "só observar": peça ao usuário para clicar em '
                    '"Liberar edição" em Controle por IA (barra superior ou Preferências > Add-ons)'}
        return {'ok': True, 'resultado': COMANDOS[pedido['cmd']](pedido)}
    except TrocouEditor:
        return None
    except Exception as erro:
        return {'ok': False, 'erro': str(erro), 'traceback': traceback.format_exc()}


def escuta():
    if ESTADO['escuta'] is None:
        s = socket.socket()
        s.bind(('127.0.0.1', 0))
        s.listen(4)
        s.setblocking(False)
        ESTADO['escuta'] = s
        sessao.escrever(CONFIG['arquivo_sessao'], {'porta': s.getsockname()[1], 'token': CONFIG['token'],
                                                    'pid': os.getpid(), 'versao': VERSAO})
    return ESTADO['escuta']


def porta():
    return ESTADO['escuta'].getsockname()[1] if ESTADO['escuta'] else None


def conectado():
    return ESTADO['conexao'] is not None


def ligar(arquivo_sessao, observar=False):
    """Começa a escutar. Recusa se outro editor vivo já usa o arquivo de sessão."""
    if CONFIG['ligado']:
        return
    outro = sessao.ler(arquivo_sessao)
    if outro and outro.get('pid') != os.getpid():
        raise RuntimeError('já há outro editor com o controle por IA ligado (pid %s); desligue lá primeiro' % outro['pid'])
    CONFIG.update(arquivo_sessao=str(arquivo_sessao), observar=observar, token=secrets.token_hex(16), ligado=True)
    escuta()


def desligar():
    """Fecha a conexão e o socket e apaga o arquivo de sessão (só se for nosso)."""
    for chave in ('conexao', 'escuta'):
        if ESTADO[chave] is not None:
            try:
                ESTADO[chave].close()
            except OSError:
                pass
            ESTADO[chave] = None
    ESTADO['buffer'] = b''
    if CONFIG['arquivo_sessao']:
        sessao.apagar(CONFIG['arquivo_sessao'], so_se_pid=os.getpid())
    CONFIG['ligado'] = False


def tique():
    e = ESTADO
    if not CONFIG['ligado']:
        return
    if e['conexao'] is None:
        try:
            e['conexao'], _ = escuta().accept()
            e['conexao'].setblocking(False)
            e['buffer'] = b''
        except BlockingIOError:
            return
    try:
        dados = e['conexao'].recv(1 << 20)
        if not dados:
            e['conexao'].close()
            e['conexao'] = None
            return
        e['buffer'] += dados
    except BlockingIOError:
        pass
    except OSError:
        e['conexao'] = None
        return
    if b'\n' in e['buffer']:
        linha, resto = e['buffer'].split(b'\n', 1)
        resposta = atender(linha.decode('utf-8'))
        if resposta is not None and e['conexao'] is not None:
            e['buffer'] = resto
            e['conexao'].setblocking(True)
            e['conexao'].sendall((json.dumps(resposta) + '\n').encode('utf-8'))
            e['conexao'].setblocking(False)


class ANASTACIO_OT_servidor_criador(bpy.types.Operator):
    """Laço modal que atende o MCP enquanto CONFIG['ligado']."""
    bl_idname = 'wm.anastacio_servidor_criador'
    bl_label = 'Controle por IA (MCP do criador)'

    def invoke(self, context, _event):
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.02, context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, evento):
        if not CONFIG['ligado']:
            context.window_manager.event_timer_remove(self._timer)
            return {'FINISHED'}
        if evento.type == 'TIMER':
            tique()
        return {'PASS_THROUGH'}


def iniciar_modal():
    bpy.ops.wm.anastacio_servidor_criador(contexto(), 'INVOKE_DEFAULT')


def registrar():
    bpy.utils.register_class(ANASTACIO_OT_servidor_criador)


def desregistrar():
    desligar()
    bpy.utils.unregister_class(ANASTACIO_OT_servidor_criador)
