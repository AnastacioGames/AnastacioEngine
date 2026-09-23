import Range as bge
import time
from Range import logic as g
import Range.render as render

# Ocean/water surface shader for a mesh plane (BL_Shader custom-material hook -- NOT the
# particle-look system in RAS_ParticleShaderCache.cpp). Attach as an "Always" python
# controller on a subdivided plane object (more subdivisions = smoother wave silhouette,
# the wave shape itself comes from the vertex shader so a flat-shaded low-poly plane will
# look faceted). Follows the same setSourceList/bindCallbacks pattern as ShellShader.py.

own = g.getCurrentController().owner
scene = g.getCurrentScene()
Camera = scene.active_camera

# ======================================================================
# ============================= PARAMETER ===============================
# ======================================================================

WAVE_HEIGHT = 0.35      # amplitude of the tallest wave layer
WAVE_SPEED = 1.0        # global time multiplier
DEEP_COLOR = (0.0, 0.07, 0.13)
SHALLOW_COLOR = (0.05, 0.45, 0.55)
SKY_COLOR = (0.55, 0.75, 0.9)
FOAM_COLOR = (0.9, 0.95, 0.95)
SPEC_POWER = 220.0
SPEC_STRENGTH = 2.5

# ======================================================================
# ============================= TIMER ====================================
# ======================================================================

def getTime():
    own['time'] = time.monotonic()
    own['init'] = True

if 'init' not in own:
    getTime()

own['timer'] = (time.monotonic() - own['time']) * WAVE_SPEED

# ======================================================================
# ==================== GLSL SETTINGS (Range/UPBGE) =====================
# ======================================================================

render.setGLSLMaterialSetting('lights', True)
render.setGLSLMaterialSetting('shaders', True)
render.setGLSLMaterialSetting('shadows', True)

# ======================================================================
# ============================= SHADERS ==================================
# ======================================================================

# ============================ Vertex Shader ============================
vs = """
out vec3 world_pos;
out vec3 world_normal;
out vec3 view_dir;

uniform float u_time;
uniform float u_waveHeight;
uniform mat4 ModelMatrix;
uniform mat4 ViewMatrix;
uniform mat4 ProjectionMatrix;
uniform vec3 camera_pos;

// Sum-of-directional-sines height field (cheap Gerstner-style approximation): each octave
// rotates direction by ~52 degrees and roughly doubles frequency, giving a choppy, non-repeating
// surface. Returns (height, dHeight/dx, dHeight/dy) so the fragment normal comes from analytic
// derivatives instead of a finite-difference sample.
vec3 waveHeight(vec2 p) {
    float h = 0.0;
    vec2 grad = vec2(0.0);
    float amp = u_waveHeight;
    float freq = 0.25;
    vec2 dir = normalize(vec2(0.8, 0.6));
    float speed = 1.0;
    for (int i = 0; i < 5; i++) {
        float phase = dot(p, dir) * freq + u_time * speed;
        h += amp * sin(phase);
        grad += amp * freq * cos(phase) * dir;
        dir = vec2(dir.x * 0.6157 - dir.y * 0.7880, dir.x * 0.7880 + dir.y * 0.6157);
        amp *= 0.55;
        freq *= 1.8;
        speed *= 1.15;
    }
    return vec3(h, grad);
}

void main() {
    vec4 wp = ModelMatrix * gl_Vertex;
    vec3 h = waveHeight(wp.xy);
    wp.z += h.x;

    world_pos = wp.xyz;
    world_normal = normalize(vec3(-h.y, -h.z, 1.0));
    view_dir = camera_pos - world_pos;

    gl_Position = ProjectionMatrix * ViewMatrix * wp;
}
"""

# =========================== Fragment Shader ============================
fs = """
uniform vec3 light_direction;
uniform vec3 deep_color;
uniform vec3 shallow_color;
uniform vec3 sky_color;
uniform vec3 foam_color;
uniform float spec_power;
uniform float spec_strength;

in vec3 world_pos;
in vec3 world_normal;
in vec3 view_dir;

out vec4 FragColor;

void main() {
    vec3 N = normalize(world_normal);
    vec3 V = normalize(view_dir);
    vec3 L = normalize(light_direction);

    // Fresnel: steep viewing angle -> more sky reflection, straight down -> see into the water.
    float fresnel = clamp(pow(1.0 - max(dot(N, V), 0.0), 5.0), 0.02, 1.0);

    vec3 waterColor = mix(deep_color, shallow_color, clamp(dot(N, vec3(0.0, 0.0, 1.0)), 0.0, 1.0));
    vec3 rgb = mix(waterColor, sky_color, fresnel);

    // Blinn-Phong sun glint.
    vec3 H = normalize(L + V);
    float spec = pow(max(dot(N, H), 0.0), spec_power);
    rgb += vec3(1.0, 0.95, 0.8) * spec * spec_strength;

    // Foam on the steepest wave faces (crests/troughs), where the normal tilts away from up.
    float crest = smoothstep(0.75, 1.0, 1.0 - N.z);
    rgb = mix(rgb, foam_color, crest * 0.4);

    FragColor = vec4(rgb, 1.0);
}
"""

# ======================================================================
# ============================= APPLICATION ==============================
# ======================================================================

mesh = own.meshes[0]

for mat in mesh.materials:
    shader = mat.getShader()
    if shader is None:
        continue

    if not shader.isValid():
        shader.setSourceList({"vertex": vs, "fragment": fs}, True)
        shader.setUniformDef('ModelMatrix', g.MODELMATRIX)

    light = scene.objects.get("Sun")
    if light:
        light_dir = light.worldOrientation.col[2]
        shader.setUniform3f("light_direction", light_dir[0], light_dir[1], light_dir[2])
    else:
        shader.setUniform3f("light_direction", 0.3, 0.3, 1.0)

    shader.setUniformMatrix4('ViewMatrix', Camera.modelview_matrix, False)
    shader.setUniformMatrix4('ProjectionMatrix', Camera.projection_matrix, False)

    camPos = Camera.worldPosition
    shader.setUniform3f("camera_pos", camPos[0], camPos[1], camPos[2])

    shader.setUniform1f("u_time", own['timer'])
    shader.setUniform1f("u_waveHeight", float(WAVE_HEIGHT))

    shader.setUniform3f("deep_color", *DEEP_COLOR)
    shader.setUniform3f("shallow_color", *SHALLOW_COLOR)
    shader.setUniform3f("sky_color", *SKY_COLOR)
    shader.setUniform3f("foam_color", *FOAM_COLOR)
    shader.setUniform1f("spec_power", float(SPEC_POWER))
    shader.setUniform1f("spec_strength", float(SPEC_STRENGTH))
