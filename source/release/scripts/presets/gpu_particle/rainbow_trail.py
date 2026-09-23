import bpy
gp = bpy.context.object.gpu_particles

gp.particle_look = 'RAINBOW_TRAIL'
gp.use_vortex = False
gp.gravity = (0.0, 0.0, 0.0)
gp.lifetime = 1.2
gp.emitter_position = (0.0, 0.0, 0.0)
gp.emitter_radius = 0.1
gp.velocity = (0.0, 0.0, 2.0)
gp.velocity_randomness = 0.5
gp.size = 0.15
gp.end_size = 0.05
gp.color = (1.0, 1.0, 1.0, 1.0)
gp.end_color = (1.0, 1.0, 1.0, 0.0)
gp.emission_direction = (0.0, 0.0, 1.0)
gp.emission_angle = 15.0
gp.particle_count = 80
gp.texture = ""
gp.use_size_curve = False
gp.use_color_curve = False
gp.blend_mode = 'ADDITIVE'
gp.billboard_mode = 'CAMERA_FACING'
