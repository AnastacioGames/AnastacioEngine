"""Prévia na 3D View, Fase 1 (docs/plano-previa-viewport.md): Custom 2D Filters na viewport com
Game Preview > 2D Filters. Um atuador Custom Filter (pass 0) com Text que inverte a imagem misturada
pela propriedade float "forca" do dono (Smart 2D Filter, uniform pela propriedade). Confere que a
prévia ligada inverte como o jogo e que, desligada, nada muda."""
from PIL import Image, ImageStat
from rodar import py

L, A = 960, 540

CENA = '''
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = %d, %d, 100
bpy.ops.mesh.primitive_plane_add(radius=20)
for i in range(-3, 4):
    bpy.ops.mesh.primitive_cube_add(location=(i * 3, 6, 1))
ob = bpy.context.active_object
txt = bpy.data.texts.new('inverter.glsl')
txt.write("""uniform sampler2D bgl_RenderedTexture;
uniform float forca; // @min 0 @max 1
void main()
{
    vec4 c = texture2D(bgl_RenderedTexture, gl_TexCoord[0].st);
    gl_FragColor = vec4(mix(c.rgb, 1.0 - c.rgb, forca), 1.0);
}
""")
bpy.ops.object.game_property_new(type='FLOAT', name='forca')
ob.game.properties['forca'].value = 1.0
bpy.ops.logic.sensor_add(type='ALWAYS', object=ob.name)
bpy.ops.logic.actuator_add(type='FILTER_2D', object=ob.name)
s, a = ob.game.sensors[-1], ob.game.actuators[-1]
a.mode = 'CUSTOMFILTER'
a.glsl_shader = txt
a.filter_pass = 0
bpy.ops.logic.controller_add(type='LOGIC_AND', object=ob.name)
c = ob.game.controllers[-1]
s.link(c)
a.link(c)
''' % (L, A)

RENDER = '''
import bpy
for a in bpy.context.screen.areas:
    if a.type == 'VIEW_3D':
        sp = a.spaces.active
        sp.region_3d.view_perspective = 'CAMERA'
        sp.viewport_shade = 'SOLID'
        sp.show_only_render = True
        sp.fx_settings.use_game_2d_filters = %s
        ov = dict(bpy.context.copy(), area=a, region=[r for r in a.regions if r.type == 'WINDOW'][0])
bpy.ops.render.opengl(ov, view_context=True)
bpy.data.images['Render Result'].save_render(r'%s')
resultado = 'ok'
'''


def media(png):
    return ImageStat.Stat(Image.open(png).convert('L')).mean[0]


def testar(t):
    cena = t.gerar(CENA)
    jogo_png, on_png, off_png = (str(t.pasta / n) for n in ('jogo.png', 'on.png', 'off.png'))

    j = t.jogo(cena, largura=L, altura=A)
    j.esperar(frames=30)
    j.tela(arquivo=jogo_png)

    e = t.editor(cena)
    py(e, RENDER % ('False', off_png))
    py(e, RENDER % ('True', on_png))

    jogo, on, off = media(jogo_png), media(on_png), media(off_png)
    t.nota('luminância média: jogo %.1f, prévia %.1f, sem prévia %.1f (invertida esperada %.1f)'
           % (jogo, on, off, 255 - off))
    assert abs(on - (255 - off)) < 12, 'a prévia não inverteu a imagem'
    assert abs(jogo - on) < abs(jogo - off), 'o jogo não bate com a prévia'
