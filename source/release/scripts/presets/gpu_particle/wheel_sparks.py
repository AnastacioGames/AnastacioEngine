import bpy
gp = bpy.context.object.gpu_particles

gp.particle_look = 'DEFAULT'
gp.use_vortex = False
gp.gravity = (0.0, 0.0, -2.5)
gp.lifetime = 0.35
gp.emitter_position = (0.0, 0.0, 0.0)
gp.emitter_radius = 0.05
gp.velocity = (0.0, 0.0, 0.8)
gp.velocity_randomness = 1.8
gp.size = 0.05
gp.end_size = 0.01
gp.color = (1.0, 0.95, 0.75, 1.0)
gp.end_color = (1.0, 0.35, 0.05, 0.0)
gp.emission_direction = (0.0, 0.0, 1.0)
gp.emission_angle = 60.0
gp.particle_count = 40
gp.texture = ""
gp.use_size_curve = False
gp.use_color_curve = False
gp.blend_mode = 'ADDITIVE'
