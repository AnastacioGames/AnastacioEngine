"""Camera FX test scene: focus sensor, tracking, Camera FX filters and shake.

Run with:  RangeEngine -b --python tools/create_camera_fx_scene.py -- <output.range> [auto_quit]
In game: 1 normal, 2 space, 3 hell, 4 underwater background.
With auto_quit the game prints the focus values, removes the target and quits by itself.
"""
import bpy
import sys
import math

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "camera_fx_test.range"
auto_quit = len(argv) > 1 and argv[1] == "auto_quit"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 960
scene.game_settings.resolution_y = 540
world = bpy.data.worlds.new("CameraFX World")
world.horizon_color = (0.35, 0.5, 0.7)
scene.world = world


def material(name, color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    return mat


bpy.ops.mesh.primitive_plane_add(location=(0, 20, 0))
ground = bpy.context.object
ground.name = "Ground"
ground.scale = (30, 40, 1)
ground.data.materials.append(material("GroundMat", (0.3, 0.3, 0.3)))

# Scenery at many depths to see the depth of field and the speed blur.
for i in range(12):
    bpy.ops.mesh.primitive_cube_add(location=((-1) ** i * 4, i * 5 - 5, 1))
    pillar = bpy.context.object
    pillar.name = "Pillar.%02d" % i
    pillar.scale = (0.6, 0.6, 1 + (i % 3))
    pillar.data.materials.append(material("PillarMat%d" % i, (0.9, 0.3 + 0.05 * i, 0.1)))

# Focus target: marked by the property "foco" = True and moving side to side.
bpy.ops.mesh.primitive_uv_sphere_add(location=(0, 12, 1.6))
target = bpy.context.object
target.name = "Alvo"
target.data.materials.append(material("AlvoMat", (0.1, 0.8, 1.0)))
bpy.ops.object.game_property_new(type='BOOL', name="foco")
target.game.properties["foco"].value = True
bpy.ops.object.game_property_new(type='FLOAT', name="raio")
target.game.properties["raio"].value = 1.1

mover = bpy.data.texts.new("alvo_move.py")
mover.write('''import Range, math
own = Range.logic.getCurrentController().owner
t = own.get("t", 0.0) + 1.0 / 60.0
own["t"] = t
own.worldPosition = (math.sin(t * 0.8) * 6.0, 12.0 + math.cos(t * 0.5) * 6.0, 1.6)
''')
bpy.context.scene.objects.active = target
bpy.ops.logic.sensor_add(type='ALWAYS', object=target.name)
bpy.ops.logic.controller_add(type='PYTHON', object=target.name)
target.game.sensors[-1].use_pulse_true_level = True
target.game.controllers[-1].text = mover
target.game.sensors[-1].link(target.game.controllers[-1])

# Camera with every feature on.
bpy.ops.object.camera_add(location=(0, -8, 3), rotation=(math.radians(80), 0, 0))
cam = bpy.context.object
cam.name = "CameraFX"
scene.camera = cam
fx = cam.data.game_fx
fx.focus_mode = 'PROPERTY'
fx.focus_property = "foco"
fx.focus_range = 2.0
fx.track_mode = 'DRONE'
fx.track_speed = 0.3
fx.track_screen_offset = (0.0, -0.1)
fx.use_dof = True
fx.dof_quality = 'MEDIUM'
fx.dof_blur = 8.0
fx.use_cat_eye = True
fx.use_speed_blur = True
fx.use_directional_blur = True
fx.use_chromatic = True
fx.use_vignette = True
fx.fisheye_strength = 0.1
cam.data.gpu_dof.blades = 6

probe = bpy.data.texts.new("camera_probe.py")
probe.write('''import Range
cam = Range.logic.getCurrentController().owner
frame = cam.get("frame", 0) + 1
cam["frame"] = frame
AUTO_QUIT = %s
if frame %% 30 == 0:
    target = cam.focusTarget
    print("[camfx] frame=%%d target=%%s valid=%%s dist=%%.2f pos=%%s screen=%%s speed=%%.2f trauma=%%.2f"
          %% (frame, target.name if target else None, cam.focusValid, cam.focusDistance,
             [round(v, 2) for v in cam.focusPosition], [round(v, 2) for v in cam.focusScreenPosition],
             cam.cameraSpeed, cam.shakeTrauma), flush=True)
if frame == 60:
    cam.shake(0.8, 1.5)
if frame == 150 and AUTO_QUIT:
    scene = Range.logic.getCurrentScene()
    alvo = scene.objects.get("Alvo")
    if alvo:
        alvo.endObject()
        print("[camfx] target removed", flush=True)
if frame == 200 and AUTO_QUIT:
    cam.useDof = False
    cam.useSpeedBlur = cam.useDirectionalBlur = cam.useChromatic = cam.useVignette = False
    print("[camfx] effects off", flush=True)
if frame == 260 and AUTO_QUIT:
    print("[camfx] done", flush=True)
    Range.logic.endGame()
''' % ("True" if auto_quit else "False"))
bpy.context.scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
cam.game.sensors[-1].use_pulse_true_level = True
cam.game.controllers[-1].text = probe
cam.game.sensors[-1].link(cam.game.controllers[-1])

# Focus background (keys 1-4): keeps only the focus target and replaces the rest.
SHADER = r'''
uniform sampler2D bgl_RenderedTexture;
uniform sampler2D bgl_DepthTexture;
uniform float bgl_RenderedTextureWidth;
uniform float bgl_RenderedTextureHeight;

uniform int u_mode;           // 0 off, 1 space, 2 hell, 3 underwater
uniform float u_time;
uniform float u_znear;
uniform float u_zfar;
uniform float u_focusDist;    // cam.focusDistance
uniform float u_tolerance;    // depth band around the target (m)
uniform vec2 u_focusScreen;   // target on screen, bottom-up
uniform float u_screenRadius; // target radius on screen (height units)

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p)
{
    vec2 i = floor(p), f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
}
float fbm(vec2 p)
{
    float s = 0.0, a = 0.5;
    for (int i = 0; i < 5; ++i) { s += noise(p) * a; p = p * 2.03 + 1.7; a *= 0.5; }
    return s;
}
float linearDepth(vec2 uv)
{
    float d = texture2D(bgl_DepthTexture, uv).r;
    return u_znear * u_zfar / (u_zfar - d * (u_zfar - u_znear));
}

vec3 stars(vec2 p, float density)
{
    vec2 cell = floor(p), f = fract(p) - 0.5;
    float h = hash(cell);
    if (h > density) return vec3(0.0);
    vec2 off = vec2(hash(cell + 3.1), hash(cell + 7.7)) - 0.5;
    float d = length(f - off * 0.7);
    float twinkle = 0.6 + 0.4 * sin(u_time * (2.0 + h * 6.0) + h * 40.0);
    return vec3(0.8 + h, 0.85, 1.0) * smoothstep(0.08, 0.0, d) * twinkle;
}

vec3 space(vec2 p)
{
    float a = u_time * 0.01;
    p = mat2(cos(a), -sin(a), sin(a), cos(a)) * p;
    // Milky way: a tilted band of dust and glow.
    float band = exp(-pow((p.y + p.x * 0.35) * 2.2, 2.0));
    float dust = fbm(p * 3.0 + vec2(u_time * 0.005, 0.0));
    float lanes = smoothstep(0.45, 0.7, fbm(p * 6.0 + 4.0));
    vec3 col = vec3(0.01, 0.01, 0.03);
    col += band * mix(vec3(0.25, 0.15, 0.45), vec3(1.0, 0.8, 0.6), dust) * dust * 1.6 * (1.0 - lanes * 0.8);
    col += vec3(0.1, 0.25, 0.6) * pow(fbm(p * 1.5 + 9.0), 3.0) * 0.8;   // nebula
    col += vec3(0.6, 0.1, 0.3) * pow(fbm(p * 1.2 - 5.0), 4.0) * 0.8;
    col += stars(p * 90.0, 0.08) + stars(p * 40.0, 0.04) * 1.5 + stars(p * 200.0, 0.2) * band;
    return col;
}

vec3 hell(vec2 p, vec2 uv)
{
    // Flames rise from the bottom of the screen.
    vec2 q = vec2(p.x * 2.0, p.y * 1.5 - u_time * 1.2);
    float f = fbm(q + fbm(q * 1.5 + u_time * 0.3));
    float height = 1.0 - uv.y;
    float fire = smoothstep(0.2, 1.0, f * 1.4 * (0.3 + height * 1.4));
    vec3 col = mix(vec3(0.02, 0.0, 0.0), vec3(0.35, 0.02, 0.0), fbm(p * 2.0 - u_time * 0.1));
    col += fire * mix(vec3(0.9, 0.15, 0.0), vec3(1.0, 0.85, 0.3), fire * fire) * 1.5;
    // Embers.
    vec2 e = p * 25.0 + vec2(sin(u_time + p.y * 3.0), -u_time * 4.0);
    col += vec3(1.0, 0.5, 0.1) * stars(e, 0.05) * 2.0;
    return col;
}

vec3 water(vec2 p, vec2 uv)
{
    vec3 deep = vec3(0.0, 0.05, 0.15), shallow = vec3(0.0, 0.45, 0.6);
    vec3 col = mix(deep, shallow, uv.y);
    // Light shafts from the surface.
    float rays = pow(noise(vec2(p.x * 6.0 + p.y * 1.5 + u_time * 0.3, 0.0)), 3.0);
    col += vec3(0.4, 0.8, 0.9) * rays * uv.y * 0.6;
    // Caustics.
    vec2 c = p * 5.0;
    float k = abs(sin(c.x + fbm(c + u_time * 0.4) * 4.0) * sin(c.y + fbm(c - u_time * 0.3) * 4.0));
    col += vec3(0.3, 0.7, 0.8) * pow(1.0 - k, 8.0) * 0.5;
    // Bubbles going up.
    vec2 b = vec2(p.x * 12.0, p.y * 12.0 - u_time * 1.5);
    vec2 cell = floor(b), f = fract(b) - 0.5;
    float h = hash(cell);
    if (h < 0.12) {
        f.x += sin(u_time * 2.0 + h * 30.0) * 0.2;
        float r = 0.08 + h * 0.5;
        float ring = smoothstep(0.03, 0.0, abs(length(f) - r));
        col += vec3(0.7, 0.9, 1.0) * ring * 0.6;
    }
    return col;
}

void main()
{
    vec2 uv = gl_TexCoord[0].st;
    vec4 scene = texture2D(bgl_RenderedTexture, uv);
    if (u_mode == 0) {
        gl_FragColor = scene;
        return;
    }

    float aspect = bgl_RenderedTextureWidth / bgl_RenderedTextureHeight;
    vec2 p = (uv - 0.5) * vec2(aspect, 1.0);

    // Mask: depth near the focus AND near the target on screen.
    float z = linearDepth(uv);
    float depthMask = 1.0 - smoothstep(u_tolerance * 0.6, u_tolerance, abs(z - u_focusDist));
    float sd = length((uv - u_focusScreen) * vec2(aspect, 1.0));
    float screenMask = 1.0 - smoothstep(u_screenRadius, u_screenRadius * 1.15, sd);
    float mask = depthMask * screenMask;

    vec3 bg;
    vec3 subject = scene.rgb;
    if (u_mode == 1) {
        bg = space(p);
        subject *= vec3(0.75, 0.8, 1.0);                               // cold starlight
    }
    else if (u_mode == 2) {
        bg = hell(p, uv);
        subject *= vec3(1.2, 0.6, 0.4);                                // lit by the fire
        subject += vec3(0.4, 0.1, 0.0) * (0.5 + 0.5 * sin(u_time * 9.0)) * 0.3;
    }
    else {
        // Underwater: the whole picture wobbles a little.
        vec2 w = uv + vec2(sin(uv.y * 20.0 + u_time * 2.0), cos(uv.x * 18.0 + u_time * 1.7)) * 0.003;
        subject = texture2D(bgl_RenderedTexture, w).rgb * vec3(0.5, 0.85, 1.0);
        bg = water(p, uv);
    }

    // Soft glow around the cut so the subject does not look pasted.
    float rim = smoothstep(0.0, 0.5, mask) * (1.0 - smoothstep(0.5, 1.0, mask));
    vec3 glow = u_mode == 1 ? vec3(0.4, 0.5, 1.0) : (u_mode == 2 ? vec3(1.0, 0.4, 0.0) : vec3(0.3, 0.8, 1.0));
    vec3 col = mix(bg, subject, mask) + glow * rim * 0.4;
    gl_FragColor = vec4(col, 1.0);
}
'''

controller = '''import Range

SHADER = %r
NAMES = {0: "normal", 1: "espaco", 2: "inferno", 3: "agua"}
KEYS = {Range.events.ONEKEY: 0, Range.events.TWOKEY: 1, Range.events.THREEKEY: 2, Range.events.FOURKEY: 3}

cont = Range.logic.getCurrentController()
cam = cont.owner
scene = Range.logic.getCurrentScene()

if "bg_filter" not in cam:
    cam["bg_filter"] = scene.filterManager.addFilter(30, Range.logic.RAS_2DFILTER_CUSTOMFILTER, SHADER)
    cam["bg_mode"] = 1
    print("[focusbg] 1 normal, 2 espaco, 3 inferno, 4 agua", flush=True)

keyboard = Range.logic.keyboard
for key, mode in KEYS.items():
    if keyboard.events.get(key) == Range.logic.KX_INPUT_JUST_ACTIVATED:
        cam["bg_mode"] = mode
        print("[focusbg] modo", NAMES[mode], flush=True)

f = cam["bg_filter"]
target = cam.focusTarget
mode = cam["bg_mode"] if (target and cam.focusValid) else 0
f.setUniform1i("u_mode", mode)
f.setUniform1f("u_time", Range.logic.getRealTime())
if mode:
    radius = target.get("raio", 1.0)
    sx, sy = cam.getScreenPosition(target)
    # Target size on screen: project a point "radius" meters to the side of it.
    side = target.worldPosition + cam.worldOrientation.col[1] * radius
    ex, ey = cam.getScreenPosition(side)
    f.setUniform1f("u_znear", cam.near)
    f.setUniform1f("u_zfar", cam.far)
    f.setUniform1f("u_focusDist", cam.getDistanceTo(target))
    f.setUniform1f("u_tolerance", radius * 1.2)
    f.setUniform2f("u_focusScreen", sx, 1.0 - sy)
    f.setUniform1f("u_screenRadius", max(abs(ey - sy), 0.02) * 1.1)
''' % SHADER

text = bpy.data.texts.new("focus_background.py")
text.write(controller)
bpy.context.scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
cam.game.sensors[-1].use_pulse_true_level = True
cam.game.controllers[-1].text = text
cam.game.sensors[-1].link(cam.game.controllers[-1])

bpy.ops.wm.save_as_mainfile(filepath=output)
print("saved", output)
