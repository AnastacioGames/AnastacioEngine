KX_PythonMotion(EXP_PyObjectPlus)
=================================

base class --- :class:`EXP_PyObjectPlus`

.. class:: KX_PythonMotion(EXP_PyObjectPlus)

   Motion sensors of the device (phone or tablet), available as :data:`bge.logic.motion`.

   Values come from the browser in the Web runtime (``DeviceMotionEvent`` and ``DeviceOrientationEvent``),
   including the Android app, which runs the Web runtime inside a WebView. On other platforms there is no
   sensor source yet: :data:`available` is ``False``, vectors are zero and :data:`tilt` is ``(0.0, 0.0)``, so the
   same script runs everywhere.

   Vectors use the axes of the screen as it is currently shown, in portrait or landscape: x to the right, y to
   the top of the screen and z out of the screen, toward the player.

   A tilt-controlled object:

   .. code-block:: python

      from bge import logic, events

      def main(cont):
          own = cont.owner
          if logic.mouse.inputs[events.LEFTMOUSE].activated:  # a tap on the screen
              logic.motion.calibrate()
          x, y = logic.motion.tilt
          own.applyForce((x * 20.0, y * 20.0, 0.0))

   .. attribute:: available

      ``True`` while the sensors are sending data. It becomes ``False`` when no reading arrived in the last
      second (no sensor, desktop browser, page in background). (read-only).

      :type: boolean

   .. attribute:: gyroscope

      Rotation speed around each screen axis, in radians per second. (read-only).

      :type: :class:`mathutils.Vector`

   .. attribute:: accelerometer

      Acceleration including gravity, in m/s². With the device lying still, face up, it is close to
      ``(0, 0, 9.8)``. (read-only).

      :type: :class:`mathutils.Vector`

   .. attribute:: gravity

      Gravity alone, in m/s², pointing up as in :data:`accelerometer`. When the device does not report
      acceleration without gravity, it is estimated from :data:`accelerometer` with a low-pass filter. (read-only).

      :type: :class:`mathutils.Vector`

   .. attribute:: orientation

      Device orientation angles ``(alpha, beta, gamma)`` in degrees, exactly as given by the browser. They follow
      the device axes, not the screen axes. (read-only).

      :type: :class:`mathutils.Vector`

   .. attribute:: tilt

      How far the device is tilted from its neutral position, from -1.0 to 1.0 on each axis: the screen direction
      a ball would roll to. ``x`` is positive when the right edge of the screen goes down, ``y`` when the top edge
      goes down. The neutral position is the device lying flat until :meth:`calibrate` is called. (read-only).

      :type: tuple (float, float)

   .. method:: calibrate()

      Take the current position as neutral for :data:`tilt`, so the player can hold the device the way they like.

      :return: ``True`` if there was a sensor reading to calibrate with, ``False`` otherwise.
      :rtype: boolean
