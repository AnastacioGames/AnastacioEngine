"""Ponte ao vivo entre a engine e a página do editor Web (repo AnastacioEditorWeb).

AnastacioEngine -b [arquivo.range] --factory-startup --python tools/editor_web/ponte.py -- \
    --modelo D:/AnastacioEditorWeb/prototipo/modelo.html [--porta 8765] [--teste]

Um só porto em 127.0.0.1 serve a página (GET /?t=TOKEN) e o WebSocket (/ws?t=TOKEN).
Só stdlib: socket + select, handshake RFC 6455 manual. Comandos JSON restritos
(paineis — com a lista 'cena' do Outliner —, malhas, escrever [sem_undo], operador, ativar, selecionar;
sair só com --teste); nada de eval/exec. O loop roda no thread principal (bpy não é thread-safe).

Viewport: {tipo:'malhas'} leva os objetos (matriz coluna-major, cor, loc/rot/esc) e as malhas novas ou
mudadas (v/n Float32 e i Uint32 little-endian, base64); só matriz mudou -> {tipo:'transformacoes'} leve.
--exportar-malhas ARQ grava o retrato completo em JSON e sai (o montar.py do editor Web usa offline).
"""
import base64, hashlib, hmac, json, math, os, re, select, socket, sys, time

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import layout_espiao as le

