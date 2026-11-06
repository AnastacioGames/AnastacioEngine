KX_LightObject(KX_GameObject)
=============================

base class --- :class:`KX_GameObject`

.. class:: KX_LightObject(KX_GameObject)

   A light in the game: the **Lamp** object of the editor (Add > Lamp). The type chosen in the Lamp panel is read in Python with :data:`type`:

   - **Point**: ``NORMAL``, shines in all directions from one point, like a light bulb.
   - **Sun**: ``SUN``, parallel light from far away, for daylight.
   - **Spot**: ``SPOT``, a cone of light, like a flashlight.
   - **Hemi**: ``HEMI``, soft light from a half sphere, without shadows.
   - **Area**: has no type of its own in the game and reads as ``NORMAL``.

   **Fake (GPU Particle)**, in the same Add > Lamp menu, is not a light: it is a mesh with one glowing particle, so it is not a :class:`KX_LightObject`.

   .. code-block:: python

      # Check the type of the lamp, or change it during the game.
      import bge

      light = bge.logic.getCurrentController().owner

      if light.type == light.NORMAL:
          print("Point lamp")
      elif light.type == light.SUN:
          print("Sun lamp")
      elif light.type == light.SPOT:
          print("Spot lamp")
      elif light.type == light.HEMI:
          print("Hemi lamp")

      light.type = light.SPOT  # turn it into a Spot lamp

   .. code-block:: python

      # Turn on a red alert light.
      import bge

      co = bge.logic.getCurrentController()
      light = co.owner

      light.energy = 1.0
      light.color = [1.0, 0.0, 0.0]

   .. code-block:: python

      # Flicker like a torch. Run it every frame (Always sensor with True Pulse).
      import random
      import bge

      light = bge.logic.getCurrentController().owner
      light.energy = random.uniform(0.8, 1.2)

   .. code-block:: python

      # Turn the light on or off. An invisible light does not update its shadow.
      import bge

      light = bge.logic.getCurrentController().owner
      light.visible = not light.visible

   .. code-block:: python

      # Shadow quality option. Bigger sizes look sharper but use more video memory.
      # Point lamps keep the Size set in the editor.
      import bge

      light = bge.logic.getCurrentController().owner
      light.shadowMapSize = 1024  # for example 512, 1024, 2048 or 4096

   .. code-block:: python

      # Stop redrawing the shadow every frame when the scene rarely changes.
      import bge

      light = bge.logic.getCurrentController().owner
      light.staticShadow = True

      # Later, after moving something that casts a shadow, redraw it once.
      light.updateShadow()

   .. code-block:: python

      # Narrow the cone of a spot light and soften its edge.
      import bge

      light = bge.logic.getCurrentController().owner
      if light.type == light.SPOT:
          light.spotsize = 45.0  # cone angle in degrees
          light.spotblend = 0.3  # edge softness, from 0 to 1

   .. data:: SPOT

      A spot light source. See attribute :data:`type`

   .. data:: SUN

      A point light source with no attenuation. See attribute :data:`type`

   .. data:: NORMAL

      A point light source. See attribute :data:`type`

   .. data:: HEMI

      A hemi light source. See attribute :data:`type`
      
   .. attribute:: type

      The type of light - must be SPOT, SUN or NORMAL

   .. attribute:: energy

      The brightness of this light.

      :type: float

   .. attribute:: shadowClipStart

      The shadowmap clip start, below which objects will not generate shadows.

      :type: float (read only)

   .. attribute:: shadowClipEnd

      The shadowmap clip end, beyond which objects will not generate shadows.

      :type: float (read only)

   .. attribute:: shadowFrustumSize

      Size of the frustum used for creating the shadowmap.

      :type: float (read only)

   .. attribute:: shadowBindId

      The OpenGL shadow texture bind number/id.

      :type: int (read only)

   .. attribute:: shadowMapType

      The shadow shadow map type (0 -> Simple; 1 -> Variance)

      :type: int (read only)

   .. attribute:: shadowBias

      The shadow buffer sampling bias.

      :type: float (read only)

   .. attribute:: shadowBleedBias

      The bias for reducing light-bleed on variance shadow maps.

      :type: float (read only)

   .. attribute:: useShadow

      Returns True if the light has Shadow option activated, else returns False.

      :type: boolean (read only)

   .. attribute:: shadowColor

      The color of this light shadows. Black = (0.0, 0.0, 0.0), White = (1.0, 1.0, 1.0).

      :type: :class:`mathutils.Color` (read only)

   .. attribute:: shadowMatrix

      Matrix that converts a vector in camera space to shadow buffer depth space.

      Computed as:
          mat4_perspective_to_depth * mat4_lamp_to_perspective * mat4_world_to_lamp * mat4_cam_to_world.

      mat4_perspective_to_depth is a fixed matrix defined as follow:

         0.5 0.0 0.0 0.5
         0.0 0.5 0.0 0.5
         0.0 0.0 0.5 0.5
         0.0 0.0 0.0 1.0

      .. note:

         There is one matrix of that type per lamp casting shadow in the scene.

      :type: Matrix4x4 (read only)

   .. attribute:: distance

      The maximum distance this light can illuminate. (SPOT and NORMAL lights only).

      :type: float

   .. attribute:: color

      The color of this light. Black = [0.0, 0.0, 0.0], White = [1.0, 1.0, 1.0].

      :type: list [r, g, b]

   .. attribute:: lin_attenuation

      The linear component of this light's attenuation. (SPOT and NORMAL lights only).

      :type: float

   .. attribute:: quad_attenuation

      The quadratic component of this light's attenuation (SPOT and NORMAL lights only).

      :type: float

   .. attribute:: spotsize

      The cone angle of the spot light, in degrees (SPOT lights only).

      :type: float in [0 - 180].

   .. attribute:: spotblend

      Specifies the intensity distribution of the spot light (SPOT lights only).

      :type: float in [0 - 1]

      .. note::

         Higher values result in a more focused light source.

   .. attribute:: shadowMapSize

      Shadow map resolution in pixels (the lamp's Size). Setting it resizes the shadow buffer on
      the fly without recompiling shaders, for a shadow quality option (e.g. 512 / 1024 / 2048).
      Cascaded shadow maps keep their ratio to it. Reads 0 when the lamp has no shadow buffer.
      Point lamps keep their own size.

      :type: integer from 64 to 16384 (clamped to the graphics card maximum).

   .. attribute:: staticShadow

      Enables static shadows. By default (staticShadow=False) the shadow cast by the lamp is recalculated every frame. When this is not needed, set staticShadow=True. In that case, call :py:meth:`updateShadow` to request a shadow update.

      :type: boolean.

   .. method:: updateShadow()

      Set the shadow to be updated next frame if the lamp uses a static shadow, see :data:`staticShadow`.
