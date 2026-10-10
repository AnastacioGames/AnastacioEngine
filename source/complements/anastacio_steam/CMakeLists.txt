cmake_minimum_required(VERSION 3.15)
project(AnastacioSteam LANGUAGES CXX)
if(NOT WIN32 OR NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
    message(FATAL_ERROR "This first Steam complement supports Windows x64 only")
endif()
set(ANASTACIO_STEAM_SDK "" CACHE PATH "Local official Steamworks SDK root (not committed)")
if(NOT EXISTS "${ANASTACIO_STEAM_SDK}/public/steam/steam_api.h")
    message(FATAL_ERROR "Set ANASTACIO_STEAM_SDK to the local SDK directory")
endif()
add_library(AnastacioSteam SHARED AnastacioSteam.cpp)
target_compile_features(AnastacioSteam PRIVATE cxx_std_17)
target_include_directories(AnastacioSteam PRIVATE
    "${ANASTACIO_STEAM_SDK}/public" "${CMAKE_CURRENT_SOURCE_DIR}/../../source/gameengine/Network")
target_link_libraries(AnastacioSteam PRIVATE "${ANASTACIO_STEAM_SDK}/redistributable_bin/win64/steam_api64.lib")
target_link_libraries(AnastacioSteam PRIVATE shell32)
if(MSVC)
    # No C++ allocations cross the ABI; keep the complement's CRT self-contained.
    set_property(TARGET AnastacioSteam PROPERTY MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
    target_compile_options(AnastacioSteam PRIVATE /W4 /EHsc)
endif()
# Local test output only; no install/release packaging at this stage.
add_custom_command(TARGET AnastacioSteam POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
    "${ANASTACIO_STEAM_SDK}/redistributable_bin/win64/steam_api64.dll"
    "$<TARGET_FILE_DIR:AnastacioSteam>/steam_api64.dll")
include(CTest)
if(BUILD_TESTING)
    add_executable(anastacio_steam_policy_tests AnastacioSteam_tests.cpp)
    target_compile_features(anastacio_steam_policy_tests PRIVATE cxx_std_17)
    target_include_directories(anastacio_steam_policy_tests PRIVATE
        "${ANASTACIO_STEAM_SDK}/public" "${CMAKE_CURRENT_SOURCE_DIR}/../../source/gameengine/Network")
    target_link_libraries(anastacio_steam_policy_tests PRIVATE
        "${ANASTACIO_STEAM_SDK}/redistributable_bin/win64/steam_api64.lib" shell32)
    if(MSVC)
        set_property(TARGET anastacio_steam_policy_tests PROPERTY MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
    endif()
    add_test(NAME anastacio_steam_policy COMMAND anastacio_steam_policy_tests)
endif()
