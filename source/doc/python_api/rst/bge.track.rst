Track Data (bge.track)
======================

Baked track data of the Track Tool (``Range.track``, alias ``bge.track``).

The editor tool bakes one table per sample of a track layout into the Text datablock
``TRACK_<name>.json`` (format version 1, see ``docs/plano-track-tool.md``). In the game the engine
reads that Text from the loaded file (and from files loaded with :func:`bge.logic.LibLoad`) the
first time :func:`get` asks for it, keeps it by name and answers the queries in C++.
The results match the pure Python reference ``range_track.runtime`` (scripts/modules) within 1 mm.

Units are meters and radians. "Left" is the positive lateral side.

.. code-block:: python

   import Range

   track = Range.track.get("Pista_4")
   s, side, dist = track.project(own.worldPosition)
   lap_progress = s / track.length
   target = track.racingLine(s + 15.0)

.. module:: bge.track

.. function:: get(name)

   Track baked in the Text ``TRACK_<name>.json`` of the game file or of a LibLoaded file.
   The Text name itself (``"TRACK_Pista_4.json"``) is accepted too. Read once and cached; the cache
   follows LibLoad/LibFree and is cleared when the game ends.

   :arg name: track name (the name of the track layout object).
   :type name: str
   :return: the track, or None when there is no such Text.
   :rtype: :class:`Track` or None
   :raises ValueError: the Text is not a valid track (the message says what is wrong).

.. function:: names()

   Names of the tracks available in the loaded files (Texts ``TRACK_*.json``).

   :rtype: list of str

.. function:: fromJson(text, name="")

   Track built from a JSON string in the baked format (version 1), for data kept elsewhere.

   :arg text: JSON text.
   :type text: str
   :arg name: name used when the JSON has no ``name``.
   :type name: str
   :rtype: :class:`Track`

.. function:: reload()

   Forget the cached tracks: the next :func:`get` reads the Text again.

.. class:: Track

   Baked track. Get one with :func:`get`; it stays valid after the file that held it is freed.

   Positions may be a :class:`mathutils.Vector` or a sequence of numbers. With only ``(x, y)`` the
   height is ignored; with ``z`` the height picks the right level on bridges and crossings.
   ``s`` wraps around on a closed circuit and is clamped to ``[0, length]`` on an open track.

   .. method:: project(pos)

      Projection of a position on the track.

      :return: ``(s, side, dist)``: meters along the track, ``1`` left / ``-1`` right of the
         center line and lateral distance from it (>= 0).
      :rtype: tuple (float, int, float)

   .. method:: pointAt(s)

      Center line point at ``s``.

      :rtype: :class:`mathutils.Vector`

   .. method:: tangentAt(s)

      Unit 3D direction of travel at ``s``.

      :rtype: :class:`mathutils.Vector`

   .. method:: lateralAt(s)

      Horizontal unit vector to the left at ``s``.

      :rtype: :class:`mathutils.Vector`

   .. method:: bankAt(s)

      Banking at ``s`` in radians (positive: the left edge is lower).

      :rtype: float

   .. method:: widthAt(s)

      Asphalt half widths at ``s``.

      :return: ``(left, right)``
      :rtype: tuple of 2 floats

   .. method:: edgeAt(s)

      Lateral distance of the outer border band (wall, guard rail) at ``s``.

      :return: ``(left, right)``
      :rtype: tuple of 2 floats

   .. method:: racingLine(s)

      Racing line point at ``s``, on the banked surface.

      :rtype: :class:`mathutils.Vector`

   .. method:: isOnRoad(pos)

      True when ``pos`` is over the asphalt (inside the half widths) and up to 3 m from the
      surface (height ignored without ``z``). Past the start or the end of an open track: False.

      :rtype: bool

   .. method:: surfaceAt(s)

      Surface name of the sample that starts the stretch at ``s`` (``""`` when the track has no
      surface names).

      :rtype: str

   .. attribute:: name

      Track name.

      :type: str

   .. attribute:: length

      Track length in meters.

      :type: float

   .. attribute:: cyclic

      True for a closed circuit.

      :type: bool

   .. attribute:: count

      Number of baked samples.

      :type: int

   .. attribute:: surfaces

      Surface names.

      :type: list of str
