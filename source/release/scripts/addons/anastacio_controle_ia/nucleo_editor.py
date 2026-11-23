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
SO_LEITURA = {'ping', 'cena', 'objeto', 'listar', 'descrever', 'ler', 'tela', 'backup', 'copia_para_jogo',
              'pedir_liberacao', 'resposta_pedido'}

CONFIG = {'arquivo_sessao': None, 'observar': False, 'token': None, 'ligado': False, 'dono': 'mcp'}
LIMITE_LINHA = 8 << 20  # bytes de um pedido sem quebra de linha
TEMPO_ENVIO = 5.0       # s para entregar uma resposta antes de largar a conexão
# Operadores que executam código: só com ANASTACIO_CRIADOR_PY=1, igual ao `py`.
OPS_DE_CODIGO = {'script.python_file_run', 'script.execute_preset', 'script.reload', 'text.run_script',
                 'text.open', 'wm.addon_install', 'wm.addon_enable', 'wm.addon_refresh', 'wm.addon_remove',
                 'wm.addon_userpref_show', 'wm.save_userpref', 'wm.read_factory_settings',
                 'console.execute', 'wm.context_set_value', 'wm.context_set_string',
                 'wm.context_set_enum', 'wm.context_toggle', 'wm.context_toggle_enum', 'wm.properties_edit',
                 'wm.properties_add', 'wm.keyconfig_import', 'wm.keyconfig_activate', 'wm.appconfig_activate',
                 'wm.url_open', 'wm.path_open', 'file.execute', 'wm.app_template_install'}
# Operadores que gravam arquivos em caminhos escolhidos por quem chama (o projeto, exportações, imagens):
# só com ANASTACIO_CRIADOR_PY=1. Salvar o projeto é do `projeto_salvar`, que grava no arquivo dele.
OPS_GRAVAM_ARQUIVO = {'wm.save_as_mainfile', 'wm.save_mainfile', 'wm.save_homefile', 'wm.collada_export',
                      'image.save', 'image.save_as', 'image.save_dirty', 'image.save_sequence', 'render.render',
                      'render.opengl', 'wm.link', 'wm.append', 'wm.link_append', 'wm.copy_prev_settings',
                      'sound.mixdown', 'screen.screenshot', 'screen.screencast', 'object.bake_image',
                      'wm.alembic_export', 'wm.usd_export', 'text.save', 'text.save_as'}
PREFIXOS_GRAVAM = ('export_', 'wm.save', 'image.save', 'wm.alembic', 'wm.usd')


def grava_arquivo(nome):
    return nome in OPS_GRAVAM_ARQUIVO or nome.startswith(PREFIXOS_GRAVAM)


# Operadores do editor de texto agem no texto ATIVO (que pode ser um script do usuário): nunca por `op`.
OPS_TEXTO_ATIVO = {'text.insert', 'text.paste', 'text.cut', 'text.delete', 'text.line_break', 'text.comment',
                   'text.uncomment', 'text.indent', 'text.unindent', 'text.convert_whitespace', 'text.replace',
                   'text.move_lines', 'text.duplicate_line', 'text.overwrite_toggle'}
LIMITE_SCRIPT = 200_000  # caracteres
CRIADOS = set()  # scripts que a IA criou nesta sessão: ela pode regravá-los sem pedir autorização
# `definir` só mexe em dados do projeto, nunca em preferências do usuário nem em caminhos de scripts.
PREFIXOS_DEFINIR = ('bpy.data', 'bpy.context.scene', 'bpy.context.object', 'bpy.context.active_object',
                    'bpy.context.window_manager.addon_search')
MAX_CONEXOES = 4  # clientes ao mesmo tempo (ex.: Claude Code e outro); passando disso a mais velha é largada
ESTADO = {'escuta': None, 'conexoes': []}

class TrocouEditor(Exception):
    """O pedido volta para a fila e roda de novo no próximo tique."""


def contexto(editor=None, mudar=True):
    janela = bpy.context.window_manager.windows[0]
    tela = janela.screen
    area = None
    if editor:
        area = next((a for a in tela.areas if a.type == editor), None)
    if area is None:
        area = max(tela.areas, key=lambda a: a.width * a.height)
        if editor:
            if not mudar:
                raise PermissionError('modo "só observar": não troco o layout do editor; peça a tela de um editor '
                                      'que já está aberto ou peça ao usuário para liberar a edição')
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