GUID = b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
LIM_HANDSHAKE = 8 * 1024
LIM_MENSAGEM = 1024 * 1024
LIM_SAIDA = 256 * 1024 * 1024
LIM_TRI_MALHA = 2000000      # malha maior é pulada com aviso
LIM_TRI_TOTAL = 20000000     # orçamento da cena inteira
LIM_PARTE = 8 * 1024 * 1024  # retrato grande vai em várias mensagens 'malhas'
GEOMETRIA = {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META'}
INTERVALO_HASH = 0.5
OPERADORES = {'ed.undo', 'ed.redo', 'object.select_all', 'object.location_clear',
              'object.rotation_clear', 'object.scale_clear',
              # Botão "+" do template_ID: só criam um bloco novo com nome padrão (desfazível).
              # Fora de propósito: *.open (lê arquivo do disco) e *.unlink (apaga ligação).
              'material.new', 'world.new', 'texture.new', 'particle.new', 'palette.new', 'text.new'}
SCRIPTS_EMBUTIDOS = ('widgets_templates.js',)
RE_CAMINHO =re.compile(r'^[A-Za-z_]\w*(\[\d+\]|\["[^"\\]*"\])?(\.[A-Za-z_]\w*(\[\d+\]|\["[^"\\]*"\])?)*$')


def log(*a):
    print('[ponte]', *a)
    sys.stdout.flush()


# ---------------------------------------------------------------- JSON seguro

def _limpo(v):
    """Troca NaN/inf por None (JSON.parse do navegador não aceita)."""
    if isinstance(v, float):
        return v if math.isfinite(v) else None
    if isinstance(v, dict):
        return {k: _limpo(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_limpo(x) for x in v]
    return v


def para_json(obj):
    return json.dumps(_limpo(obj), ensure_ascii=False, default=repr)


# ---------------------------------------------------------------- engine

def objeto_ativo():
    return bpy.context.scene.objects.active


def lista_cena(cena):
    """Objetos da cena em ordem hierárquica (pai antes dos filhos, irmãos por nome) para o Outliner."""
    ativo = cena.objects.active
    nomes = {o.name for o in cena.objects}
    filhos = {}
    for o in cena.objects:
        pai = o.parent.name if o.parent and o.parent.name in nomes else None
        filhos.setdefault(pai, []).append(o)
    saida = []

    def descer(pai, nivel):
        for o in sorted(filhos.get(pai, []), key=lambda x: x.name):
            saida.append({'nome': o.name, 'tipo': o.type, 'pai': pai, 'nivel': nivel,
                          'ativo': o is ativo, 'selecionado': bool(o.select)})
            descer(o.name, nivel + 1)
    descer(None, 0)
    return saida


def estado_paineis():
    cena = bpy.context.scene
    obj = cena.objects.active
    return {'objeto': obj.name if obj else None,
            'objetos': sorted(o.name for o in cena.objects),
            'cena': lista_cena(cena),
            'paineis': le.exportar_paineis(obj, cena)}


def _numero(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _valida_escalar(p, v):
    t = p.type
    if t == 'BOOLEAN':
        ok = isinstance(v, bool)
    elif t == 'INT':
        ok = _numero(v) and float(v).is_integer()
    elif t == 'FLOAT':
        ok = _numero(v)
    elif t == 'STRING':
        ok = isinstance(v, str) and len(v) <= 4096
    elif t == 'ENUM':
        ids = {i.identifier for i in p.enum_items}
        if p.is_enum_flag:
            ok = isinstance(v, list) and all(isinstance(x, str) and x in ids for x in v)
        else:
            ok = isinstance(v, str) and v in ids
    else:
        raise ValueError('tipo de propriedade não suportado: %s' % t)
    if not ok:
        raise ValueError('valor de tipo errado para %s: %r' % (t, v))
    if t == 'INT':
        return int(v)
    if t == 'ENUM' and p.is_enum_flag:
        return set(v)
    return v


def validar_escrita(rna, valor, indice):
    """Confere tudo antes de chamar le.escrever. Devolve (valor convertido, indice)."""
    if not isinstance(rna, dict) or not all(isinstance(rna.get(k), str) for k in ('id_tipo', 'id', 'caminho')):
        raise ValueError('rna inválido')
    colecao = le.COLECOES.get(rna['id_tipo'])
    if colecao is None:
        raise ValueError('tipo de bloco não permitido: %r' % rna['id_tipo'])
    if not RE_CAMINHO.match(rna['caminho']):
        raise ValueError('caminho inválido: %r' % rna['caminho'])
    dono = getattr(bpy.data, colecao).get(rna['id'])
    if dono is None:
        raise ValueError('bloco não existe: %r' % rna['id'])
    base, _, nome = rna['caminho'].rpartition('.')
    try:
        alvo = dono.path_resolve(base) if base else dono
    except Exception:
        raise ValueError('caminho não resolve: %r' % rna['caminho'])
    if not hasattr(alvo, 'bl_rna') or nome not in alvo.bl_rna.properties:
        raise ValueError('propriedade desconhecida: %r' % nome)
    p = alvo.bl_rna.properties[nome]
    if p.is_readonly or alvo.is_property_readonly(nome):
        raise ValueError('propriedade só leitura: %r' % nome)
    n = p.array_length if p.type in {'BOOLEAN', 'INT', 'FLOAT'} else 0
    if indice is not None:
        if n == 0:
            raise ValueError('índice em propriedade que não é array')
        if not isinstance(indice, int) or isinstance(indice, bool) or not 0 <= indice < n:
            raise ValueError('índice fora do array (0..%d): %r' % (n - 1, indice))
        return _valida_escalar(p, valor), indice
    if n:
        if not isinstance(valor, list) or len(valor) != n:
            raise ValueError('esperado lista de %d valores' % n)
        return [_valida_escalar(p, x) for x in valor], None
    return _valida_escalar(p, valor), None


def cmd_escrever(m):
    sem_undo = m.get('sem_undo', False)
    if not isinstance(sem_undo, bool):
        raise ValueError('sem_undo deve ser bool')
    valor, indice = validar_escrita(m.get('rna'), m.get('valor'), m.get('indice'))
    novo = le.escrever(m['rna'], valor, indice)
    if hasattr(novo, 'to_list'):
        novo = novo.to_list()
    elif isinstance(novo, (set, frozenset)):
        novo = sorted(novo)
    elif hasattr(novo, '__len__') and not isinstance(novo, str):
        novo = list(novo)
    desfazer = False
    # Arrasto do gizmo: as escritas do meio vão com sem_undo e só a final empilha (um passo de undo).
    if not sem_undo and bpy.ops.ed.undo_push.poll():
        bpy.ops.ed.undo_push(message='Web: ' + m['rna']['caminho'])
        desfazer = True
    return {'valor': novo, 'undo_push': desfazer}


def cmd_operador(m):
    nome = m.get('op')
    props = m.get('props') or {}
    if nome not in OPERADORES:
        raise ValueError('operador fora da lista: %r' % (nome,))
    if not isinstance(props, dict) or not all(
            isinstance(k, str) and (v is None or isinstance(v, (bool, int, float, str))) for k, v in props.items()):
        raise ValueError('props inválidas')
    grupo, op = nome.split('.')
    f = getattr(getattr(bpy.ops, grupo), op)
    if not f.poll():
        raise ValueError('poll falso para %s' % nome)
    try:
        r = f(**props)
    except Exception as e:
        raise ValueError('%s: %s' % (nome, e))
    if 'FINISHED' not in r:
        raise ValueError('%s terminou com %s' % (nome, sorted(r)))
    if not nome.startswith('ed.') and bpy.ops.ed.undo_push.poll():
        bpy.ops.ed.undo_push(message='Web: ' + nome)
    return {'resultado': sorted(r)}


def cmd_ativar(m):
    nome = m.get('objeto')
    cena = bpy.context.scene
    obj = cena.objects.get(nome) if isinstance(nome, str) else None
    if obj is None:
        raise ValueError('objeto não está na cena: %r' % (nome,))
    # Como clicar no Outliner: só ele selecionado e ativo (operadores agem na seleção).
    for o in cena.objects:
        if o.select and o is not obj:
            o.select = False
    obj.select = True
    cena.objects.active = obj
    return {'objeto': obj.name}


def cmd_selecionar(m):
    """Clique na viewport. nome None limpa a seleção; adicionar=True é o Shift+clique do Blender
    (não selecionado ou não ativo -> seleciona e ativa; já ativo e selecionado -> tira da seleção)."""
    nome, adicionar = m.get('nome'), m.get('adicionar', False)
    if not isinstance(adicionar, bool):
        raise ValueError('adicionar deve ser bool')
    cena = bpy.context.scene
    if nome is None:
        if not adicionar:
            for o in cena.objects:
                o.select = False
        return {'objeto': None}
    if not isinstance(nome, str) or cena.objects.get(nome) is None:
        raise ValueError('objeto não está na cena: %r' % (nome,))
    if not adicionar:
        return cmd_ativar({'objeto': nome})
    obj = cena.objects[nome]
    if obj.select and cena.objects.active is obj:
        obj.select = False
    else:
        obj.select = True
        cena.objects.active = obj
    return {'objeto': obj.name, 'selecionado': bool(obj.select)}


# ---------------------------------------------------------------- malhas da viewport

def _b64(a):
    return base64.b64encode(np.ascontiguousarray(a, dtype=a.dtype.newbyteorder('<')).tobytes()).decode('ascii')


def _matriz(m):
    """4x4 em coluna-major (como o WebGL espera), sem NaN."""
    return [float(m[r][c]) if math.isfinite(m[r][c]) else 0.0 for c in range(4) for r in range(4)]


def _ler(colecao, attr, n, tipo, largura):
    a = np.empty(n * largura, tipo)
    if n:
        colecao.foreach_get(attr, a)
    return a.reshape(-1, largura) if largura > 1 else a


def geometria(obj, cena, orcamento):
    """Triangula a malha avaliada (modificadores em PREVIEW). Faces smooth usam a normal do vértice;
    faces flat duplicam os cantos com a normal da face. Devolve dict, {'pulada': n} ou None (vazia)."""
    me = obj.to_mesh(cena, True, 'PREVIEW')
    if me is None:
        return None
    try:
        me.calc_tessface()
        nv, nf = len(me.vertices), len(me.tessfaces)
        if not nf:
            return None
        fv = _ler(me.tessfaces, 'vertices_raw', nf, np.int32, 4)
        quad = fv[:, 3] != 0   # convenção MFace: v4 == 0 marca triângulo
        ntri = nf + int(quad.sum())
        if ntri > min(LIM_TRI_MALHA, orcamento):
            return {'pulada': ntri}
        co = _ler(me.vertices, 'co', nv, np.float32, 3)
        vn = _ler(me.vertices, 'normal', nv, np.float32, 3)
        fn = _ler(me.tessfaces, 'normal', nf, np.float32, 3)
        sm = _ler(me.tessfaces, 'use_smooth', nf, np.int32, 1).astype(bool)
        idx = np.arange(nf)
        tri = np.concatenate([fv[:, :3], fv[quad][:, [0, 2, 3]]])
        face = np.concatenate([idx, idx[quad]])
        liso = sm[face]
        plano = ~liso
        base = nv if liso.any() else 0
        tp = tri[plano]
        v = np.concatenate([co[:base], co[tp].reshape(-1, 3)])
        n = np.concatenate([vn[:base], np.repeat(fn[face[plano]], 3, axis=0)])
        i = np.empty((ntri, 3), np.uint32)
        i[liso] = tri[liso]
        i[plano] = base + np.arange(len(tp) * 3, dtype=np.uint32).reshape(-1, 3)
        v = np.nan_to_num(v, posinf=0.0, neginf=0.0).astype(np.float32)
        n = np.nan_to_num(n, posinf=0.0, neginf=0.0).astype(np.float32)
        return {'v': v, 'n': n, 'i': i.reshape(-1), 'tri': ntri}
    finally:
        bpy.data.meshes.remove(me)


def _assinatura_mods(obj):
    """Valores simples de todos os modificadores (mudar o nível do Subsurf etc. invalida o cache)."""
    out = []
    for md in obj.modifiers:
        for p in md.bl_rna.properties:
            if p.identifier == 'rna_type':
                continue
            v = getattr(md, p.identifier, None)
            if p.type in {'BOOLEAN', 'INT', 'FLOAT', 'ENUM', 'STRING'}:
                out.append((p.identifier, tuple(v) if hasattr(v, '__len__') and not isinstance(v, str) else v))
            elif isinstance(v, bpy.types.Object):
                out.append((p.identifier, v.name, _matriz(v.matrix_world)))
    return repr(out).encode('utf-8')


def chave_malha(obj, memo=None):
    """(id, assinatura barata). Mesh sem modificador é compartilhada pelo datablock ('m:'); com modificador
    ou outro tipo de geometria é por objeto ('o:'). A assinatura (coordenadas + topologia + smooth +
    modificadores) evita refazer to_mesh a cada ciclo; None = refazer sempre."""
    d = obj.data
    if obj.type != 'MESH' or d.shape_keys is not None:
        return 'o:' + obj.name, None   # shape keys: valores por objeto, refaz sempre
    memo = {} if memo is None else memo
    dado = memo.get(d.name)   # mesh compartilhada: lê as coordenadas uma vez por ciclo
    if dado is None:
        h = hashlib.md5()
        nv, nfc, nl = len(d.vertices), len(d.polygons), len(d.loops)
        h.update(('%d/%d/%d/%s' % (nv, nfc, nl, d.shape_keys is not None)).encode())
        h.update(_ler(d.vertices, 'co', nv, np.float32, 3).tobytes())
        h.update(_ler(d.loops, 'vertex_index', nl, np.int32, 1).tobytes())
        h.update(_ler(d.polygons, 'loop_total', nfc, np.int32, 1).tobytes())
        h.update(_ler(d.polygons, 'use_smooth', nfc, np.int32, 1).tobytes())
        dado = memo[d.name] = h.hexdigest()
    if obj.modifiers:
        return 'o:' + obj.name, hashlib.md5(dado.encode() + _assinatura_mods(obj)).hexdigest()
    return 'm:' + d.name, dado


def cor_objeto(obj):
    mat = obj.active_material
    c = list(mat.diffuse_color) if mat else [0.8, 0.8, 0.8]
    return [round(x, 4) if math.isfinite(x) else 0.8 for x in c[:3]]


def matriz_mundo(o, memo):
    """matrix_world montada de matrix_basis (que o 2.79 calcula na hora de loc/rot/esc) e da cadeia de pais.
    Pai por osso/vértice ou constraints: cai no matrix_world guardado (pode estar atrasado em -b)."""
    m = memo.get(o.name)
    if m is None:
        if o.constraints or (o.parent and o.parent_type != 'OBJECT'):
            m = o.matrix_world.copy()
        elif o.parent:
            m = matriz_mundo(o.parent, memo) * o.matrix_parent_inverse * o.matrix_basis
        else:
            m = o.matrix_basis.copy()
        memo[o.name] = m
    return m


class Malhas:
    """Cache e diferenças da viewport: malha compartilhada vai uma vez; só reenvia a que mudou."""

    def __init__(self):
        self.cache = {}       # id -> {'barata', 'hash', 'dados', 'tri'}
        self.enviadas = {}    # id -> hash que os clientes já têm
        self.estrutura = None
        self.matrizes = None
        self.objetos = []
        self.avisos = []
        self.rev = 0
        self.ms = 0.0

    def coletar(self):
        cena = bpy.context.scene
        t0 = time.perf_counter()
        # Sem cena.update(): em -b ele deixa o to_mesh() seguinte ~9x mais lento (45 ms vs 5 ms por Suzanne
        # subdividida); a matriz sai de matriz_mundo(), que segue loc/rot/esc na hora.
        memo, memo_dados = {}, {}
        objetos, atuais, orcamento, avisos = [], {}, LIM_TRI_TOTAL, []
        for o in cena.objects:
            if o.hide:
                continue
            mid = None
            if o.type in GEOMETRIA:
                mid, barata = chave_malha(o, memo_dados)
                c = atuais.get(mid)
                if c is None:
                    c = self.cache.get(mid)
                    if c is None or barata is None or c['barata'] != barata:
                        g = geometria(o, cena, orcamento)
                        if g is None or 'pulada' in g:
                            if g:
                                avisos.append('%s: %d triângulos, pulada (limite %d)'
                                              % (o.name, g['pulada'], min(LIM_TRI_MALHA, orcamento)))
                            # Pulada só pelo orçamento da cena: sem assinatura, tenta de novo no próximo ciclo.
                            pelo_limite = g and g['pulada'] > LIM_TRI_MALHA
                            c = {'barata': barata if (g is None or pelo_limite) else None, 'hash': None, 'dados': None, 'tri': 0}
                        else:
                            h = hashlib.md5()
                            for k in ('v', 'n', 'i'):
                                h.update(g[k].tobytes())
                            c = {'barata': barata, 'hash': h.hexdigest(), 'tri': g['tri'],
                                 'dados': {'v': _b64(g['v']), 'n': _b64(g['n']), 'i': _b64(g['i']), 'tri': g['tri'],
                                           'h': h.hexdigest()[:12]}}
                        self.cache[mid] = c
                    atuais[mid] = c
                    orcamento -= c['tri']
                if c['dados'] is None:
                    mid = None
            rot = {'QUATERNION': o.rotation_quaternion, 'AXIS_ANGLE': o.rotation_axis_angle}.get(o.rotation_mode, o.rotation_euler)
            objetos.append({'nome': o.name, 'tipo': o.type,
                            'sub': o.data.type if o.type == 'LAMP' else None,
                            'malha_id': mid, 'cor': cor_objeto(o), 'matriz': _matriz(matriz_mundo(o, memo)),
                            'loc': list(o.location), 'rot': list(rot), 'esc': list(o.scale),
                            'modo_rot': o.rotation_mode, 'pai': o.parent.name if o.parent else None})
        for mid in [k for k in self.cache if k not in atuais]:
            del self.cache[mid]
        if avisos and avisos != self.avisos:
            for a in avisos:
                log('aviso malhas:', a)
        self.objetos = _limpo(objetos)
        self.avisos = avisos
        self.ms = (time.perf_counter() - t0) * 1000
        return atuais

    @staticmethod
    def _partes(itens, rev, completo):
        msgs, atual, tam = [], {}, 0
        for k, d in itens:
            n = len(d['v']) + len(d['n']) + len(d['i'])
            if atual and tam + n > LIM_PARTE:
                msgs.append({'tipo': 'malhas', 'rev': rev, 'completo': completo, 'malhas': atual, 'remover': []})
                atual, tam = {}, 0
            atual[k] = d
            tam += n
        msgs.append({'tipo': 'malhas', 'rev': rev, 'completo': completo, 'malhas': atual, 'remover': []})
        return msgs

    def retrato(self):
        """Tudo (cliente novo e --exportar-malhas), em partes de até LIM_PARTE; a última leva os objetos."""
        msgs = self._partes([(k, c['dados']) for k, c in self.cache.items() if c['dados']], self.rev, True)
        msgs[-1].update(objetos=self.objetos, avisos=self.avisos, fim=True)
        return msgs

    def diferenca(self):
        """Coleta e devolve as mensagens para os clientes que já têm o retrato (lista, talvez vazia)."""
        atuais = self.coletar()
        novas = [(k, c['dados']) for k, c in atuais.items() if c['dados'] and self.enviadas.get(k) != c['hash']]
        remover = [k for k in self.enviadas if k not in atuais or not atuais[k]['dados']]
        estrutura = [(o['nome'], o['tipo'], o['sub'], o['malha_id'], o['cor'], o['modo_rot'], o['pai'])
                     for o in self.objetos]
        matrizes = [{k: o[k] for k in ('nome', 'matriz', 'loc', 'rot', 'esc')} for o in self.objetos]
        self.enviadas = {k: c['hash'] for k, c in atuais.items() if c['dados']}
        if novas or remover or estrutura != self.estrutura:
            self.estrutura, self.matrizes = estrutura, matrizes
            self.rev += 1
            msgs = self._partes(novas, self.rev, False)
            msgs[-1].update(remover=remover, objetos=self.objetos, avisos=self.avisos, fim=True)
            return msgs
        if matrizes != self.matrizes:
            mudou = [m for m, a in zip(matrizes, self.matrizes) if m != a]
            self.matrizes = matrizes
            self.rev += 1
            return [{'tipo': 'transformacoes', 'rev': self.rev, 'objetos': mudou}]
        return []


# ---------------------------------------------------------------- WebSocket

class Cliente:
    def __init__(self, sock, end):
        self.sock = sock
        self.end = end
        self.entrada = bytearray()
        self.saida = bytearray()
        self.ws = False
        self.fechar_apos = False   # fecha quando a saída esvaziar
        self.fragmentos = None     # bytearray durante mensagem fragmentada
        self.tem_malhas = False    # já recebeu o retrato completo -> recebe as diferenças

    def envia_bytes(self, b):
        self.saida += b
        if len(self.saida) > LIM_SAIDA:
            raise ConnectionError('buffer de saída cheio (cliente lento)')

    def envia_frame(self, opcode, dados):
        n = len(dados)
        if n < 126:
            cab = bytes([0x80 | opcode, n])
        elif n < 65536:
            cab = bytes([0x80 | opcode, 126]) + n.to_bytes(2, 'big')
        else:
            cab = bytes([0x80 | opcode, 127]) + n.to_bytes(8, 'big')
        self.envia_bytes(cab + dados)

    def envia_json(self, obj):
        self.envia_frame(1, para_json(obj).encode('utf-8'))

    def fecha_ws(self, codigo, motivo=''):
        if not self.fechar_apos:
            self.envia_frame(8, codigo.to_bytes(2, 'big') + motivo.encode('utf-8')[:120])
        self.fechar_apos = True
        self.entrada = bytearray()


def resposta_http(status, corpo=b'', tipo='text/plain; charset=utf-8', extra=''):
    return ('HTTP/1.1 %s\r\nContent-Type: %s\r\nContent-Length: %d\r\nCache-Control: no-store\r\n'
            'X-Content-Type-Options: nosniff\r\nConnection: close\r\n%s\r\n'
            % (status, tipo, len(corpo), extra)).encode('latin-1') + corpo


class Ponte:
    def __init__(self, porta, modelo, teste):
        self.modelo = modelo
        self.teste = teste
        self.token = base64.urlsafe_b64encode(os.urandom(24)).decode('ascii').rstrip('=')
        self.serv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serv.bind(('127.0.0.1', porta))
        self.serv.listen(16)
        self.serv.setblocking(False)
        self.porta = self.serv.getsockname()[1]
        self.origem = 'http://127.0.0.1:%d' % self.porta
        self.hosts = {'127.0.0.1:%d' % self.porta}
        self.clientes = {}
        self.rev = 0
        self.hash = None
        self.ultimo_hash = 0.0
        self.rodando = True
        self.estado = None
        self.malhas = Malhas()

    # --- painéis e revisão
    def atualizar(self, forcar=False):
        """Exporta painéis; se mudaram (ou forcar), sobe a revisão. Devolve True se mudou."""
        est = estado_paineis()
        h = hashlib.md5(para_json(est).encode('utf-8')).hexdigest()
        mudou = h != self.hash
        if mudou or forcar:
            self.rev += 1
        self.hash = h
        self.estado = est
        return mudou or forcar

    def msg_paineis(self):
        m = {'tipo': 'paineis', 'rev': self.rev}
        m.update(self.estado)
        return m

    def difundir(self):
        m = self.msg_paineis()
        dados = para_json(m).encode('utf-8')
        for c in list(self.clientes.values()):
            if c.ws and not c.fechar_apos:
                self._seguro(c, c.envia_frame, 1, dados)

    def difundir_malhas(self):
        """Só coleta se alguém pediu malhas (ou forçado pelo teste de desempenho)."""
        alvos = [c for c in self.clientes.values() if c.ws and c.tem_malhas and not c.fechar_apos]
        if not alvos:
            return
        for m in self.malhas.diferenca():
            dados = para_json(m).encode('utf-8')
            for c in alvos:
                self._seguro(c, c.envia_frame, 1, dados)

    def enviar_retrato(self, c):
        if not c.tem_malhas and not any(x.tem_malhas for x in self.clientes.values()):
            self.malhas.diferenca()   # primeiro cliente: coleta agora e marca tudo como enviado
        c.tem_malhas = True
        for m in self.malhas.retrato():
            c.envia_json(m)

    def _seguro(self, c, f, *a):
        try:
            f(*a)
        except ConnectionError as e:
            log('derrubando', c.end, e)
            self.remover(c)

    # --- HTTP / handshake
    def tratar_http(self, c):
        fim = c.entrada.find(b'\r\n\r\n')
        if fim < 0:
            if len(c.entrada) > LIM_HANDSHAKE:
                c.envia_bytes(resposta_http('431 Request Header Fields Too Large'))
                c.fechar_apos = True
            return
        if fim + 4 > LIM_HANDSHAKE:
            c.envia_bytes(resposta_http('431 Request Header Fields Too Large'))
            c.fechar_apos = True
            return
        bruto = bytes(c.entrada[:fim]).decode('latin-1')
        del c.entrada[:fim + 4]
        linhas = bruto.split('\r\n')
        partes = linhas[0].split(' ')
        cab = {}
        for l in linhas[1:]:
            k, _, v = l.partition(':')
            cab[k.strip().lower()] = v.strip()
        if len(partes) != 3 or partes[0] != 'GET':
            return self.recusar(c, '405 Method Not Allowed')
        caminho, _, consulta = partes[1].partition('?')
        params = {}
        for par in consulta.split('&'):
            k, _, v = par.partition('=')
            params[k] = v
        if cab.get('host') not in self.hosts:
            return self.recusar(c, '421 Misdirected Request')
        token_ok = hmac.compare_digest(params.get('t', '').encode('utf-8', 'replace'), self.token.encode('ascii'))
        if caminho == '/ws':
            if not token_ok:
                return self.recusar(c, '403 Forbidden', 'token')
            if cab.get('origin') != self.origem:
                return self.recusar(c, '403 Forbidden', 'origin')
            chave = cab.get('sec-websocket-key', '')
            if (cab.get('upgrade', '').lower() != 'websocket'
                    or 'upgrade' not in cab.get('connection', '').lower()
                    or cab.get('sec-websocket-version') != '13' or len(chave) != 24):
                return self.recusar(c, '400 Bad Request', 'handshake')
            aceite = base64.b64encode(hashlib.sha1(chave.encode('ascii') + GUID).digest()).decode('ascii')
            c.envia_bytes(('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                           'Sec-WebSocket-Accept: %s\r\n\r\n' % aceite).encode('ascii'))
            c.ws = True
            log('ws conectado', c.end)
            return
        if caminho == '/':
            if not token_ok:
                return self.recusar(c, '403 Forbidden', 'token')
            with open(self.modelo, encoding='utf-8') as f:
                html = f.read()
            # Scripts auxiliares (só os desta lista, vizinhos de modelo.html) vão embutidos: sem rota de arquivos.
            for nome_js in SCRIPTS_EMBUTIDOS:
                arq_js = os.path.join(os.path.dirname(self.modelo), nome_js)
                if os.path.isfile(arq_js):
                    with open(arq_js, encoding='utf-8') as f:
                        corpo_js = f.read().replace('</script', '<\\/script')
                    html = html.replace('<script src="%s"></script>' % nome_js, '<script>\n%s\n</script>' % corpo_js, 1)
            html = html.replace('/*PAINEIS*/{}', para_json(self.estado['paineis']).replace('</', '<\\/'), 1)
            html = html.replace('/*CENA*/[]', para_json(self.estado['cena']).replace('</', '<\\/'), 1)
            c.envia_bytes(resposta_http('200 OK', html.encode('utf-8'), 'text/html; charset=utf-8',
                                        "Content-Security-Policy: default-src 'self' 'unsafe-inline'; "
                                        "connect-src ws://127.0.0.1:%d\r\n" % self.porta))
            c.fechar_apos = True
            return
        self.recusar(c, '404 Not Found')

    def recusar(self, c, status, motivo=''):
        if motivo:
            log('recusado', c.end, status, motivo)
        c.envia_bytes(resposta_http(status, (status + ' ' + motivo).encode('utf-8')))
        c.fechar_apos = True
        c.entrada = bytearray()

    # --- frames
    def tratar_frames(self, c):
        while not c.fechar_apos:
            b = c.entrada
            if len(b) < 2:
                return
            fin, op = b[0] & 0x80, b[0] & 0x0F
            if b[0] & 0x70:
                return c.fecha_ws(1002, 'RSV')
            if not b[1] & 0x80:
                return c.fecha_ws(1002, 'frame sem mascara')
            n = b[1] & 0x7F
            pos = 2
            if n == 126:
                if len(b) < 4:
                    return
                n = int.from_bytes(b[2:4], 'big')
                pos = 4
            elif n == 127:
                if len(b) < 10:
                    return
                n = int.from_bytes(b[2:10], 'big')
                pos = 10
            if op >= 8 and (n > 125 or not fin):
                return c.fecha_ws(1002, 'controle invalido')
            atual = len(c.fragmentos) if c.fragmentos is not None else 0
            if n + atual > LIM_MENSAGEM:
                return c.fecha_ws(1009, 'mensagem grande')
            if len(b) < pos + 4 + n:
                return
            mascara = bytes(b[pos:pos + 4])
            dados = bytearray(b[pos + 4:pos + 4 + n])
            del b[:pos + 4 + n]
            if n:
                m = (mascara * (n // 4 + 1))[:n]
                dados = (int.from_bytes(dados, 'little') ^ int.from_bytes(m, 'little')).to_bytes(n, 'little')
            if op == 8:
                c.fecha_ws(1000)
                return
            if op == 9:
                c.envia_frame(10, bytes(dados))
                continue
            if op == 10:
                continue
            if op == 0:
                if c.fragmentos is None:
                    return c.fecha_ws(1002, 'continuacao solta')
                c.fragmentos += dados
                if not fin:
                    continue
                dados, c.fragmentos = bytes(c.fragmentos), None
            elif op == 1:
                if c.fragmentos is not None:
                    return c.fecha_ws(1002, 'nova mensagem no meio')
                if not fin:
                    c.fragmentos = bytearray(dados)
                    continue
            elif op == 2:
                return c.fecha_ws(1003, 'so texto')
            else:
                return c.fecha_ws(1002, 'opcode')
            try:
                texto = bytes(dados).decode('utf-8')
            except UnicodeDecodeError:
                return c.fecha_ws(1007, 'utf-8')
            self.comando(c, texto)

    # --- comandos
    def comando(self, c, texto):
        try:
            m = json.loads(texto)
        except ValueError:
            return c.envia_json({'tipo': 'erro', 'erro': 'JSON inválido'})
        if not isinstance(m, dict):
            return c.envia_json({'tipo': 'erro', 'erro': 'esperado objeto'})
        cmd = m.get('cmd')
        resp = {'id': m.get('id'), 'cmd': cmd}
        try:
            if cmd == 'paineis':
                c.envia_json(self.msg_paineis())
                return
            elif cmd == 'malhas':
                self.enviar_retrato(c)
                return
            elif cmd == 'selecionar':
                resp.update(cmd_selecionar(m))
            elif cmd == 'escrever':
                resp.update(cmd_escrever(m))
            elif cmd == 'operador':
                resp.update(cmd_operador(m))
            elif cmd == 'ativar':
                resp.update(cmd_ativar(m))
            elif cmd == 'sair' and self.teste:
                c.envia_json(dict(resp, tipo='ok'))
                self.rodando = False
                return
            else:
                raise ValueError('comando desconhecido: %r' % (cmd,))
        except Exception as e:
            resp.update(tipo='erro', erro=str(e))
            c.envia_json(resp)
            return
        resp['tipo'] = 'ok'
        c.envia_json(resp)
        self.atualizar(forcar=True)
        self.difundir()
        self.difundir_malhas()

    # --- loop
    def remover(self, c):
        self.clientes.pop(c.sock, None)
        try:
            c.sock.close()
        except OSError:
            pass

    def passo(self, espera=0.05):
        leit = [self.serv] + [s for s, c in self.clientes.items() if not c.fechar_apos]
        escr = [s for s, c in self.clientes.items() if c.saida]
        r, w, _ = select.select(leit, escr, [], espera)
        for s in r:
            if s is self.serv:
                try:
                    novo, end = self.serv.accept()
                except (BlockingIOError, InterruptedError):
                    continue
                novo.setblocking(False)
                self.clientes[novo] = Cliente(novo, end)
                continue
            c = self.clientes.get(s)
            if c is None:
                continue
            try:
                dados = s.recv(65536)
            except (BlockingIOError, InterruptedError):
                continue
            except OSError:
                self.remover(c)
                continue
            if not dados:
                self.remover(c)
                continue
            c.entrada += dados
            try:
                if c.ws:
                    self.tratar_frames(c)
                else:
                    self.tratar_http(c)
                    if c.ws and c.entrada:
                        self.tratar_frames(c)
            except ConnectionError as e:
                log('derrubando', c.end, e)
                self.remover(c)
        for s in w:
            c = self.clientes.get(s)
            if c is None or not c.saida:
                continue
            try:
                n = s.send(c.saida)
                del c.saida[:n]
            except (BlockingIOError, InterruptedError):
                pass
            except OSError:
                self.remover(c)
        for c in list(self.clientes.values()):
            if c.fechar_apos and not c.saida:
                self.remover(c)
        agora = time.monotonic()
        if agora - self.ultimo_hash >= INTERVALO_HASH:
            self.ultimo_hash = agora
            if self.atualizar():
                self.difundir()
            self.difundir_malhas()

    def rodar(self):
        t = time.perf_counter()
        self.atualizar()
        log('exportar painéis + hash: %.1f ms, %d painéis, %d KB' % (
            (time.perf_counter() - t) * 1000, len(self.estado['paineis']), len(para_json(self.estado)) // 1024))
        log('PRONTO %s/?t=%s' % (self.origem, self.token))
        if self.abrir:
            abrir_janela_app('%s/?t=%s' % (self.origem, self.token))
        try:
            while self.rodando:
                self.passo()
            # Deixa as últimas respostas saírem (no máx. 1 s).
            fim = time.monotonic() + 1.0
            while any(c.saida for c in self.clientes.values()) and time.monotonic() < fim:
                self.passo(0.02)
        except KeyboardInterrupt:
            log('Ctrl+C')
        finally:
            for c in list(self.clientes.values()):
                self.remover(c)
            self.serv.close()
            log('encerrada')


def abrir_janela_app(url):
    """Abre a página numa janela de app (Edge/Chrome --app): sem abas nem barra de endereço,
    maximizada sem cobrir a barra do Windows."""
    import shutil, subprocess
    candidatos = [shutil.which('msedge'), shutil.which('chrome')]
    for base in (os.environ.get('ProgramFiles(x86)'), os.environ.get('ProgramFiles'),
                 os.environ.get('LOCALAPPDATA')):
        if base:
            candidatos += [os.path.join(base, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
                           os.path.join(base, 'Google', 'Chrome', 'Application', 'chrome.exe')]
    for exe in candidatos:
        if exe and os.path.isfile(exe):
            subprocess.Popen([exe, '--app=' + url, '--start-maximized'])
            log('janela de app aberta:', os.path.basename(exe))
            return
    log('Edge/Chrome não encontrado; abra a URL acima no navegador')


def exportar_malhas(arq):
    """Retrato completo num JSON só (offline) + medidas de tempo e tamanho no log."""
    mal = Malhas()
    t = time.perf_counter()
    mal.diferenca()
    frio = (time.perf_counter() - t) * 1000
    t = time.perf_counter()
    mal.diferenca()
    quente = (time.perf_counter() - t) * 1000
    t = time.perf_counter()
    msgs = mal.retrato()
    tam = sum(len(para_json(m)) for m in msgs)
    serial = (time.perf_counter() - t) * 1000
    junto = {'tipo': 'malhas', 'rev': 1, 'completo': True, 'malhas': {}, 'remover': [], 'fim': True,
             'objetos': mal.objetos, 'avisos': mal.avisos, 'cena': lista_cena(bpy.context.scene)}
    for m in msgs:
        junto['malhas'].update(m['malhas'])
    with open(arq, 'w', encoding='utf-8') as f:
        f.write(para_json(junto))
    tri = sum(c['tri'] for c in mal.cache.values())
    log('MEDIDA malhas: %d objetos, %d malhas, %d tri; 1a coleta %.1f ms, ciclo sem mudança %.1f ms, '
        'JSON %.1f ms, %d KB em %d mensagem(ns)' % (len(mal.objetos), len(junto['malhas']), tri, frio, quente,
                                                     serial, tam // 1024, len(msgs)))


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    porta, modelo, teste, abrir = 8765, None, False, False
    i = 0
    while i < len(args):
        a = args[i]
        if a == '--porta':
            porta = int(args[i + 1]); i += 1
        elif a == '--modelo':
            modelo = args[i + 1]; i += 1
        elif a == '--teste':
            teste = True
        elif a == '--abrir':
            abrir = True
        elif a == '--exportar-malhas':
            exportar_malhas(args[i + 1])
            return
        i += 1
    if modelo is None:
        modelo = os.path.join('D:' + os.sep, 'AnastacioEditorWeb', 'prototipo', 'modelo.html')
    if not os.path.isfile(modelo):
        log('modelo.html não encontrado:', modelo)
        return
    p = Ponte(porta, modelo, teste)
    p.abrir = abrir
    p.rodar()


main()
