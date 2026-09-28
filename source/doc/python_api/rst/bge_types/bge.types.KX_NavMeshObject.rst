KX_NavMeshObject(KX_GameObject)
===============================

base class --- :class:`KX_GameObject`

.. class:: KX_NavMeshObject(KX_GameObject)

   Python interface for using and controlling navigation meshes.

   A navigation mesh with a Boolean game property ``dynamic_navmesh`` set to True is built in tiles when the
   game starts, so obstacles can carve it at runtime. Objects with "Create Obstacle" carve it automatically;
   :meth:`addObstacle` adds any other object. Paths may differ slightly from the static navigation mesh.

   .. attribute:: dynamic

      True when the navigation mesh was built in tiles and obstacles can carve it (read-only).

      :type: boolean

   .. attribute:: version

      Incremented when the navigation mesh is rebuilt or finishes changing because of obstacles
      (read-only). Paths found with an older version may cross new obstacles.

      :type: integer

   .. method:: findPath(start, goal)

      Finds the path from start to goal points.

      :arg start: the start point
      :arg start: 3D Vector
      :arg goal: the goal point
      :arg start: 3D Vector
      :return: a path as a list of points
      :rtype: list of points

   .. method:: raycast(start, goal)

      Raycast from start to goal points.

      :arg start: the start point
      :arg start: 3D Vector
      :arg goal: the goal point
      :arg start: 3D Vector
      :return: the hit factor
      :rtype: float

   .. method:: draw(mode)

      Draws a debug mesh for the navigation mesh.
      On a dynamic navigation mesh, the obstacle cylinders are drawn in yellow.

      :arg mode: the drawing mode (one of :ref:`these constants <navmesh-draw-mode>`)
      :arg mode: integer
      :return: None

   .. method:: rebuild()

      Rebuild the navigation mesh.

      :return: None

   .. method:: addObstacle(object, radius=0.0)

      Makes the object carve every dynamic navigation mesh of its scene, following it when it moves.
      Calling it again changes the radius. It has no effect on static navigation meshes.

      :arg object: the obstacle, in the same scene as the navigation mesh
      :type object: :class:`KX_GameObject` or string
      :arg radius: the world radius of the obstacle cylinder, 0.0 uses the object "Create Obstacle" radius
         or half its bounding box size
      :type radius: float
      :return: None

   .. method:: removeObstacle(object)

      Stops the object carving the dynamic navigation meshes, including objects with "Create Obstacle".

      :arg object: the obstacle
      :type object: :class:`KX_GameObject` or string
      :return: None
