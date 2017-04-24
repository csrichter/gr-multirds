INCLUDE(FindPkgConfig)
PKG_CHECK_MODULES(PC_MULTIRDS multirds)

FIND_PATH(
    MULTIRDS_INCLUDE_DIRS
    NAMES multirds/api.h
    HINTS $ENV{MULTIRDS_DIR}/include
        ${PC_MULTIRDS_INCLUDEDIR}
    PATHS ${CMAKE_INSTALL_PREFIX}/include
          /usr/local/include
          /usr/include
)

FIND_LIBRARY(
    MULTIRDS_LIBRARIES
    NAMES gnuradio-multirds
    HINTS $ENV{MULTIRDS_DIR}/lib
        ${PC_MULTIRDS_LIBDIR}
    PATHS ${CMAKE_INSTALL_PREFIX}/lib
          ${CMAKE_INSTALL_PREFIX}/lib64
          /usr/local/lib
          /usr/local/lib64
          /usr/lib
          /usr/lib64
)

INCLUDE(FindPackageHandleStandardArgs)
FIND_PACKAGE_HANDLE_STANDARD_ARGS(MULTIRDS DEFAULT_MSG MULTIRDS_LIBRARIES MULTIRDS_INCLUDE_DIRS)
MARK_AS_ADVANCED(MULTIRDS_LIBRARIES MULTIRDS_INCLUDE_DIRS)

