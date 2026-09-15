import bpy
gp = bpy.context.object.gpu_particles

gp.particle_look = 'SMOKE'
gp.use_vortex = False
gp.gravity = (0.0, 0.0, 0.3)
gp.lifetime = 3.0
gp.emitter_position = (0.0, 0.0, 0.0)
gp.emitter_radius = 0.3
gp.velocity = (0.0, 0.0, 0.6)
gp.velocity_randomness = 0.4
gp.size = 0.5
gp.end_size = 1.5
gp.color = (0.6, 0.6, 0.6, 0.5)
gp.end_color = (0.3, 0.3, 0.3, 0.0)
gp.emission_direction = (0.0, 0.0, 1.0)
gp.emission_angle = 25.0
gp.particle_count = 60
gp.texture = ""
gp.use_size_curve = False
gp.use_color_curve = False
gp.blend_mode = 'ALPHA'
gp.billboard_mode = 'VERTICAL'
