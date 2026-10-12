# Copia o ocean2DFilter.blend (Seascape em 2D Filter) e adiciona um cubo que boia.
# - O filtro passa a usar a camera real (bgl_InverseViewMatrix/ProjectionMatrix)
#   e compoe os objetos da cena pela profundidade (bgl_DepthTexture).
# - A altura das ondas e recalculada em Python (mesmas formulas do shader) para o empuxo.
# Uso:
#   AnastacioEngine.exe -b ocean2DFilter.blend --factory-startup --python criar_cena_oceano_cubo.py -- saida.range
import bpy
import sys
from mathutils import Vector

saida = sys.argv[sys.argv.index('--') + 1]

SHADER = r"""
// "Seascape" by Alexander Alekseev aka TDM - 2014
// License Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported License.
// Adaptado: camera da cena, eixo Z para cima, composicao por profundidade.

uniform sampler2D bgl_RenderedTexture;
uniform sampler2D bgl_DepthTexture;
uniform mat4 bgl_InverseViewMatrix;
uniform mat4 bgl_InverseProjectionMatrix;
uniform float iGlobalTime;

const int NUM_STEPS = 8;
const int ITER_GEOMETRY = 3;
const int ITER_FRAGMENT = 5;
const float SEA_HEIGHT = 0.6;
const float SEA_CHOPPY = 4.0;
const float SEA_SPEED = 0.8;
const float SEA_FREQ = 0.16;
const vec3 SEA_BASE = vec3(0.1,0.19,0.22);
const vec3 SEA_WATER_COLOR = vec3(0.8,0.9,0.6);
const mat2 octave_m = mat2(1.6,1.2,-1.2,1.6);

// hash sem sin(): da o mesmo resultado na GPU e no Python (oceano_boia.py)
float hash(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}
float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f*f*(3.0-2.0*f);
    return -1.0+2.0*mix(mix(hash(i + vec2(0.0,0.0)), hash(i + vec2(1.0,0.0)), u.x),
                        mix(hash(i + vec2(0.0,1.0)), hash(i + vec2(1.0,1.0)), u.x), u.y);
}

float diffuse(vec3 n, vec3 l, float p) { return pow(dot(n,l) * 0.4 + 0.6, p); }
float specular(vec3 n, vec3 l, vec3 e, float s) {
    float nrm = (s + 8.0) / (3.1415 * 8.0);
    return pow(max(dot(reflect(e,n),l),0.0),s) * nrm;
}
vec3 getSkyColor(vec3 e) {
    e.z = max(e.z, 0.0);
    return vec3(pow(1.0-e.z,2.0), 1.0-e.z, 0.6+(1.0-e.z)*0.4);
}

float sea_octave(vec2 uv, float choppy) {
    uv += noise(uv);
    vec2 wv = 1.0-abs(sin(uv));
    vec2 swv = abs(cos(uv));
    wv = mix(wv,swv,wv);
    return pow(1.0-pow(wv.x * wv.y,0.65),choppy);
}

float seaHeight(vec2 xy, int iters) {
    float t = iGlobalTime * SEA_SPEED;
    float freq = SEA_FREQ, amp = SEA_HEIGHT, choppy = SEA_CHOPPY;
    vec2 uv = xy; uv.x *= 0.75;
    float h = 0.0;
    for (int i = 0; i < ITER_FRAGMENT; i++) {
        if (i >= iters) break;
        float d = sea_octave((uv+t)*freq,choppy);
        d += sea_octave((uv-t)*freq,choppy);
        h += d * amp;
        uv *= octave_m; freq *= 1.9; amp *= 0.22;
        choppy = mix(choppy,1.0,0.2);
    }
    return h;
}
float map(vec3 p)          { return p.z - seaHeight(p.xy, ITER_GEOMETRY); }
float map_detailed(vec3 p) { return p.z - seaHeight(p.xy, ITER_FRAGMENT); }

vec3 getSeaColor(vec3 p, vec3 n, vec3 l, vec3 eye, vec3 dist) {
    float fresnel = 1.0 - max(dot(n,-eye),0.0);
    fresnel = pow(fresnel,3.0) * 0.65;
    vec3 reflected = getSkyColor(reflect(eye,n));
    vec3 refracted = SEA_BASE + diffuse(n,l,80.0) * SEA_WATER_COLOR * 0.12;
    vec3 color = mix(refracted,reflected,fresnel);
    float atten = max(1.0 - dot(dist,dist) * 0.001, 0.0);
    color += SEA_WATER_COLOR * (p.z - SEA_HEIGHT) * 0.18 * atten;
    color += vec3(specular(n,l,eye,60.0));
    return color;
}

vec3 getNormal(vec3 p, float eps) {
    vec3 n;
    float h = map_detailed(p);
    n.x = map_detailed(vec3(p.x+eps,p.y,p.z)) - h;
    n.y = map_detailed(vec3(p.x,p.y+eps,p.z)) - h;
    n.z = eps;
    return normalize(n);
}

float heightMapTracing(vec3 ori, vec3 dir, out vec3 p) {
    float tm = 0.0;
    float tx = 1000.0;
    p = ori + dir * tx;
    float hx = map(p);
    if (hx > 0.0) return -1.0; // nao bate no mar (ceu)
    float hm = map(ori);
    float tmid = 0.0;
    for (int i = 0; i < NUM_STEPS; i++) {
        tmid = mix(tm,tx, hm/(hm-hx));
        p = ori + dir * tmid;
        float hmid = map(p);
        if (hmid < 0.0) { tx = tmid; hx = hmid; }
        else            { tm = tmid; hm = hmid; }
    }
    return tmid;
}

void main() {
    vec2 uv = gl_TexCoord[0].st;
    vec2 ndc = uv * 2.0 - 1.0;

    // raio da camera real
    vec4 v = bgl_InverseProjectionMatrix * vec4(ndc, 1.0, 1.0);
    v /= v.w;
    vec3 ori = bgl_InverseViewMatrix[3].xyz;
    vec3 dir = normalize(mat3(bgl_InverseViewMatrix) * v.xyz);

    // distancia dos objetos da cena
    float d = texture2D(bgl_DepthTexture, uv).r;
    vec4 vp = bgl_InverseProjectionMatrix * vec4(ndc, d * 2.0 - 1.0, 1.0);
    float sceneDist = (d >= 0.99999) ? 1e9 : length(vp.xyz / vp.w);

    vec3 p;
    float tSea = heightMapTracing(ori, dir, p);
    vec3 light = normalize(vec3(0.0, 0.8, 1.0));

    vec3 color;
    if (tSea > 0.0 && tSea < sceneDist) {
        vec3 dist = p - ori;
        vec3 n = getNormal(p, dot(dist,dist) * (0.1 / 1280.0));
        color = mix(getSkyColor(dir), getSeaColor(p,n,light,dir,dist),
                    pow(smoothstep(0.0,-0.05,dir.z),0.3));
        color = pow(color, vec3(0.75));
    }
    else if (sceneDist < 1e8) {
        color = texture2D(bgl_RenderedTexture, uv).rgb; // objeto na frente da agua
    }
    else {
        color = pow(getSkyColor(dir), vec3(0.75));
    }
    gl_FragColor = vec4(color, 1.0);
}
"""

