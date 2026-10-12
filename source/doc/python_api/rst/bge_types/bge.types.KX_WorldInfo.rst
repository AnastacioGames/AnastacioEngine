KX_WorldInfo(EXP_PyObjectPlus)
==============================

base class --- :class:`EXP_PyObjectPlus`

.. class:: KX_WorldInfo(EXP_PyObjectPlus)

   A world object.

   .. code-block:: python

      # Set the mist color to red.
      import bge

      sce = bge.logic.getCurrentScene()

      sce.world.mistColor = [1.0, 0.0, 0.0]

   .. data:: KX_MIST_QUADRATIC

      Type of quadratic attenuation used to fade mist.

   .. data:: KX_MIST_LINEAR

      Type of linear attenuation used to fade mist.

   .. data:: KX_MIST_INV_QUADRATIC

      Type of inverse quadratic attenuation used to fade mist.

   .. attribute:: mistEnable

      Return the state of the mist.

      :type: bool

   .. attribute:: mistStart

      The mist start point.

      :type: float

   .. attribute:: mistDistance

      The mist distance fom the start point to reach 100% mist.

      :type: float

   .. attribute:: mistIntensity

      The mist intensity.

      :type: float

   .. attribute:: mistType

      The type of mist - must be KX_MIST_QUADRATIC, KX_MIST_LINEAR or KX_MIST_INV_QUADRATIC

   .. attribute:: mistColor

      The color of the mist. Black = [0.0, 0.0, 0.0], White = [1.0, 1.0, 1.0].
      Mist and background color sould always set to the same color.

      :type: :class:`mathutils.Color`

   .. attribute:: horizonColor

      The horizon color. Black = [0.0, 0.0, 0.0, 1.0], White = [1.0, 1.0, 1.0, 1.0].
      Mist and horizon color should always be set to the same color.

      :type: :class:`mathutils.Vector`

   .. attribute:: zenithColor

      The zenith color. Black = [0.0, 0.0, 0.0, 1.0], White = [1.0, 1.0, 1.0, 1.0].

      :type: :class:`mathutils.Vector`

   .. attribute:: ambientColor

      The color of the ambient light. Black = [0.0, 0.0, 0.0], White = [1.0, 1.0, 1.0].

      :type: :class:`mathutils.Color`

   .. attribute:: exposure

      Amount of exponential color correction for light.

      :type: float between 0.0 and 1.0 inclusive

   .. attribute:: range

      The color range that will be mapped to 0 - 1.

      :type: float between 0.2 and 5.0 inclusive

   .. attribute:: envLightEnergy

      The environment light energy.

      :type: float from 0.0 to infinite

   .. attribute:: envLightEnabled

      Returns True if Environment Lighting is enabled. Else returns False

      :type: bool (read only)

   .. attribute:: envLightColor

      White:       returns 0
      SkyColor:    returns 1
      SkyTexture:  returns 2

      :type: int (read only)

   .. method:: setWeather(name, value)

      Changes a World weather setting at runtime (the "weather." prefix is optional).
      Booleans: ``rain``, ``ripples``, ``splash``, ``puddles``, ``puddle_ssr``, ``ripple_puddle_only``, ``splash_puddle_only`` (both also turn ``puddles`` on), ``aura``, ``lightning``, ``lightning_side``, ``clouds``, ``lens_flare``, ``mist``.
      Floats: ``rain_intensity``, ``rain_density``, ``rain_speed``, ``rain_wind``, ``rain_darken``,
      ``rain_streak_width``, ``ripple_intensity``, ``ripple_normal``, ``ripple_size``, ``ripple_rate``, ``splash_normal``, ``splash_min_up``, ``splash_size``, ``splash_rate``, ``splash_intensity``,
      ``splash_distance``, ``puddle_amount``, ``puddle_size``, ``puddle_darkness``, ``puddle_reflection``,
      ``puddle_distance``, ``puddle_min_up``, ``aura_size``, ``aura_rate``, ``aura_intensity``, ``aura_distance``,
      ``lightning_rate``, ``lightning_intensity``, ``lightning_distance``, ``lightning_width``,
      ``cloud_coverage``, ``cloud_scale``, ``cloud_speed``, ``flare_scale``, ``flare_intensity``, ``mist_*``.

      Clouds, Sky Layers and Volumetric Clouds (the toggles need the clouds pass, built at load when any of
      the three is enabled in the World): booleans ``use_sky_layers``, ``use_volumetric_clouds``,
      ``vcloud_shadow_enable``; integers ``cloud_detail`` (1-8), ``vcloud_quality`` (0 Low, 1 Medium, 2 High);
      floats ``cloud_color_r/_g/_b``, ``vcloud_coverage``, ``vcloud_scale``, ``vcloud_speed``,
      ``vcloud_altitude``, ``vcloud_thickness``, ``vcloud_density``, ``vcloud_detail_scale``,
      ``vcloud_silver_intensity``, ``vcloud_shadow_strength``, ``vcloud_color_r/_g/_b``.

      Fog - Volumetric: booleans ``vfog``, ``vfog_use_lamps``, ``vfog_use_shafts``, ``vfog_use_sun_shafts``,
      ``vfog_volumes_only``, ``vfog_use_wind``, ``vfog_use_time_of_day``, ``vfog_use_layer``,
      ``vfog_use_reach_clouds``; integers ``vfog_quality`` (0 Low, 1 Medium, 2 High), ``vfog_max_lights`` (1-8);
      floats ``vfog_density``, ``vfog_base``, ``vfog_falloff``, ``vfog_distance``, ``vfog_noise_scale``,
      ``vfog_noise_amount``, ``vfog_speed``, ``vfog_anisotropy``, ``vfog_edge``, ``vfog_light_intensity``,
      ``vfog_sun_intensity``, ``vfog_shaft_intensity``, ``vfog_ambient``, ``vfog_morning_boost``,
      ``vfog_wind_direction`` (degrees), ``vfog_color_r/_g/_b``. The fog resolution is fixed at load.

      .. code-block:: python

         scene.world.setWeather("aura", True)
         scene.world.setWeather("splash_size", 1.5)

      :arg name: setting name
      :type name: string
      :arg value: new value
      :type value: bool or float
      :raises ValueError: unknown setting name

   .. method:: strikeLightning(bolt=True)

      Strikes a lightning now (World > Rain must be on; automatic lightning can stay off).

      :arg bolt: show a bolt; False gives only a far flash behind the clouds
      :type bolt: bool
