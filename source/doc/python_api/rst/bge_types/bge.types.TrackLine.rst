TrackLine
=========

.. class:: TrackLine(points)

   Closed polyline for racing AI, computed in C++. Tells how far along the track a car is,
   gives the point and the side of the track at a distance, and stores per-point profiles
   (curvature, safe speed). Build it once per track and share it between the cars.

   The line is closed: the last point connects to the first. ``s`` is the distance in meters
   from the first point and wraps around, so ``s`` greater than :data:`length` or negative works.

   .. code-block:: python

      import Range
      from mathutils import Vector

      points = curve.getCurvePoints()        # or the center of the road mesh
      line = Range.types.TrackLine(points)

      d2, s, seg = line.locate(car.worldPosition)               # global search
      d2, s, seg = line.locate(car.worldPosition, seg, 15, 40, 20.0)  # near the last segment
      target = line.point(s + 12.0)          # 12 m ahead
      right = line.side(s)                   # unit vector to the right, or None

   :arg points: at least 3 points (:class:`mathutils.Vector` or 3-item sequences).
   :type points: sequence

   .. attribute:: length

      Total length of the closed line, in meters (read-only).

      :type: float

   .. method:: locate(pos, seg=-1, back=0, ahead=0, lost=0.0)

      Closest segment of the line to ``pos``.

      With ``seg`` >= 0 only the segments from ``seg - back`` to ``seg + ahead`` are tested,
      which avoids jumping to a neighbouring part of the track. When that result is farther
      than ``lost`` meters (respawn, shortcut), or with ``seg`` = -1, the whole line is searched.

      :arg pos: position in world coordinates.
      :type pos: :class:`mathutils.Vector`
      :arg seg: segment from the previous call, -1 if unknown.
      :type seg: integer
      :arg back: segments to test behind ``seg``.
      :type back: integer
      :arg ahead: segments to test ahead of ``seg``.
      :type ahead: integer
      :arg lost: distance in meters that triggers the global search.
      :type lost: float
      :return: (squared distance to the line, ``s`` in meters, segment index).
      :rtype: tuple (float, float, integer)

   .. method:: point(s)

      Point of the line ``s`` meters from the start.

      :rtype: :class:`mathutils.Vector`

   .. method:: side(s)

      Horizontal unit vector pointing to the right of the line at ``s``, or None where the
      line is vertical or degenerate.

      :rtype: :class:`mathutils.Vector` or None

   .. method:: setProfile(name, values)

      Stores one value per point under ``name`` (curvature, safe speed, any number).

      :arg name: profile name.
      :type name: string
      :arg values: one number per point of the line.
      :type values: sequence of float

   .. method:: profile(name, s)

      Value of the profile ``name`` interpolated at ``s`` meters.

      :rtype: float
