import bpy
gp = bpy.context.object.gpu_particles

gp.particle_look = 'TORNADO'
gp.gravity = (0.0, 0.0, 0.1)
gp.lifetime = 2.5
gp.emitter_position = (0.0, 0.0, 0.0)
gp.emitter_radius = 0.2
gp.velocity = (0.0, 0.0, 1.5)
gp.velocity_randomness = 0.15
gp.size = 0.6
gp.end_size = 0.2
gp.color = (0.6, 0.5, 0.4, 0.6)
gp.end_color = (0.5, 0.45, 0.4, 0.0)
gp.emission_direction = (0.0, 0.0, 1.0)
gp.emission_angle = 180.0
gp.particle_count = 100
gp.texture = ""
gp.use_size_curve = False
gp.use_color_curve = False
gp.blend_mode = 'ALPHA'
gp.billboard_mode = 'VERTICAL'
# Cone/vortex motion: narrow funnel at the base widening into the supercell as particles rise,
# spinning around the vertical axis -- this is what gives the tornado its cone silhouette.
gp.use_vortex = True
gp.vortex_rotation_speed = 260.0
gp.vortex_radius_top = 1.8
gp.vortex_height = 2.5
