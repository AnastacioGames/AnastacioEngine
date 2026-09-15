import bpy
gp = bpy.context.object.gpu_particles

gp.particle_look = 'DEFAULT'
gp.use_vortex = False
gp.gravity = (0.0, 0.0, 0.0)
gp.lifetime = 0.15
gp.emitter_position = (0.0, 0.0, 0.0)
gp.emitter_radius = 0.3
gp.velocity = (0.0, 0.0, 0.0)
gp.velocity_randomness = 3.5
gp.size = 0.08
gp.end_size = 0.02
gp.color = (0.85, 0.95, 1.0, 1.0)
gp.end_color = (0.1, 0.35, 0.9, 0.0)
gp.emission_direction = (0.0, 0.0, 1.0)
gp.emission_angle = 180.0
gp.particle_count = 150
gp.texture = ""
gp.use_size_curve = False
gp.use_color_curve = False
gp.blend_mode = 'ADDITIVE'
