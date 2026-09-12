import Range as bge
import time
from Range import logic as g
import Range.render as render

own = g.getCurrentController().owner
scene = g.getCurrentScene()
Camera = scene.active_camera

# ======================================================================
# ======================= PARAMETER ====================================
# ======================================================================


MAX_SHELLS   = 24        # REDUZIERT von 37
SHELL_COUNT  = 16        # REDUZIERT von 16 - weniger Shells = mehr FPS
SHELL_HEIGHT = 0.065     # Etwas höher kompensiert weniger Shells
UV_SCALE     = 8.0
WIND_POWER   = 2.0
COLOR_SHIFT  = 1.0
NOISE_POWER  = 1.0

BRIGHTNESS   = 1.8

# AGGRESSIVE LOD für massive Performance-Steigerung
LOD_START    = 20.0      # LOD startet früher
LOD_END      = 40.0     # Endet früher (statt 20)
LOD_MIN_SHELLS = 1      # Nur 1 Shell in der Ferne (statt 2)

# Alpha Clipping
ALPHA_CUTOFF = .5

# FRUSTUM CULLING - rendert nur sichtbare Bereiche
ENABLE_FRUSTUM_CULLING = True

# ======================================================================
# ============================= TIMER ==================================
# ======================================================================

def getTime():
    own['time'] = time.monotonic()
    own['init'] = True

if 'init' not in own:
    getTime()

own['timer'] = time.monotonic() - own['time']

# ======================================================================
# ==================== GLSL SETTINGS (Range/UPBGE) =====================
# ======================================================================

render.setGLSLMaterialSetting('lights', True)
render.setGLSLMaterialSetting('shaders', True)
render.setGLSLMaterialSetting('shadows', True)

# ======================================================================
# ============================= SHADERS ================================
# ======================================================================

# ============================ Vertex Shader ============================
vs = """
out vec3 normal_ws;
out vec3 world_pos;
out vec2 Tcoord1;
out vec2 diffuse_uv;
out vec2 height_uv;

uniform float uv_scale;
uniform mat4 ModelMatrix;

void main()
{
    vec4 wp = ModelMatrix * gl_Vertex;
    world_pos = wp.xyz;
    normal_ws = normalize(mat3(ModelMatrix) * gl_Normal);
    
    // gl_MultiTexCoord0 = Texture Slot 0 UV-Map Auswahl
    Tcoord1 = gl_MultiTexCoord0.xy * uv_scale;
    
    // gl_MultiTexCoord1 = Texture Slot 1 UV-Map Auswahl (Diffuse)
    diffuse_uv = gl_MultiTexCoord1.xy;
    
    // gl_MultiTexCoord2 = Texture Slot 2 UV-Map Auswahl (Height/Noise)
    height_uv = gl_MultiTexCoord2.xy;
    
    gl_Position = gl_Vertex;
}
"""

