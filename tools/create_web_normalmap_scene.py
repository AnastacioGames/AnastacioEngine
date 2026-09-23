"""Run with RangeEngine -b --python tools/create_web_normalmap_scene.py.

Teste de normal map desktop x Web usando a cena que o motor abre ao iniciar
(source/release/datafiles/startup.blend: cubo e plano com projects-teste/cubo_normal.dds como normal
map, camera e Sun). A cena e aberta como esta; so as imagens sao convertidas para caminho absoluto e
empacotadas, para o .range rodar em qualquer pasta e no pacote Web. Rode o mesmo
build-web/bin/web-normalmap.range com RangeRuntime.exe e no navegador e compare.
Saida: build-web/bin/web-normalmap.range.
"""
import bpy
from pathlib import Path

root = Path(__file__).resolve().parents[1]
out_dir = root / 'build-web' / 'bin'
out_dir.mkdir(parents=True, exist_ok=True)
startup = root / 'source' / 'release' / 'datafiles' / 'startup.blend'

bpy.ops.wm.open_mainfile(filepath=str(startup))
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'

# Os caminhos do startup.blend sao relativos a pasta instalada (build/bin/<versao>/datafiles), nao a do
# fonte: acha cada imagem pelo nome nas pastas de recursos do repositorio e empacota.
search = [root / 'projects-teste', root / 'tools' / 'matcaps-texture']
for img in bpy.data.images:
    name = Path(img.filepath.replace('\\', '/')).name
    resolved = next((d / name for d in search if (d / name).exists()), Path(name))
    if resolved.exists():
        img.filepath = str(resolved.resolve())
        img.pack()
        print('[web-normalmap] imagem empacotada: %s' % img.name)
    else:
        print('[web-normalmap] AVISO imagem nao encontrada: %s -> %s' % (img.name, resolved))

output = out_dir / 'web-normalmap.range'
bpy.ops.wm.save_as_mainfile(filepath=str(output))
print('[web-normalmap] saved', str(output))
