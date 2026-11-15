"""Layout falso: roda os draw() dos painéis Python e devolve a árvore em JSON.

Nada desenha: cada chamada de `layout` vira um nó. Usado pelo experimento do
editor na Web (repo AnastacioEditorWeb) e pelos testes em tools/editor_web.
"""
import bpy

# Métodos que só criam um sub-layout.
CONTAINERS = {'row', 'column', 'split', 'box', 'column_flow', 'grid_flow'}
# Itens simples entendidos pela UI Web.
ITENS = {'prop', 'label', 'operator', 'separator', 'menu', 'prop_enum',
         'props_enum', 'prop_menu_enum', 'operator_menu_enum', 'operator_enum',
         'prop_search', 'context_pointer_set'}
# Templates com dados próprios (ver _template).
TEMPLATES = {'template_list', 'template_ID', 'template_preview'}
# Estado herdado que o painel pode ajustar no layout.
ESTADO = {'active', 'enabled', 'alert', 'alignment', 'scale_x', 'scale_y',
          'operator_context', 'use_property_split'}


def caminho_rna(dado, prop=None):
    """Caminho estável para escrever de volta: bloco ID + caminho dentro dele."""
    try:
        dono = dado.id_data
        base = dado.path_from_id() if dado != dono else ''
    except Exception:
        return None
    if dono is None:
        return None
    caminho = base + ('.' if base and prop else '') + (prop or '')
    return {'id_tipo': type(dono).__name__, 'id': dono.name, 'caminho': caminho}


def info_prop(dado, prop):
    """Tipo, limites e valor da propriedade RNA."""
    nome = prop
    try:
        p = dado.bl_rna.properties[prop]
    except Exception:
        return {'erro': 'prop desconhecida'}
    info = {'tipo_rna': p.type, 'subtipo': p.subtype, 'rotulo': p.name, 'dica': p.description}
    if p.type in {'INT', 'FLOAT'}:
        info.update(min=p.soft_min, max=p.soft_max, tamanho=p.array_length)
    if p.type == 'ENUM':
        info['opcoes'] = [(i.identifier, i.name) for i in p.enum_items]
    try:
        v = getattr(dado, nome)
        if hasattr(v, 'to_list'):
            v = v.to_list()
        elif p.type == 'POINTER':
            v = getattr(v, 'name', None) if v is not None else None
        elif p.type == 'COLLECTION':
            v = len(v)
        elif isinstance(v, (set, frozenset)):
            v = sorted(v)
        elif hasattr(v, '__len__') and not isinstance(v, str):
            v = list(v)
        info['valor'] = v
    except Exception as e:
        info['valor_erro'] = str(e)
    return info


class PropsOperador:
    """Objeto devolvido por layout.operator(); guarda as propriedades atribuídas."""

    def __init__(self, no):
        object.__setattr__(self, '_no', no)

    def __setattr__(self, k, v):
        self._no.setdefault('props', {})[k] = v if isinstance(v, (bool, int, float, str)) else repr(v)

    def __getattr__(self, k):
        return self._no.get('props', {}).get(k)


class LayoutFalso:
    def __init__(self, tipo='layout', registro=None, **extra):
        no = {'tipo': tipo}
        no.update(extra)
        no['itens'] = []
        object.__setattr__(self, '_no', no)
        object.__setattr__(self, '_reg', registro if registro is not None else {})

    # Estado herdado: active, enabled...
    def __setattr__(self, k, v):
        self._no.setdefault('estado', {})[k] = v

    def __getattr__(self, nome):
        if nome in ESTADO:
            return self._no.get('estado', {}).get(nome, True)
        reg = self._reg

        def chamada(*args, **kw):
            reg[nome] = reg.get(nome, 0) + 1
            if nome in CONTAINERS:
                filho = LayoutFalso(nome, reg, args=_simples(args, kw))
                self._no['itens'].append(filho._no)
                return filho
            no = {'tipo': nome}
            if nome in ITENS:
                no.update(_item(nome, args, kw))
            elif nome in TEMPLATES:
                try:
                    no.update(_template(nome, args, kw))
                except Exception as e:
                    no['sem_suporte'] = True
                    no['erro'] = '%s: %s' % (type(e).__name__, e)
                    no['args'] = _simples(args, kw)
                self._no['itens'].append(no)
                return None
            else:
                # template_*, UIList etc.: sem suporte, só registra.
                no['sem_suporte'] = True
                no['args'] = _simples(args, kw)
            self._no['itens'].append(no)
            if nome == 'operator':
                return PropsOperador(no)
            if nome in ITENS:
                return None
            # Desconhecido: devolve sub-layout para o painel seguir desenhando.
            filho = LayoutFalso('filho_de_' + nome, reg)
            no['itens'] = [filho._no]
            return filho
        return chamada

    def para_json(self):
        return self._no


