#if __VERSION__ < 130
  #define in attribute
  #define flat
  #define out varying
#endif

#ifdef USE_CORE_PROFILE
/* No fixed-function matrix stack under core profile -- uploaded explicitly here instead,
 * see RAS_OpenGLDebugDraw::Flush (same convention as gpu_shader_flat_color_vert.glsl). */
uniform mat4 unfviewprojmat;
#else
uniform mat4 unfviewprojmat;
#endif

/* Camera right/up vectors (world space, already scaled by nothing -- per-instance size is
 * applied below) so the quad stays screen-aligned ("always face camera") regardless of the
 * light's own orientation. Cheaper than re-deriving them per vertex from the view matrix. */
uniform vec3 unfcamright;
uniform vec3 unfcamup;

/* Per-vertex: unit quad corner in [-0.5, 0.5]. */
in vec2 pos;

/* Per-instance: world-space light position, billboard half-size, and RGBA tint (alpha already
 * carries the distance fade computed in KX_LightObject::UpdateDistanceCulling). */
in vec3 center;
in float size;
in vec4 color;

out vec2 localPos;
flat out vec4 finalColor;

void main()
{
	vec3 worldPos = center + (pos.x * unfcamright + pos.y * unfcamup) * size;
	gl_Position = unfviewprojmat * vec4(worldPos, 1.0);
	localPos = pos;
	finalColor = color;
}