TEMPO_PEDIDO = 60.0     # s que o aviso fica na tela esperando o usuário
ESPERA_NEGADO = float(os.environ.get('ANASTACIO_CRIADOR_ESPERA_NEGADO', 30))   # s sem novo pedido depois de uma negação
PEDIDO = {'motivo': None, 'fim': 0.0, 'resultado': None, 'bloqueado_ate': 0.0, 'cliente': ''}
QUEM = {'atual': ''}  # cliente do pedido que está sendo atendido agora


def nome_cliente(bruto):
    """Nome para mostrar de quem se conectou (ex.: 'claude-code' -> 'Claude Code'); vazio se não disse."""
    nome = ''.join(ch for ch in str(bruto or '') if ch.isprintable()).strip()[:24]
    baixo = nome.lower()
    if 'claude' in baixo:
        return 'Claude Code' if 'code' in baixo or baixo == 'claude' else 'Claude'
    if 'codex' in baixo:
        return 'Codex'
    return nome


def clientes_conectados():
    """Nomes de quem está conectado agora (sem repetir; 'IA' para quem não se identificou)."""
    return sorted({c.get('nome') or 'IA' for c in ESTADO['conexoes']})


def pedido_atual():
    """Pedido de liberação pendente ({'motivo','resta'}) ou None; expira sozinho."""
    if PEDIDO['motivo'] is not None and time.time() > PEDIDO['fim']:
        PEDIDO.update(motivo=None, resultado='expirou')
    if PEDIDO['motivo'] is None:
        return None
    return {'motivo': PEDIDO['motivo'], 'cliente': PEDIDO['cliente'],
            'resta': round(PEDIDO['fim'] - time.time(), 1)}


def responder_pedido(permitir):
    """Chamado só pelo usuário (botão do editor). Permitir libera a edição; negar segura novos pedidos."""
    if PEDIDO['motivo'] is None:
        return
    PEDIDO['motivo'] = None
    PEDIDO['resultado'] = 'permitido' if permitir else 'negado'
    if permitir:
        CONFIG['observar'] = False
    else:
        PEDIDO['bloqueado_ate'] = time.time() + ESPERA_NEGADO


def cmd_pedir_liberacao(p):
    """Mostra no editor um aviso pedindo ao usuário para liberar a edição. Não libera nada por si."""
    if not CONFIG['observar']:
        return {'estado': 'permitido', 'aviso': 'a edição já está liberada'}
    if CONFIG['dono'] == 'mcp':
        raise ValueError('o editor foi aberto pelo MCP; não há aviso para clicar')
    if time.time() < PEDIDO['bloqueado_ate']:
        return {'estado': 'negado', 'aviso': 'o usuário negou há pouco; aguarde antes de pedir de novo'}
    motivo = str(p.get('motivo', '')).strip()[:200]
    if not motivo:
        raise ValueError('informe o motivo em uma frase')
    PEDIDO.update(motivo=motivo, fim=time.time() + TEMPO_PEDIDO, resultado=None, cliente=QUEM['atual'])
    for janela in bpy.context.window_manager.windows:
        for area in janela.screen.areas:
            area.tag_redraw()
    return {'estado': 'pendente', 'resta': TEMPO_PEDIDO}


def cmd_resposta_pedido(_p):
    """Estado do pedido: pendente, permitido, negado, expirou (ou None se nunca houve)."""
    if pedido_atual() is not None:
        return {'estado': 'pendente', 'resta': pedido_atual()['resta']}
    return {'estado': PEDIDO['resultado']}


def cmd_ping(_p):
    return {'versao': VERSAO, 'arquivo': bpy.data.filepath, 'py_liberado': PY_LIBERADO,
            'modo': 'observar' if CONFIG['observar'] else 'controle', 'pedido': pedido_atual(),
            'clientes': clientes_conectados()}


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
    if p['nome'] in OPS_TEXTO_ATIVO:
        raise PermissionError('%s edita o texto ativo do editor (pode ser um script do usuário). '
                              'Use script_gravar para criar ou trocar o conteúdo de um script pelo nome' % p['nome'])
    if grava_arquivo(p['nome']) and not PY_LIBERADO:
        raise PermissionError('%s grava arquivos em caminhos livres: só com ANASTACIO_CRIADOR_PY=1 '
                              '(para salvar o projeto use projeto_salvar)' % p['nome'])
    if p['nome'] in OPS_DE_CODIGO and not PY_LIBERADO:
        raise PermissionError('%s executa código ou mexe em preferências: só com ANASTACIO_CRIADOR_PY=1' % p['nome'])
    op = operador(p['nome'])
    if p['nome'] in CARREGAM_ARQUIVO:
        return {'estado': sorted(op('EXEC_DEFAULT', **p.get('args', {})))}
    ctx = contexto(p.get('editor'))
    if p.get('modo'):
        bpy.ops.object.mode_set(ctx, mode=p['modo'])
    if not op.poll(ctx):
        return {'estado': 'sem_contexto'}
    return {'estado': sorted(op(ctx, 'EXEC_DEFAULT', **p.get('args', {})))}


