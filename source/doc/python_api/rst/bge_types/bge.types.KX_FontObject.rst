KX_FontObject(KX_GameObject)
============================

base class --- :class:`KX_GameObject`

.. class:: KX_FontObject(KX_GameObject)

   A Font object.

   .. code-block:: python

      # Display a message about the exit key using a Font object.
      import bge

      co = bge.logic.getCurrentController()
      font = co.owner

      exit_key = bge.events.EventToString(bge.logic.getExitKey())

      if exit_key.endswith("KEY"):
          exit_key = exit_key[:-3]

      font.text = "Press key '%s' to quit the game." % exit_key

   .. code-block:: python

      # Show the score stored in a game property.
      import bge

      font = bge.logic.getCurrentController().owner
      font.text = "Score: %d" % font["score"]

   .. code-block:: python

      # Center the text on the X axis, using its current width.
      import bge

      font = bge.logic.getCurrentController().owner
      font.text = "Game Over"
      font.localPosition.x = -font.dimensions.x / 2

   .. code-block:: python

      # Reveal the text one letter at a time. Run it every frame (Always sensor with True Pulse).
      import bge

      font = bge.logic.getCurrentController().owner

      if font.visibleCharacters < font.characterCount:
          font.visibleCharacters += 1

   .. code-block:: python

      # Add a dark shadow behind the text.
      import bge

      font = bge.logic.getCurrentController().owner
      font.useShadows = True
      font.shadowColor = [0.0, 0.0, 0.0, 0.8]
      font.shadowOffset = [0.02, -0.02]

   .. attribute:: text

      The text displayed by this Font object.

      :type: string
   .. attribute:: resolution

      The resolution of the font police.

      .. warning::

         High resolution can use a lot of memory and may crash.

      :type: float (0.1 to 50.0)

   .. attribute:: size

      The size (scale factor) of the font object, scaled from font object origin (affects text resolution).

      .. warning::

         High size can use a lot of memory and may crash.

      :type: float (0.0001 to 40.0)

   .. attribute:: dimensions

      The size (width and height) of the current text in Blender Units.

      :type: :class:`mathutils.Vector`