# =========================== Geometry Shader ===========================
gs = """
layout(triangles) in;
layout(triangle_strip, max_vertices = 75) out;  // REDUZIERT von 85

uniform mat4 ProjectionMatrix;
uniform mat4 ViewMatrix;
uniform mat4 ModelMatrix;

uniform int   shell_count;
uniform float shell_height;
uniform vec3  light_direction;
uniform sampler2D HeightMapExtra;
uniform vec3  camera_pos;
uniform float lod_start;
uniform float lod_end;
uniform int   lod_min_shells;
uniform bool  enable_frustum_culling;

in vec3 normal_ws[3];
in vec3 world_pos[3];
in vec2 Tcoord1[3];
in vec2 height_uv[3];
in vec2 diffuse_uv[3];

out vec2 Tcoord1_g;
out vec2 height_uv_g;
out vec2 diffuse_uv_g;
out float layers;
out float lighting;
out vec3 world_pos_g;
out vec3 normal_g;
out float heightFactor_g;

const int MAX_SHELLS = """ + str(MAX_SHELLS) + """;

void main()
{
    mat4 mvp = ProjectionMatrix * ViewMatrix * ModelMatrix;

    // ===========================================
    // FRÜHE ÜBERPRÜFUNGEN für maximale Performance
    // ===========================================
    
    // 1. HeightMap Check - komplett schwarze Bereiche überspringen
    float hVar0 = texture(HeightMapExtra, height_uv[0]).r;
    float hVar1 = texture(HeightMapExtra, height_uv[1]).r;
    float hVar2 = texture(HeightMapExtra, height_uv[2]).r;
    float maxHeight = max(max(hVar0, hVar1), hVar2);
    
    if (maxHeight < 0.001) {
        return;
    }

    // 2. Distanz-basiertes LOD
    vec3 triCenter = (world_pos[0] + world_pos[1] + world_pos[2]) / 3.0;
    float dist = length(triCenter - camera_pos);
    
    // 3. FRUSTUM CULLING - sehr weit entfernte Dreiecke komplett verwerfen
    if (enable_frustum_culling && dist > lod_end * 1.5) {
        return;
    }

    // 4. LOD Berechnung
    float lodT = clamp((dist - lod_start) / (lod_end - lod_start), 0.0, 1.0);
    float fLocalShellCount = mix(float(shell_count), float(lod_min_shells), lodT);
    int localShellCount = int(floor(fLocalShellCount + 0.5));
    localShellCount = clamp(localShellCount, 1, shell_count);

    // 5. ADAPTIVE SHELL GENERATION
    // Bei niedriger Shell-Anzahl jeden 2. Frame überspringen für noch mehr FPS
    int shellStep = (localShellCount <= 3) ? 1 : 1;

    for (int i = 0; i < MAX_SHELLS; i += shellStep)
    {
        if (i >= localShellCount)
            break;

        layers = float(i) / float(localShellCount);

        for (int vtx = 0; vtx < gl_in.length(); vtx++)
        {
            vec4 v = gl_in[vtx].gl_Position;
            vec3 n = normalize(normal_ws[vtx]);

            float hVar = texture(HeightMapExtra, height_uv[vtx]).r;
            heightFactor_g = hVar;

            float localShellHeight = shell_height * hVar;
            float offset = float(i) * localShellHeight;
            v.xyz += n * offset;

            world_pos_g = (ModelMatrix * v).xyz;

            // VEREINFACHTE BELEUCHTUNG für bessere Performance
            float NdotL = max(dot(n, light_direction), 0.0);
            float shellShadow = 1.0 - (layers * 0.5);  // Reduziert von 0.6
            lighting = mix(0.3, 1.0, NdotL * shellShadow);  // Kein Backface Darkening

            gl_Position = mvp * v;
            Tcoord1_g = Tcoord1[vtx];
            height_uv_g = height_uv[vtx];
            diffuse_uv_g = diffuse_uv[vtx];
            normal_g = n;

            EmitVertex();
        }
        EndPrimitive();
    }
}
"""

