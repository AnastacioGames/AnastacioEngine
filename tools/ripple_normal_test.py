"""Teste: ripples de chuva como NORMAL (bolha/onda) em vez de brilho aditivo.

Uso: em qualquer objeto da cena, sensor Always (pulso True) -> controlador
Python (Script) apontando para este texto. Desligue o Ripple do World Weather
para comparar (ou deixe ligado e veja os dois juntos).

Propriedades opcionais no objeto (float) para ajustar ao vivo:
  rip_scale   densidade das celulas (padrao 6.0)
  rip_speed   velocidade (padrao 1.0)
  rip_bump    forca da normal (padrao 1.5)
  rip_refr    distorcao/refracao em tela (padrao 0.012)
  rip_spec    brilho especular (padrao 0.8)
  rip_radius  distancia maxima da camera (padrao 25.0)
"""
import bge

FRAG = """
uniform sampler2D bgl_RenderedTexture;
uniform sampler2D bgl_DepthTexture;
uniform mat4 unfinvviewmat;
uniform mat4 unfinvprojmat;

uniform float t_time, t_scale, t_bump, t_refr, t_spec, t_radius;

vec3 hash3(vec3 p)
{
	return fract(sin(vec3(dot(p, vec3(1.0, 57.0, 113.0)),
	                      dot(p, vec3(57.0, 113.0, 1.0)),
	                      dot(p, vec3(113.0, 1.0, 57.0)))) * 43758.5453);
}

/* Altura da agua: cada celula solta uma gota; a onda e um seno amortecido
 * dentro de um anel que se expande -> perfil de "bolha" com crista e vale. */
float rippleHeight(vec2 p, float time)
{
	vec2 i = floor(p);
	vec2 f = fract(p);
	float h = 0.0;
	for (int y = -1; y <= 1; y++) {
		for (int x = -1; x <= 1; x++) {
			vec2 n = vec2(float(x), float(y));
			vec3 r = hash3(vec3(i + n, 0.0));
			vec2 d = n - f + r.xy;
			float dist = length(d);
			float t = fract(time * 0.8 + r.z);
			float radius = t * 1.1;
			float x0 = dist - radius;
			float env = exp(-x0 * x0 * 180.0);          /* largura do anel */
			float wave = sin(x0 * 55.0) * env;           /* crista + vale */
			float fade = (1.0 - t) * (1.0 - t);
			h += wave * fade;
		}
	}
	return h;
}

vec3 worldFromDepth(vec2 uv, float d)
{
	vec4 v = unfinvprojmat * vec4(uv * 2.0 - 1.0, d * 2.0 - 1.0, 1.0);
	v /= v.w;
	return (unfinvviewmat * v).xyz;
}

void main()
{
	vec2 uv = gl_TexCoord[0].st;
	vec4 base = texture2D(bgl_RenderedTexture, uv);
	float depth = texture2D(bgl_DepthTexture, uv).x;
	if (depth >= 0.9999) { gl_FragColor = base; return; }

	vec3 wp = worldFromDepth(uv, depth);
	vec3 cam = (unfinvviewmat * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
	vec3 gn = normalize(cross(dFdx(wp), dFdy(wp)));
	if (dot(gn, cam - wp) < 0.0) gn = -gn;

	float dcam = length(wp - cam);
	float mask = step(0.7, gn.z) * (1.0 - smoothstep(t_radius * 0.7, t_radius, dcam));
	if (mask <= 0.0) { gl_FragColor = base; return; }

	/* Gradiente da altura por diferencas finitas no plano XY do mundo. */
	vec2 p = wp.xy * t_scale;
	float e = 0.02;
	float h  = rippleHeight(p, t_time);
	float hx = rippleHeight(p + vec2(e, 0.0), t_time);
	float hy = rippleHeight(p + vec2(0.0, e), t_time);
	vec2 grad = vec2(hx - h, hy - h) / e;

	/* Normal perturbada (chao Z-up), igual a um normal map. */
	vec3 N = normalize(vec3(-grad * t_bump * 0.05, 1.0));

	/* Refracao em tela: desloca a amostra da cor pela inclinacao da normal. */
	vec2 offs = N.xy * t_refr * mask;
	vec3 col = texture2D(bgl_RenderedTexture, uv + offs).rgb;

	/* Especular + fresnel usando a normal perturbada. */
	vec3 V = normalize(cam - wp);
	vec3 L = normalize(vec3(0.3, 0.2, 1.0));
	vec3 H = normalize(L + V);
	float spec = pow(max(dot(N, H), 0.0), 120.0);
	float fres = pow(1.0 - max(dot(N, V), 0.0), 5.0);
	float slope = 1.0 - N.z;                         /* so onde ha onda */
	col += (spec * t_spec + fres * 0.25) * mask * clamp(slope * 40.0, 0.0, 1.0);

	gl_FragColor = vec4(col, base.a);
}
"""

cont = bge.logic.getCurrentController()
own = cont.owner
scene = bge.logic.getCurrentScene()
SLOT = 90

if "rip_filter" not in own:
    mgr = scene.filterManager
    if mgr.getFilter(SLOT):
        mgr.removeFilter(SLOT)
    own["rip_filter"] = mgr.addFilter(SLOT, bge.logic.RAS_2DFILTER_CUSTOMFILTER, FRAG)
    own["rip_t"] = 0.0

f = own["rip_filter"]
own["rip_t"] += 1.0 / max(bge.logic.getAverageFrameRate(), 1.0) * own.get("rip_speed", 1.0)
f.setUniform1f("t_time", own["rip_t"])
f.setUniform1f("t_scale", own.get("rip_scale", 6.0))
f.setUniform1f("t_bump", own.get("rip_bump", 1.5))
f.setUniform1f("t_refr", own.get("rip_refr", 0.012))
f.setUniform1f("t_spec", own.get("rip_spec", 0.8))
f.setUniform1f("t_radius", own.get("rip_radius", 25.0))
