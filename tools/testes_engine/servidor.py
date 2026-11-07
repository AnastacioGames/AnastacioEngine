"""Roda dentro do editor e deixa qualquer programa controlá-lo por TCP local.

Nada aqui lista operadores ou painéis à mão: tudo vem do RNA, então o que for
criado na engine fica controlável sem mudar este arquivo.
Protocolo: uma linha JSON por pedido, com "token"; uma linha JSON por resposta.
"""
import json, os, secrets, socket, sys, traceback
import bpy

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ARQUIVO_SESSAO = argv[0]
bpy.context.user_preferences.view.show_splash = False  # senão ela cobre os prints
TOKEN = secrets.token_hex(16)


class TrocouEditor(Exception):
    """O pedido volta para a fila e roda de novo no próximo tique."""


def contexto(editor=None):
    """Override para o editor pedido; troca a maior área só quando é preciso."""
    janela = bpy.context.window_manager.windows[0]
    tela = janela.screen
    area = None
    if editor:
        area = next((a for a in tela.areas if a.type == editor), None)
    if area is None:
        area = max(tela.areas, key=lambda a: a.width * a.height)
        if editor:
            area.type = editor
            raise TrocouEditor()  # só vale depois de o laço principal rodar
    regiao = next(r for r in area.regions if r.type == 'WINDOW')
    return {'window': janela, 'screen': tela, 'area': area, 'region': regiao,
            'scene': tela.scene, 'blend_data': bpy.data}


def so_janela(ctx):
    """Override de desenho: com `area`, todas as áreas seriam desenhadas com o espaço dela."""
    return {'window': ctx['window'], 'screen': ctx['screen']}


def texto(valor):
    """Converte valores do bpy em algo que cabe em JSON."""
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


def todos_operadores():
    for modulo in dir(bpy.ops):
        for funcao in dir(getattr(bpy.ops, modulo)):
            yield modulo + '.' + funcao


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


def cmd_listar(p):
    filtro = p.get('filtro', '')
    tipo = p.get('tipo', 'ops')
    if tipo == 'ops':
        nomes = todos_operadores()
    else:
        base = {'paineis': bpy.types.Panel, 'menus': bpy.types.Menu, 'cabecalhos': bpy.types.Header}[tipo]
        nomes = (c.__name__ for c in base.__subclasses__())
    return sorted(n for n in nomes if filtro in n)


def cmd_descrever(p):
    rna = operador(p['nome']).get_rna_type()
    return {'nome': p['nome'], 'descricao': rna.description, 'propriedades': propriedades(rna)}


def cmd_op(p):
    ctx = contexto(p.get('editor'))
    op = operador(p['nome'])
    if p.get('modo'):
        bpy.ops.object.mode_set(ctx, mode=p['modo'])
    if not op.poll(ctx):
        return {'estado': 'sem_contexto'}
    return {'estado': sorted(op(ctx, 'EXEC_DEFAULT', **p.get('args', {})))}


def cmd_ler(p):
    return texto(eval(p['caminho'], {'bpy': bpy}))


def cmd_definir(p):
    dono, nome = p['caminho'].rsplit('.', 1)
    setattr(eval(dono, {'bpy': bpy}), nome, p['valor'])
    return texto(getattr(eval(dono, {'bpy': bpy}), nome))


def cmd_py(p):
    espaco = {'bpy': bpy, 'contexto': contexto, 'resultado': None}
    exec(p['codigo'], espaco)
    return texto(espaco['resultado'])


def cmd_desenhar(p):
    ctx = so_janela(contexto(p.get('editor')))
    bpy.ops.wm.redraw_timer(ctx, type='DRAW_WIN_SWAP', iterations=1)
    return True


def cmd_tela(p):
    ctx = so_janela(contexto(p.get('editor')))
    bpy.ops.wm.redraw_timer(ctx, type='DRAW_WIN_SWAP', iterations=1)
    bpy.ops.screen.screenshot(ctx, filepath=p['arquivo'], full=True)
    return p['arquivo']


def cmd_evento(p):
    """Um evento real na fila; x e y contam do canto superior esquerdo, como nos prints."""
    janela = bpy.context.window_manager.windows[0]
    janela.event_simulate(p['tipo'], p['valor'], p['x'], janela.height - 1 - p['y'],
                          shift=p.get('shift', False), ctrl=p.get('ctrl', False),
                          alt=p.get('alt', False), text=p.get('texto', ''))
    return True


def cmd_fechar(_p):
    os._exit(0)  # sem wm.quit: não grava quit.blend


COMANDOS = {n[4:]: f for n, f in globals().items() if n.startswith('cmd_')}


def atender(linha):
    try:
        pedido = json.loads(linha)
        if pedido.get('token') != TOKEN:
            return {'ok': False, 'erro': 'token inválido'}
        return {'ok': True, 'resultado': COMANDOS[pedido['cmd']](pedido)}
    except TrocouEditor:
        return None
    except Exception as erro:
        return {'ok': False, 'erro': str(erro), 'traceback': traceback.format_exc()}


class ANASTACIO_OT_servidor_controle(bpy.types.Operator):
    bl_idname = 'wm.anastacio_servidor_controle'
    bl_label = 'Servidor de controle'

    def invoke(self, context, _event):
        self.conexao = None
        self.buffer = b''
        self.escuta = socket.socket()
        self.escuta.bind(('127.0.0.1', 0))
        self.escuta.listen(4)
        self.escuta.setblocking(False)
        wm = context.window_manager
        self.relogio = wm.event_timer_add(0.02, context.window)
        wm.modal_handler_add(self)
        with open(ARQUIVO_SESSAO + '.tmp', 'w') as f:
            json.dump({'porta': self.escuta.getsockname()[1], 'token': TOKEN, 'pid': os.getpid()}, f)
        os.replace(ARQUIVO_SESSAO + '.tmp', ARQUIVO_SESSAO)
        return {'RUNNING_MODAL'}

    def modal(self, _context, evento):
        """Um pedido por tique: o editor segue desenhando e tratando eventos entre eles."""
        if evento.type != 'TIMER':
            return {'PASS_THROUGH'}
        if self.conexao is None:
            try:
                self.conexao, _ = self.escuta.accept()
                self.conexao.setblocking(False)
                self.buffer = b''
            except BlockingIOError:
                return {'PASS_THROUGH'}
        try:
            dados = self.conexao.recv(1 << 20)
            if not dados:
                self.conexao.close()
                self.conexao = None
                return {'PASS_THROUGH'}
            self.buffer += dados
        except BlockingIOError:
            pass
        except OSError:
            self.conexao = None
            return {'PASS_THROUGH'}
        if b'\n' in self.buffer:
            linha, resto = self.buffer.split(b'\n', 1)
            resposta = atender(linha.decode('utf-8'))
            if resposta is not None:
                self.buffer = resto
                self.conexao.setblocking(True)
                self.conexao.sendall((json.dumps(resposta) + '\n').encode('utf-8'))
                self.conexao.setblocking(False)
        return {'PASS_THROUGH'}


bpy.utils.register_class(ANASTACIO_OT_servidor_controle)
quadros = [0]


def iniciar(_cena):
    quadros[0] += 1
    if quadros[0] < 3:
        return
    bpy.app.handlers.scene_update_post.remove(iniciar)
    ctx = contexto()
    bpy.ops.wm.anastacio_servidor_controle(ctx, 'INVOKE_DEFAULT')


bpy.app.handlers.scene_update_post.append(iniciar)
