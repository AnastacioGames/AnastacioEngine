import bpy
gp = bpy.context.object.gpu_particles

gp.particle_look = 'AURORA'
gp.use_vortex = False
gp.gravity = (0.0, 0.0, 0.0)
gp.lifetime = 4.0
gp.emitter_position = (0.0, 0.0, 0.0)
gp.emitter_radius = 0.5
gp.velocity = (0.0, 0.0, 0.05)
gp.velocity_randomness = 0.1
gp.size = 1.5
gp.end_size = 1.5
gp.color = (0.2, 1.0, 0.5, 0.5)
gp.end_color = (0.6, 0.2, 1.0, 0.0)
gp.emission_direction = (0.0, 0.0, 1.0)
gp.emission_angle = 20.0
gp.particle_count = 30
gp.texture = ""
gp.use_size_curve = False
gp.use_color_curve = False
gp.blend_mode = 'ADDITIVE'
gp.billboard_mode = 'VERTICAL'
