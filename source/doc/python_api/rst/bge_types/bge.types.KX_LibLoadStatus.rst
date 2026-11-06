KX_LibLoadStatus(EXP_PyObjectPlus)
==================================

base class --- :class:`EXP_PyObjectPlus`

.. class:: KX_LibLoadStatus(EXP_PyObjectPlus)

   An object providing information about a LibLoad() operation.

   .. code-block:: python

      # Print a message when an async LibLoad is done
      import bge

      def finished_cb(status):
          print("Library (%s) loaded in %.2fms." % (status.libraryName, status.timeTaken))

      bge.logic.LibLoad('myblend.blend', 'Scene', asynchronous=True).onFinish = finished_cb

   .. code-block:: python

      # Loading screen: show the progress. Run update every frame (Always sensor with True Pulse).
      import bge

      status = bge.logic.LibLoad("//level2.range", "Scene", asynchronous=True)

      def update(cont):
          cont.owner.text = "Loading %d%%" % (status.progress * 100)

          if status.finished:
              cont.owner.text = "Ready"

   .. code-block:: python

      # Add an object as soon as its file finishes loading.
      import bge

      def finished(status):
          print(status.libraryName, status.timeTaken)
          bge.logic.getCurrentScene().addObject("Enemy")

      status = bge.logic.LibLoad("//enemies.range", "Scene", asynchronous=True)
      status.onFinish = finished

   .. attribute:: onFinish

      A callback that gets called when the lib load is done.

      :type: callable

   .. attribute:: finished

      The current status of the lib load.

      :type: boolean

   .. attribute:: progress

      The current progress of the lib load as a normalized value from 0.0 to 1.0.

      :type: float

   .. attribute:: libraryName

      The name of the library being loaded (the first argument to LibLoad).

      :type: string

   .. attribute:: timeTaken

      The amount of time, in seconds, the lib load took (0 until the operation is complete).

      :type: float
