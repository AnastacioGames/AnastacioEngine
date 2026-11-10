SCA_MouseSensor(SCA_ISensor)
============================

base class --- :class:`SCA_ISensor`

.. class:: SCA_MouseSensor(SCA_ISensor)

   Mouse Sensor logic brick.

   .. attribute:: position

      current [x, y] coordinates of the mouse, in frame coordinates (pixels).

      :type: [integer, interger]

   .. attribute:: mode

      sensor mode.

      Unlike UPBGE, Range has the thumb buttons and buttons 6 and 7 before the wheel, so wheel up, wheel down and movement are 8, 9 and 10 (4, 5 and 6 in UPBGE). Compare with the bge.logic.KX_MOUSESENSORMODE_* constants instead of numbers. Mouse sensors in .blend files from UPBGE and the original BGE are converted when the file is opened.

      :type: integer

         * KX_MOUSESENSORMODE_LEFTBUTTON(1)
         * KX_MOUSESENSORMODE_MIDDLEBUTTON(2)
         * KX_MOUSESENSORMODE_RIGHTBUTTON(3)
         * KX_MOUSESENSORMODE_LEFTTHUMBMOUSE(4)
         * KX_MOUSESENSORMODE_RIGHTTHUMBMOUSE(5)
         * KX_MOUSESENSORMODE_BUTTON6(6)
         * KX_MOUSESENSORMODE_BUTTON7(7)
         * KX_MOUSESENSORMODE_WHEELUP(8)
         * KX_MOUSESENSORMODE_WHEELDOWN(9)
         * KX_MOUSESENSORMODE_MOVEMENT(10)

   .. method:: getButtonStatus(button)

      Get the mouse button status.

      :arg button: The code that represents the key you want to get the state of, use one of :ref:`these constants<mouse-keys>`
      :type button: int
      :return: The state of the given key, can be one of :ref:`these constants<input-status>`
      :rtype: int