def _simples(args, kw):
    def s(v):
        if v is None or isinstance(v, (bool, int, float, str)):
            return v
        if hasattr(v, 'bl_rna'):
            return {'rna': type(v).__name__, 'nome': getattr(v, 'name', None)}
        return repr(v)
    out = {'pos': [s(a) for a in args]}
    out.update({k: s(v) for k, v in kw.items()})
    return out


def _item(nome, args, kw):
    no = {}
    if nome in {'prop', 'prop_enum', 'props_enum', 'prop_menu_enum', 'prop_search'} and len(args) >= 2:
        dado, prop = args[0], args[1]
        no['rna'] = caminho_rna(dado, prop)
        no.update(info_prop(dado, prop))
        resto = args[2:]
        if resto:
            no['args'] = _simples(resto, {})
    elif nome in {'operator', 'operator_menu_enum', 'operator_enum'} and args:
        no['op'] = args[0]
        if len(args) > 1:
            no['args'] = _simples(args[1:], {})
    elif args:
        no['args'] = _simples(args, {})
    for k, v in kw.items():
        no[k] = _simples((v,), {})['pos'][0]
    return no


def colecao_do_tipo(nome_tipo):
    """Nome da coleção de bpy.data cujos itens são do tipo RNA `nome_tipo` (ex.: 'Material')."""
    for p in bpy.data.bl_rna.properties:
        if p.type == 'COLLECTION' and p.fixed_type and p.fixed_type.identifier == nome_tipo:
            return p.identifier
    return None


def _args(nomes, args, kw):
    v = dict(zip(nomes, args))
    v.update({k: kw[k] for k in nomes if k in kw})
    return v


LIMITE_LISTA = 500


def _texto_item(listtype, item, dado, ativo_dado, ativo_prop, i):
    """Nome e ícone de um item pelo draw_item da UIList, se simples; senão item.name."""
    nome = getattr(item, 'name', None)
    icone = None
    cls = getattr(bpy.types, listtype, None) if listtype else None
    if cls is not None and 'draw_item' in cls.__dict__:
        try:
            lay = LayoutFalso('item', {})
            cls.draw_item(SelfFalso(cls, lay), bpy.context, lay, dado, item, 0, ativo_dado, ativo_prop, i)
            pilha = [lay._no]
            while pilha:
                n = pilha.pop(0)
                if n['tipo'] in {'prop', 'label'}:
                    t = n.get('text')
                    if not t and n['tipo'] == 'prop' and isinstance(n.get('valor'), str):
                        t = n['valor']
                    if t:
                        nome = t
                        icone = n.get('icon')
                        break
                pilha.extend(n.get('itens', []))
        except Exception:
            pass
    return nome, icone


def _template(nome, args, kw):
    if nome == 'template_list':
        a = _args(['listtype', 'list_id', 'dataptr', 'propname', 'active_dataptr', 'active_propname'], args, kw)
        dado, prop = a['dataptr'], a['propname']
        adado, aprop = a['active_dataptr'], a['active_propname']
        col = getattr(dado, prop) if dado is not None else []  # ex.: malha sem shape keys
        itens = []
        for i, item in enumerate(col):
            if i >= LIMITE_LISTA:
                break
            n, ic = _texto_item(a.get('listtype'), item, dado, adado, aprop, i)
            d = {'nome': n, 'indice': i}
            if ic:
                d['icone'] = ic
            itens.append(d)
        return {'listtype': a.get('listtype'), 'list_id': a.get('list_id'),
                'rna': caminho_rna(dado, prop) if dado is not None else None, 'itens_lista': itens, 'total': len(col),
                'ativo': {'rna': caminho_rna(adado, aprop), 'valor': getattr(adado, aprop)},
                'rows': kw.get('rows')}
    if nome == 'template_ID':
        a = _args(['data', 'property'], args, kw)
        dado, prop = a['data'], a['property']
        p = dado.bl_rna.properties[prop]
        v = getattr(dado, prop)
        colecao = colecao_do_tipo(p.fixed_type.identifier) if p.fixed_type else None
        opcoes = [b.name for b in getattr(bpy.data, colecao)][:LIMITE_LISTA] if colecao else []
        return {'rna': caminho_rna(dado, prop), 'tipo_rna': 'POINTER', 'rotulo': p.name,
                'valor': getattr(v, 'name', None) if v is not None else None,
                'colecao': colecao, 'opcoes': opcoes, 'editavel': not p.is_readonly,
                'op_novo': kw.get('new') or None, 'op_abrir': kw.get('open') or None,
                'op_desvincular': kw.get('unlink') or None}
    # template_preview(id, show_buttons, parent, slot, preview_id)
    bloco = args[0] if args else kw.get('id')
    return {'id': {'id_tipo': type(bloco).__name__, 'id': getattr(bloco, 'name', None)} if bloco is not None else None,
            'mostrar_botoes': kw.get('show_buttons', True)}


