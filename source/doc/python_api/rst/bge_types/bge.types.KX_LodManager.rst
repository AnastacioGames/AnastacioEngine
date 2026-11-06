KX_LodManager(EXP_PyObjectPlus)
===============================

base class --- :class:`EXP_PyObjectPlus`

.. class:: KX_LodManager(EXP_PyObjectPlus)

   This class contains a list of all levels of detail used by a game object.

   .. code-block:: python

      # Graphics option: values above 1.0 switch to the simpler levels sooner.
      import bge

      obj = bge.logic.getCurrentController().owner

      if obj.lodManager is not None:
          obj.lodManager.distanceFactor = 2.0

   .. code-block:: python

      # Use the same levels of detail in another object.
      import bge

      scene = bge.logic.getCurrentScene()
      scene.objects["TreeB"].lodManager = scene.objects["TreeA"].lodManager

   .. code-block:: python

      # Also switch the physics mesh when the level changes.
      import bge

      obj = bge.logic.getCurrentController().owner

      if obj.lodManager is not None:
          obj.lodManager.updatePhysics = True

   .. attribute:: levels

      Return the list of all levels of detail of the lod manager.

      :type: list of :class:`KX_LodLevel`

   .. attribute:: distanceFactor

      Method to multiply the distance to the camera.

      :type: float
