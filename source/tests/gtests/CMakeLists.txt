
# GTest
if(WITH_GTESTS)

	include(GTestTesting)

	add_definitions(${GFLAGS_DEFINES})
	add_definitions(${GLOG_DEFINES})
	add_definitions(-DBLENDER_GFLAGS_NAMESPACE=${GFLAGS_NAMESPACE})

	# Otherwise we get warnings here that we cant fix in external projects
	remove_strict_flags()

	add_subdirectory(testing)
	add_subdirectory(blenlib)
	add_subdirectory(guardedalloc)
	# AnastacioEngine: bmesh_core_test links bf_blenloader, which pulls in imbuf/OCIO,
	# blenkernel, python and the window manager; it does not link standalone.
	# add_subdirectory(bmesh)
	if(WITH_ALEMBIC)
		add_subdirectory(alembic)
	endif()
endif()