class ContextoFalso:
    """Contexto de desenho fora da janela: valores próprios, senão bpy.context, senão None."""

    def __init__(self, **valores):
        object.__setattr__(self, '_v', valores)

    def __getattr__(self, k):
        if k in self._v:
            return self._v[k]
        return getattr(bpy.context, k, None)


class EspacoPropriedades:
    """Substituto de SpaceProperties (space_data) sem janela."""
    type = 'PROPERTIES'
    pin_id = None
    use_pin_id = False
    context = 'OBJECT'
    context_valid_flag = 0xFFFF
    texture_context = 'MATERIAL'

    def __getattr__(self, k):
        return None


class SelfFalso:
    """Substituto do `self` do painel: layout falso + atributos e métodos da classe."""

    def __init__(self, cls, layout):
        object.__setattr__(self, '_cls', cls)
        object.__setattr__(self, 'layout', layout)

    def __getattr__(self, k):
        import inspect
        bruto = inspect.getattr_static(self._cls, k)
        v = getattr(self._cls, k)
        if isinstance(bruto, (staticmethod, classmethod)):
            return v
        if callable(v) and not isinstance(v, type):
            func = getattr(v, '__func__', v)
            return func.__get__(self, type(self))
        return v


def desenhar(cls, ctx, cabecalho=True):
    """Roda poll + draw_header + draw de um painel. Devolve (json, contagem, erro)."""
    wm = bpy.context.window_manager
    antes = getattr(wm, 'ae_object_panel_category', None)
    try:
        return _desenhar(cls, ctx, cabecalho)
    finally:
        if antes is not None:
            try:
                wm.ae_object_panel_category = antes
            except Exception:
                pass


def _desenhar(cls, ctx, cabecalho):
    reg = {}
    raiz = LayoutFalso('painel', reg, id=cls.__name__, rotulo=getattr(cls, 'bl_label', ''))
    # Abas de categoria do editor (Object Physics, etc.): a UI Web escolhe a aba.
    cat = getattr(cls, 'ae_category', None)
    if cat is not None:
        wm = bpy.context.window_manager
        for nome in ('ae_object_panel_category',):
            try:
                setattr(wm, nome, cat)
            except Exception:
                pass
    poll = getattr(cls, 'poll', None)
    if poll is not None:
        try:
            if not poll(ctx):
                return None, reg, 'poll falso'
        except Exception as e:
            return None, reg, 'poll: %s: %s' % (type(e).__name__, e)
    eu = SelfFalso(cls, raiz)
    try:
        if cabecalho and hasattr(cls, 'draw_header'):
            cab = LayoutFalso('cabecalho', reg)
            object.__setattr__(eu, 'layout', cab)
            cls.draw_header(eu, ctx)
            raiz._no['cabecalho'] = cab._no
            object.__setattr__(eu, 'layout', raiz)
        cls.draw(eu, ctx)
    except Exception as e:
        return raiz.para_json(), reg, 'draw: %s: %s' % (type(e).__name__, e)
    return raiz.para_json(), reg, None


COLECOES = {'Object': 'objects', 'Mesh': 'meshes', 'Material': 'materials', 'Scene': 'scenes',
            'World': 'worlds', 'Lamp': 'lamps', 'Camera': 'cameras', 'Texture': 'textures'}


# Tipos de bloco aceitos como valor de ponteiro (por nome, na coleção do tipo).
POINTER_TIPOS = {'Material', 'World', 'Texture', 'Image', 'Mesh', 'Camera', 'Lamp', 'Object',
                 'Group', 'Action', 'Text', 'ParticleSettings', 'NodeTree', 'Sound'}