def cmd_script_gravar(p):
    """Cria um texto (script) pelo nome e grava o conteúdo. Só dados: não roda nada. Não sobrescreve sem pedir."""
    nome, conteudo = p['nome'], p['conteudo']
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.\- ]{0,62}', nome):
        raise ValueError('nome de script inválido: use letras, números, _ . - e espaço (até 63)')
    if not isinstance(conteudo, str) or len(conteudo) > LIMITE_SCRIPT:
        raise ValueError('conteúdo deve ser texto de até %d caracteres' % LIMITE_SCRIPT)
    existente = bpy.data.texts.get(nome)
    if existente is not None and not p.get('sobrescrever') and nome not in CRIADOS:
        raise ValueError('já existe um script "%s" que não foi criado por você nesta sessão; use outro nome ou peça ao '
                         'usuário para autorizar sobrescrever' % nome)
    texto = existente or bpy.data.texts.new(nome)
    texto.clear()
    texto.write(conteudo)
    CRIADOS.add(texto.name)
    return {'script': texto.name, 'linhas': conteudo.count('\n') + 1, 'criado': existente is None}


def cmd_script_ligar(p):
    """Liga um script ao objeto: sensor Always (pulso contínuo) -> controlador Python em modo Script."""
    objeto = bpy.data.objects[p['objeto']]
    texto = bpy.data.texts[p['script']]
    if any(c.type == 'PYTHON' and c.text == texto for c in objeto.game.controllers):
        return {'objeto': objeto.name, 'script': texto.name, 'aviso': 'já estava ligado'}
    ctx = contexto()
    cena = bpy.context.scene
    antes = cena.objects.active
    cena.objects.active = objeto
    try:
        bpy.ops.logic.sensor_add(ctx, type='ALWAYS', object=objeto.name)
        bpy.ops.logic.controller_add(ctx, type='PYTHON', object=objeto.name)
    finally:
        cena.objects.active = antes
    ctrl, sensor = objeto.game.controllers[-1], objeto.game.sensors[-1]
    ctrl.mode = 'SCRIPT'
    ctrl.text = texto
    sensor.use_pulse_true_level = True
    sensor.link(ctrl)
    return {'objeto': objeto.name, 'script': texto.name, 'sensor': sensor.name, 'controlador': ctrl.name}


def cmd_ler(p):
    return texto(caminhos.ler(p['caminho'], bpy))


def cmd_definir(p):
    if not PY_LIBERADO and not p['caminho'].startswith(PREFIXOS_DEFINIR):
        raise PermissionError('definir só aceita dados do projeto (bpy.data..., bpy.context.scene...); '
                              'outros caminhos exigem ANASTACIO_CRIADOR_PY=1')
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


def cmd_copia_para_jogo(p):
    """Grava uma cópia da cena atual (com o que ainda não foi salvo) em `arquivo`, sem trocar o arquivo aberto."""
    bpy.ops.wm.save_as_mainfile(filepath=p['arquivo'], copy=True)
    return p['arquivo']


def cmd_salvar(_p):
    if not bpy.data.filepath:
        raise ValueError('projeto sem nome: salve pelo editor uma primeira vez')
    bpy.ops.wm.save_mainfile()
    return bpy.data.filepath


def cmd_tela(p):
    ctx = so_janela(contexto(p.get('editor'), mudar=not CONFIG['observar']))
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
    if CONFIG['dono'] != 'mcp':  # editor aberto pelo usuário: só solta a conexão, nunca mata o processo
        desligar()
        return 'controle desligado; o editor continua aberto'
    os._exit(0)  # sem wm.quit: não grava quit.blend nem mexe no projeto