# =========================== Fragment Shader ===========================
fs = """
uniform sampler2D HairPattern;
uniform sampler2D Texture1;
uniform sampler2D HeightMapExtra;

uniform float timer;
uniform float wind_strength;
uniform float color_shift;
uniform float noise_strength;
uniform float brightness;
uniform float alpha_cutoff;

in float layers;
in float lighting;
in vec2 Tcoord1_g;
in vec2 height_uv_g;
in vec2 diffuse_uv_g;
in vec3 world_pos_g;
in vec3 normal_g;
in float heightFactor_g;

out vec4 FragColor;

void main()
{
    // WICHTIG: Zwei verschiedene UV-Sets verwenden!
    // 1. Skalierte UVs für das Haar-Pattern
    vec2 uv_scaled = Tcoord1_g;
    float windOffset = sin(Tcoord1_g.x * 6.28 + timer * 1.0) * layers * 0.0125 * wind_strength;
    uv_scaled.x += windOffset;

    // 2. Original UVs für die HeightMap Maskierung
    vec2 uv_mask = height_uv_g;

    // Hair Pattern - mit skalierten UVs für die Grashalm-Struktur
    float heightMask = texture2D(HairPattern, uv_scaled).r;

    // HeightMap Maske - mit Original UVs (gleiche wie im Geometry Shader!)
    float maskValue = texture2D(HeightMapExtra, uv_mask).r;
    
    // Früher Abbruch wenn die Maske zu dunkel ist
    if (maskValue < 0.01) {
        discard;
    }

    // Diffuse - verwendet jetzt eigene UV-Map!
    vec3 diffuse = texture2D(Texture1, diffuse_uv_g).rgb;

    // VEREINFACHTE COLOR BERECHNUNG
    vec3 FinColor = diffuse * (layers * 0.5 + 0.75) * color_shift;

    // VEREINFACHTER NOISE (nur 1 sin statt 2) - verwendet uv_scaled
    float noise = sin(uv_scaled.x + timer) * 0.15 * noise_strength;
    FinColor *= (1.0 - noise);

    // Beleuchtung
    FinColor *= lighting;

    // Inter-Shell-Schatten
    FinColor *= mix(0.92, 1.0, layers);

    // Helligkeit
    FinColor *= brightness;

    // Alpha Berechnung
    float inv = 1.0 - heightMask;
    float shellAlpha = pow(inv * (2.0 - layers * 2.0), layers + 1.0);
    shellAlpha += inv * (2.0 - layers * 2.0);

    // HeightMap Alpha Modulation
    float heightAlpha = smoothstep(0.0, 0.2, heightFactor_g);
    shellAlpha *= heightAlpha;

    // ALPHA CLIPPING
    if (shellAlpha < alpha_cutoff)
        discard;

    FragColor.rgb = FinColor;
    FragColor.a = 1.0;
}
"""


# ======================================================================
# ============================= ANWENDUNG ===============================
# ======================================================================


mesh = own.meshes[0]

for mat in mesh.materials:
    shader = mat.getShader()
    if shader is None:
        continue

    if not shader.isValid():
        sources = {
            "vertex":   vs,
            "geometry": gs,
            "fragment": fs
        }
        shader.setSourceList(sources, True)

        shader.setSampler('HairPattern', 0)
        shader.setSampler('Texture1', 1)
        shader.setSampler('HeightMapExtra', 2)

        shader.setUniformDef('ModelMatrix', g.MODELMATRIX)
        shader.setUniformDef('ViewMatrix', g.VIEWMATRIX)

    # Licht
    light = scene.objects.get("Sun")
    if light:
        light_dir = light.worldOrientation.col[2]
        shader.setUniform3f("light_direction", light_dir[0], light_dir[1], light_dir[2])
    else:
        shader.setUniform3f("light_direction", 0.0, 0.0, 1.0)

    # Kamera
    shader.setUniformMatrix4('ProjectionMatrix', Camera.projection_matrix, False)
    shader.setUniform1f('timer', own['timer'])

    camPos = Camera.worldPosition
    shader.setUniform3f("camera_pos", camPos[0], camPos[1], camPos[2])
    shader.setUniform1f("lod_start", float(LOD_START))
    shader.setUniform1f("lod_end", float(LOD_END))
    shader.setUniform1i("lod_min_shells", int(LOD_MIN_SHELLS))
    shader.setUniform1i("enable_frustum_culling", int(ENABLE_FRUSTUM_CULLING))

    # Shell Parameter
    shader.setUniform1i("shell_count", int(SHELL_COUNT))
    shader.setUniform1f("shell_height", float(SHELL_HEIGHT))

    # Sonstige
    shader.setUniform1f("uv_scale", float(UV_SCALE))
    shader.setUniform1f("wind_strength", float(WIND_POWER))
    shader.setUniform1f("color_shift", float(COLOR_SHIFT))
    shader.setUniform1f("noise_strength", float(NOISE_POWER))
    shader.setUniform1f("brightness", float(BRIGHTNESS))

    shader.setUniform1f("alpha_cutoff", float(ALPHA_CUTOFF))