# Índice ativo de lista -> coleção irmã que ele indexa (validação de faixa).
LISTAS_INDICE = {'active_material_index': 'material_slots', 'active_texture_index': 'texture_slots',
                 'active_particle_system_index': 'particle_systems'}


def escrever(rna, valor, indice=None):
    """Escreve de volta um caminho vindo da UI Web, sem eval: só bloco ID conhecido + path_resolve."""
    colecao = COLECOES.get(rna['id_tipo'])
    if colecao is None:
        raise ValueError('tipo de bloco não permitido: %r' % rna['id_tipo'])
    dono = getattr(bpy.data, colecao)[rna['id']]  # KeyError se apagaram ou renomearam
    base, _, prop = rna['caminho'].rpartition('.')
    alvo = dono.path_resolve(base) if base else dono
    if prop not in alvo.bl_rna.properties or alvo.bl_rna.properties[prop].is_readonly:
        raise ValueError('propriedade não editável: %r' % prop)
    p = alvo.bl_rna.properties[prop]
    if p.type == 'POINTER':
        # Só por nome, dentro da coleção de bpy.data do tipo fixo da prop.
        if indice is not None:
            raise ValueError('ponteiro não tem índice')
        tipo = p.fixed_type.identifier if p.fixed_type else None
        if tipo not in POINTER_TIPOS:
            raise ValueError('ponteiro de tipo não permitido: %r' % tipo)
        colecao = colecao_do_tipo(tipo)
        if valor is None:
            if p.is_never_none:
                raise ValueError('ponteiro não pode ficar vazio: %r' % prop)
            setattr(alvo, prop, None)
        else:
            if not isinstance(valor, str):
                raise ValueError('ponteiro espera nome (str)')
            setattr(alvo, prop, getattr(bpy.data, colecao)[valor])  # KeyError se não existe
        v = getattr(alvo, prop)
        return getattr(v, 'name', None) if v is not None else None
    if p.type == 'INT' and indice is None and p.array_length == 0:
        if isinstance(valor, bool) or not isinstance(valor, int):
            raise ValueError('inteiro esperado')
        if not (p.hard_min <= valor <= p.hard_max):
            raise ValueError('fora do intervalo: %r' % valor)
        lista = LISTAS_INDICE.get(prop)
        if lista and hasattr(alvo, lista) and not (0 <= valor < len(getattr(alvo, lista))):
            raise ValueError('índice fora da lista %s: %r' % (lista, valor))
    if indice is None:
        setattr(alvo, prop, valor)
    else:
        getattr(alvo, prop)[indice] = valor
    return getattr(alvo, prop)


def contexto_para(obj, cena=None):
    """ContextoFalso de Properties para `obj` (pode ser None); torna-o ativo."""
    cena = cena or bpy.context.scene
    if obj is not None:
        cena.objects.active = obj
    dado = obj.data if obj is not None else None
    tipo = obj.type if obj is not None else None
    return ContextoFalso(
        object=obj, active_object=obj, scene=cena, world=cena.world,
        mesh=dado if tipo == 'MESH' else None,
        lamp=dado if tipo == 'LAMP' else None,
        camera=dado if tipo == 'CAMERA' else None,
        material=obj.active_material if obj is not None else None, material_slot=None,
        texture=None, texture_slot=None, bone=None, edit_bone=None,
        pose_bone=None, armature=None, curve=None, meta_ball=None, lattice=None,
        speaker=None, particle_system=None, particle_settings=None,
        render_layer=cena.render.layers.active, space_data=EspacoPropriedades(),
        area=None, region=None, user_preferences=bpy.context.user_preferences)


def paineis_properties():
    """Classes de painel do editor Properties, na ordem de registro."""
    return [c for c in bpy.types.Panel.__subclasses__()
            if getattr(c, 'bl_space_type', '') == 'PROPERTIES']


def exportar_paineis(obj, cena=None):
    """Todos os painéis desenháveis para `obj`: {nome: {aba, ordem, arvore}}."""
    ctx = contexto_para(obj, cena)
    saida = {}
    for c in paineis_properties():
        js, _reg, erro = desenhar(c, ctx)
        if js is None or erro:
            continue
        saida[c.__name__] = {'aba': getattr(c, 'bl_context', ''), 'ordem': len(saida), 'arvore': js}
    return saida
