"""Save As Runtime gera um pacote que abre sozinho, com Python, DLLs e a cena embutida."""
import shutil

CENA = '''
import bpy.utils, importlib.util, os
caminho = os.path.join(bpy.utils.resource_path('LOCAL'), 'scripts', 'addons', 'game_engine_save_as_runtime.py')
spec = importlib.util.spec_from_file_location('exportar_teste', caminho)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
cube = bpy.data.objects['Cube']
cube.name = 'Marcado'
cube.game.physics_type = 'NO_COLLISION'
bpy.context.scene.game_settings.show_fullscreen = False  # tela cheia não abre no desktop invisível
pasta = os.path.join(os.path.dirname(saida), 'pacote')
os.makedirs(pasta)
player = os.path.join(os.path.dirname(bpy.app.binary_path), 'AnastacioRuntime.exe')
assert m.WriteRuntime(player, os.path.join(pasta, 'Jogo.exe'), True, True, True, False, True)
'''


def testar(t):
    t.gerar(CENA, limite=540)  # copiar o Python leva minutos
    pasta = t.pasta / 'pacote'
    t.abertos.append(lambda: shutil.rmtree(pasta, ignore_errors=True))  # roda por último: o pacote é grande
    for parte in ('Jogo.exe', 'python311.dll', 'blender.crt/blender.crt.manifest', '2.79/python/lib/encodings/__init__.py'):
        assert (pasta / parte).exists(), 'faltou no pacote: ' + parte
    j = t.jogo(pasta / 'Jogo.exe', exportado=True, espera=300)  # 1ª abertura de pacote novo é lenta
    j.esperar(frames=5)
    nomes = j.py(codigo="resultado = [o.name for o in cena().objects]")
    assert 'Marcado' in nomes, 'a cena embutida não veio: %s' % nomes
    origem = j.py(codigo="import sys; resultado = sys.executable + ' | ' + logic.expandPath('//')")
    assert 'pacote' in origem, 'o jogo não rodou de dentro do pacote: %s' % origem
    t.nota('%d objetos; %s' % (len(nomes), origem))
