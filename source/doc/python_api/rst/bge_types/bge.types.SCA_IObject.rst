SCA_IObject(EXP_Value)
======================

base class --- :class:`EXP_Value`

.. class:: SCA_IObject(EXP_Value)

   This class has no python functions

   .. code-block:: python

      # Every game object is also a SCA_IObject.
      import bge

      obj = bge.logic.getCurrentController().owner
      print(isinstance(obj, bge.types.SCA_IObject))
