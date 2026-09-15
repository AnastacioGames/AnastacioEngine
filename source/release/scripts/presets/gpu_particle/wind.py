import bpy
gp = bpy.context.object.gpu_particles

gp.particle_look = 'WIND'
gp.use_vortex = False
gp.gravity = (0.0, 0.0, 0.0)
gp.lifetime = 1.0
gp.emitter_position = (0.0, 0.0, 0.0)
gp.emitter_radius = 0.2
gp.velocity = (2.0, 0.0, 0.0)
gp.velocity_randomness = 0.3
gp.size = 1.0
gp.end_size = 1.0
gp.color = (1.0, 1.0, 1.0, 0.3)
gp.end_color = (1.0, 1.0, 1.0, 0.0)
gp.emission_direction = (1.0, 0.0, 0.0)
gp.emission_angle = 10.0
gp.particle_count = 40
gp.texture = ""
gp.use_size_curve = False
gp.use_color_curve = False
gp.blend_mode = 'ALPHA'
gp.billboard_mode = 'CAMERA_FACING'