BOIA = r'''import bge
import math

# Mesmas formulas do oceanFilter (seaHeight com ITER_GEOMETRY = 3).
SEA_HEIGHT = 0.6
SEA_CHOPPY = 4.0
SEA_SPEED = 0.8
SEA_FREQ = 0.16
ITER_GEOMETRY = 3

def _fract(x):
    return x - math.floor(x)

def _hash(px, py):
    a = _fract(px * 0.1031)
    b = _fract(py * 0.1031)
    c = _fract(px * 0.1031)
    k = a * (b + 33.33) + b * (c + 33.33) + c * (a + 33.33)
    a += k; b += k; c += k
    return _fract((a + b) * c)

def _noise(x, y):
    ix = math.floor(x); iy = math.floor(y)
    fx = x - ix; fy = y - iy
    ux = fx * fx * (3.0 - 2.0 * fx)
    uy = fy * fy * (3.0 - 2.0 * fy)
    a = _hash(ix, iy); b = _hash(ix + 1.0, iy)
    c = _hash(ix, iy + 1.0); d = _hash(ix + 1.0, iy + 1.0)
    return -1.0 + 2.0 * ((a + (b - a) * ux) + ((c + (d - c) * ux) - (a + (b - a) * ux)) * uy)

def _octave(x, y, choppy):
    n = _noise(x, y)
    x += n; y += n
    wx = 1.0 - abs(math.sin(x)); wy = 1.0 - abs(math.sin(y))
    sx = abs(math.cos(x)); sy = abs(math.cos(y))
    wx = wx + (sx - wx) * wx
    wy = wy + (sy - wy) * wy
    return (1.0 - (wx * wy) ** 0.65) ** choppy

def altura_mar(x, y, tempo):
    t = tempo * SEA_SPEED
    freq = SEA_FREQ; amp = SEA_HEIGHT; choppy = SEA_CHOPPY
    ux = x * 0.75; uy = y
    h = 0.0
    for _ in range(ITER_GEOMETRY):
        d = _octave((ux + t) * freq, (uy + t) * freq, choppy)
        d += _octave((ux - t) * freq, (uy - t) * freq, choppy)
        h += d * amp
        # GLSL: uv *= m  (vetor linha vezes mat2 coluna-major)
        ux, uy = ux * 1.6 + uy * 1.2, ux * -1.2 + uy * 1.6
        freq *= 1.9; amp *= 0.22
        choppy = choppy + (1.0 - choppy) * 0.2
    return h

# cantos de baixo do cubo (coordenadas locais)
PONTOS = [(-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (-0.5, 0.5, -0.5)]
EMPUXO = 9.0     # forca por canto por metro submerso (massa 1)
ARRASTO = 0.6

def tick(cont):
    own = cont.owner
    scene = bge.logic.getCurrentScene()
    cam = scene.active_camera
    tempo = cam["iGlobalTime"] if "iGlobalTime" in cam else 0.0
    dt = 1.0 / bge.logic.getLogicTicRate()

    vel = own.worldLinearVelocity
    submerso = 0
    for local in PONTOS:
        p = own.worldTransform * bge.logic.mathutils.Vector(local) if hasattr(bge.logic, "mathutils") else own.worldTransform * __import__("mathutils").Vector(local)
        h = altura_mar(p.x, p.y, tempo)
        prof = h - p.z
        if prof > 0.0:
            submerso += 1
            f = EMPUXO * min(prof, 1.0)
            own.applyImpulse(p, (0.0, 0.0, f * dt), False)
    if submerso:
        k = ARRASTO * submerso / 4.0
        own.worldLinearVelocity = vel * (1.0 - k * dt * 3.0)
        av = own.worldAngularVelocity
        own.worldAngularVelocity = av * (1.0 - k * dt * 3.0)

    # interacao: setas/WASD empurram, espaco pula, R volta ao inicio
    kb = bge.logic.keyboard.inputs
    ev = bge.events
    def ativo(*keys):
        return any(kb[k].active for k in keys)
    forca = 6.0 * dt
    if ativo(ev.WKEY, ev.UPARROWKEY):    own.applyImpulse(own.worldPosition, (0, forca, 0), False)
    if ativo(ev.SKEY, ev.DOWNARROWKEY):  own.applyImpulse(own.worldPosition, (0, -forca, 0), False)
    if ativo(ev.AKEY, ev.LEFTARROWKEY):  own.applyImpulse(own.worldPosition, (-forca, 0, 0), False)
    if ativo(ev.DKEY, ev.RIGHTARROWKEY): own.applyImpulse(own.worldPosition, (forca, 0, 0), False)
    if kb[ev.SPACEKEY].activated and submerso:
        own.applyImpulse(own.worldPosition, (0, 0, 5.0), False)
    if kb[ev.RKEY].activated:
        own.worldPosition = (0.0, 0.0, 4.0)
        own.worldLinearVelocity = (0, 0, 0)
        own.worldAngularVelocity = (0, 0, 0)
'''

