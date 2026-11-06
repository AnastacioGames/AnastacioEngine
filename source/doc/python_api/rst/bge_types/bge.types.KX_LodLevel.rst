KX_LodLevel(EXP_PyObjectPlus)
=============================

base class --- :class:`EXP_PyObjectPlus`

.. class:: KX_LodLevel(EXP_PyObjectPlus)

   A single lod level for a game object lod manager.

   .. code-block:: python

      # List the levels of detail of the object.
      import bge

      obj = bge.logic.getCurrentController().owner

      if obj.lodManager is not None:
          for lod in obj.lodManager.levels:
              print(lod.level, lod.distance, lod.useMesh, lod.useMaterial)

   .. code-block:: python

      # See which level the object is using right now.
      import bge

      obj = bge.logic.getCurrentController().owner

      if obj.lodManager is not None:
          lod = obj.lodManager.levels[obj.currentLodLevel]
          print(lod.level, lod.mesh)

   .. attribute:: mesh

      The mesh used for this lod level. (read only)

      :type: :class:`RAS_MeshObject`

   .. attribute:: level

      The number of the lod level. (read only)

      :type: integer

   .. attribute:: distance

      Distance to begin using this level of detail. (read only)

      :type: float (0.0 to infinite)

   .. attribute:: hysteresis

      Minimum distance factor change required to transition to the previous level of detail in percent. (read only)

      :type: float [0.0 to 100.0]

   .. attribute:: useMesh

      Return True if the lod level uses a different mesh than the original object mesh. (read only)

      :type: boolean

   .. attribute:: useMaterial

      Return True if the lod level uses a different material than the original object mesh material. (read only)

      :type: boolean

   .. attribute:: useHysteresis

      Return true if the lod level uses hysteresis override. (read only)

      :type: boolean