COMANDOS = {n[4:]: f for n, f in globals().items() if n.startswith('cmd_')}


def atender(linha):
    try:
        pedido = json.loads(linha)
        if pedido.get('token') != CONFIG['token']:
            return {'ok': False, 'erro': 'token inválido'}
        QUEM['atual'] = nome_cliente(pedido.get('cliente'))
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
                                                    'pid': os.getpid(), 'versao': VERSAO,
                                                    'programa': sessao.nome_processo(os.getpid())})
    return ESTADO['escuta']


def porta():
    return ESTADO['escuta'].getsockname()[1] if ESTADO['escuta'] else None


def conectado():
    return bool(ESTADO['conexoes'])


def ligar(arquivo_sessao, observar=False, dono='mcp'):
    """Começa a escutar. Recusa se outro editor vivo já usa o arquivo de sessão."""
    if CONFIG['ligado']:
        return
    outro = sessao.ler(arquivo_sessao)
    if outro and outro.get('pid') != os.getpid():
        raise RuntimeError('já há outro editor com o controle por IA ligado (pid %s); desligue lá primeiro' % outro['pid'])
    CONFIG.update(arquivo_sessao=str(arquivo_sessao), observar=observar, token=secrets.token_hex(16), dono=dono)
    try:
        escuta()
    except Exception:
        desligar()
        raise
    CONFIG['ligado'] = True


def desligar():
    """Fecha a conexão e o socket e apaga o arquivo de sessão (só se for nosso)."""
    _largar()
    if ESTADO['escuta'] is not None:
        try:
            ESTADO['escuta'].close()
        except OSError:
            pass
        ESTADO['escuta'] = None
    if CONFIG['arquivo_sessao']:
        sessao.apagar(CONFIG['arquivo_sessao'], so_se_pid=os.getpid())
    CONFIG['ligado'] = False


def _largar(c=None):
    """Fecha uma conexão (ou todas, sem argumento)."""
    for x in ([c] if c is not None else list(ESTADO['conexoes'])):
        try:
            x['s'].close()
        except OSError:
            pass
        if x in ESTADO['conexoes']:
            ESTADO['conexoes'].remove(x)


def _atender_conexao(c):
    try:
        dados = c['s'].recv(1 << 20)
        if not dados:
            _largar(c)
            return
        c['buf'] += dados
    except BlockingIOError:
        pass
    except OSError:
        _largar(c)
        return
    if len(c['buf']) > LIMITE_LINHA and b'\n' not in c['buf']:
        _largar(c)
        return
    if b'\n' in c['buf']:
        linha, resto = c['buf'].split(b'\n', 1)
        QUEM['atual'] = ''
        texto = linha.decode('utf-8', 'replace')
        try:  # o nome vale já para este pedido (o ping mostra quem pediu)
            nome = nome_cliente(json.loads(texto).get('cliente'))
            if nome:
                c['nome'] = nome
        except (ValueError, AttributeError):
            pass
        resposta = atender(texto)
        if resposta is not None and c in ESTADO['conexoes']:
            c['buf'] = resto
            try:
                c['s'].settimeout(TEMPO_ENVIO)
                c['s'].sendall((json.dumps(resposta) + '\n').encode('utf-8'))
                c['s'].setblocking(False)
            except OSError:  # cliente sumiu ou parou de ler: solta só ele, o laço continua
                _largar(c)


def tique():
    e = ESTADO
    if not CONFIG['ligado']:
        return
    try:
        nova, _ = escuta().accept()
        nova.setblocking(False)
        e['conexoes'].append({'s': nova, 'buf': b''})
        while len(e['conexoes']) > MAX_CONEXOES:  # conexão parada não prende a vaga: a mais velha sai
            _largar(e['conexoes'][0])
    except (BlockingIOError, InterruptedError, OSError):
        pass
    for c in list(e['conexoes']):
        _atender_conexao(c)


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
            try:
                tique()
            except Exception:
                traceback.print_exc()
                _largar()
        return {'PASS_THROUGH'}


def iniciar_modal():
    bpy.ops.wm.anastacio_servidor_criador(contexto(), 'INVOKE_DEFAULT')


def registrar():
    bpy.utils.register_class(ANASTACIO_OT_servidor_criador)


def desregistrar():
    desligar()
    bpy.utils.unregister_class(ANASTACIO_OT_servidor_criador)