# A linha do Vector acima fica simples:
BOIA = BOIA.replace(
    'p = own.worldTransform * bge.logic.mathutils.Vector(local) if hasattr(bge.logic, "mathutils") else own.worldTransform * __import__("mathutils").Vector(local)',
    'p = own.worldTransform * Vector(local)')
BOIA = BOIA.replace('import bge\nimport math\n', 'import bge\nimport math\nfrom mathutils import Vector\n', 1)

CAMERA_SEGUE = r'''import bge
from mathutils import Vector

# camera acompanha o cubo de longe, mantendo o mesmo deslocamento
OFFSET = Vector((7.0, -7.0, 4.5))

def tick(cont):
    cam = cont.owner
    scene = bge.logic.getCurrentScene()
    cubo = scene.objects.get("CuboBoia")
    if cubo is None:
        return
    alvo = cubo.worldPosition.copy()
    alvo.z = 0.8
    desejado = alvo + OFFSET
    cam.worldPosition = cam.worldPosition.lerp(desejado, 0.05)
    cam.alignAxisToVect(cam.worldPosition - alvo, 2, 1.0)
    cam.alignAxisToVect(Vector((0, 0, 1)), 1, 0.5)
'''

scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'

# shader do filtro
bpy.data.texts['oceanFilter'].from_string(SHADER)

