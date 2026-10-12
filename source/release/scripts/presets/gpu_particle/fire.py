import bpy
gp = bpy.context.object.gpu_particles

gp.particle_look = 'FIRE'
gp.use_vortex = False
gp.gravity = (0.0, 0.0, 1.2)
gp.lifetime = 1.1
gp.emitter_position = (0.0, 0.0, 0.0)
gp.emitter_radius = 0.35
gp.velocity = (0.0, 0.0, 1.4)
gp.velocity_randomness = 0.5
gp.size = 0.9
gp.end_size = 0.35
gp.color = (1.0, 1.0, 1.0, 0.5)
gp.end_color = (1.0, 1.0, 1.0, 0.0)
gp.emission_direction = (0.0, 0.0, 1.0)
gp.emission_angle = 20.0
gp.particle_count = 110
gp.texture = ""
gp.use_size_curve = False
gp.use_color_curve = False
gp.blend_mode = 'ADDITIVE'
gp.billboard_mode = 'VERTICAL'
