import bpy
gp = bpy.context.object.gpu_particles

gp.gravity = (0.0, 0.0, -0.3)
gp.lifetime = 1.8
gp.emitter_position = (0.0, 0.0, 0.0)
gp.emitter_radius = 0.4
gp.velocity = (0.0, 0.0, 0.3)
gp.velocity_randomness = 0.5
gp.size = 0.3
gp.end_size = 0.6
gp.color = (0.5, 0.5, 0.52, 0.6)
gp.end_color = (0.5, 0.5, 0.52, 0.0)
gp.emission_direction = (0.0, 0.0, 1.0)
gp.emission_angle = 90.0
gp.particle_count = 120
gp.texture = ""
gp.use_size_curve = False
gp.use_color_curve = False
gp.blend_mode = 'ALPHA'