# textos de logica
def texto(nome, conteudo):
    t = bpy.data.texts.get(nome) or bpy.data.texts.new(nome)
    t.from_string(conteudo)
    return t
texto('oceano_boia.py', BOIA)
texto('camera_segue.py', CAMERA_SEGUE)

def selecionar(obj):
    for o in scene.objects:
        o.select = False
    obj.select = True
    scene.objects.active = obj

# cubo
bpy.ops.mesh.primitive_cube_add(radius=0.5, location=(0.0, 0.0, 4.0))
cubo = bpy.context.active_object
cubo.name = 'CuboBoia'
mat = bpy.data.materials.new('CuboLaranja')
mat.diffuse_color = (1.0, 0.35, 0.05)
cubo.data.materials.append(mat)
cubo.game.physics_type = 'RIGID_BODY'
cubo.game.mass = 1.0
cubo.game.use_collision_bounds = True
cubo.game.collision_bounds_type = 'BOX'
cubo.game.damping = 0.1
cubo.game.rotation_damping = 0.3

selecionar(cubo)
bpy.ops.logic.sensor_add(type='ALWAYS', name='Sempre', object=cubo.name)
bpy.ops.logic.controller_add(type='PYTHON', name='Boia', object=cubo.name)
s = cubo.game.sensors['Sempre']
s.use_pulse_true_level = True
c = cubo.game.controllers['Boia']
c.mode = 'MODULE'
c.module = 'oceano_boia.tick'
s.link(c)

# camera: mira no cubo e acompanha
cam = scene.camera
cam.location = (7.0, -7.0, 5.3)
cam.rotation_euler = (Vector((0.0, 0.0, 0.8)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
selecionar(cam)
bpy.ops.logic.sensor_add(type='ALWAYS', name='SempreSegue', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', name='Segue', object=cam.name)
s = cam.game.sensors['SempreSegue']
s.use_pulse_true_level = True
c = cam.game.controllers['Segue']
c.mode = 'MODULE'
c.module = 'camera_segue.tick'
s.link(c)

scene.game_settings.physics_engine = 'BULLET'
scene.game_settings.resolution_x = 1600
scene.game_settings.resolution_y = 900
bpy.ops.wm.save_as_mainfile(filepath=saida, copy=True)
print('salvo', saida)
