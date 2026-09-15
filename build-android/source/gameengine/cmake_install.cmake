# Install script for directory: D:/AnastacioEngine/source/source/gameengine

# Set the install prefix
if(NOT DEFINED CMAKE_INSTALL_PREFIX)
  set(CMAKE_INSTALL_PREFIX "D:/AnastacioEngine/build-android/bin")
endif()
string(REGEX REPLACE "/$" "" CMAKE_INSTALL_PREFIX "${CMAKE_INSTALL_PREFIX}")

# Set the install configuration name.
if(NOT DEFINED CMAKE_INSTALL_CONFIG_NAME)
  if(BUILD_TYPE)
    string(REGEX REPLACE "^[^A-Za-z0-9_]+" ""
           CMAKE_INSTALL_CONFIG_NAME "${BUILD_TYPE}")
  else()
    set(CMAKE_INSTALL_CONFIG_NAME "Release")
  endif()
  message(STATUS "Install configuration: \"${CMAKE_INSTALL_CONFIG_NAME}\"")
endif()

# Set the component getting installed.
if(NOT CMAKE_INSTALL_COMPONENT)
  if(COMPONENT)
    message(STATUS "Install component: \"${COMPONENT}\"")
    set(CMAKE_INSTALL_COMPONENT "${COMPONENT}")
  else()
    set(CMAKE_INSTALL_COMPONENT)
  endif()
endif()

# Install shared libraries without execute permission?
if(NOT DEFINED CMAKE_INSTALL_SO_NO_EXE)
  set(CMAKE_INSTALL_SO_NO_EXE "0")
endif()

# Is this installation the result of a crosscompile?
if(NOT DEFINED CMAKE_CROSSCOMPILING)
  set(CMAKE_CROSSCOMPILING "TRUE")
endif()

# Set path to fallback-tool for dependency-resolution.
if(NOT DEFINED CMAKE_OBJDUMP)
  set(CMAKE_OBJDUMP "D:/android-ndk-r30-windows/android-ndk-r30/toolchains/llvm/prebuilt/windows-x86_64/bin/llvm-objdump.exe")
endif()

if(NOT CMAKE_INSTALL_LOCAL_ONLY)
  # Include the install script for each subdirectory.
  include("D:/AnastacioEngine/build-android/source/gameengine/BlenderRoutines/cmake_install.cmake")
  include("D:/AnastacioEngine/build-android/source/gameengine/Common/cmake_install.cmake")
  include("D:/AnastacioEngine/build-android/source/gameengine/Converter/cmake_install.cmake")
  include("D:/AnastacioEngine/build-android/source/gameengine/Device/cmake_install.cmake")
  include("D:/AnastacioEngine/build-android/source/gameengine/Expressions/cmake_install.cmake")
  include("D:/AnastacioEngine/build-android/source/gameengine/GameLogic/cmake_install.cmake")
  include("D:/AnastacioEngine/build-android/source/gameengine/Ketsji/cmake_install.cmake")
  include("D:/AnastacioEngine/build-android/source/gameengine/Ketsji/KXNetwork/cmake_install.cmake")
  include("D:/AnastacioEngine/build-android/source/gameengine/Ketsji/KXImgui/cmake_install.cmake")
  include("D:/AnastacioEngine/build-android/source/gameengine/Launcher/cmake_install.cmake")
  include("D:/AnastacioEngine/build-android/source/gameengine/Physics/Dummy/cmake_install.cmake")
  include("D:/AnastacioEngine/build-android/source/gameengine/Rasterizer/cmake_install.cmake")
  include("D:/AnastacioEngine/build-android/source/gameengine/Rasterizer/Node/cmake_install.cmake")
  include("D:/AnastacioEngine/build-android/source/gameengine/Rasterizer/RAS_OpenGLFilters/cmake_install.cmake")
  include("D:/AnastacioEngine/build-android/source/gameengine/Rasterizer/RAS_OpenGLRasterizer/cmake_install.cmake")
  include("D:/AnastacioEngine/build-android/source/gameengine/SceneGraph/cmake_install.cmake")
  include("D:/AnastacioEngine/build-android/source/gameengine/Physics/Bullet/cmake_install.cmake")
  include("D:/AnastacioEngine/build-android/source/gameengine/GamePlayer/cmake_install.cmake")

endif()

string(REPLACE ";" "\n" CMAKE_INSTALL_MANIFEST_CONTENT
       "${CMAKE_INSTALL_MANIFEST_FILES}")
if(CMAKE_INSTALL_LOCAL_ONLY)
  file(WRITE "D:/AnastacioEngine/build-android/source/gameengine/install_local_manifest.txt"
     "${CMAKE_INSTALL_MANIFEST_CONTENT}")
endif()
