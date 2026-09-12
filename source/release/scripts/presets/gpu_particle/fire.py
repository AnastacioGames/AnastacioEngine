import bpy
gp = bpy.context.object.gpu_particles

gp.gravity = (0.0, 0.0, 0.6)
gp.lifetime = 0.7
gp.emitter_position = (0.0, 0.0, 0.0)
gp.emitter_radius = 0.15
gp.velocity = (0.0, 0.0, 1.2)
gp.velocity_randomness = 0.4
gp.size = 0.25
gp.end_size = 0.05
gp.color = (1.0, 0.85, 0.3, 1.0)
gp.end_color = (0.55, 0.05, 0.0, 0.0)
gp.emission_direction = (0.0, 0.0, 1.0)
gp.emission_angle = 25.0
gp.particle_count = 200
gp.texture = ""
gp.use_size_curve = False
gp.use_color_curve = False
gp.blend_mode = 'ADDITIVE'
