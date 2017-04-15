INCLUDE(FindPkgConfig)
PKG_CHECK_MODULES(PC_CRFA multirds)

FIND_PATH(
    CRFA_INCLUDE_DIRS
    NAMES multirds/api.h
    HINTS $ENV{CRFA_DIR}/include
        ${PC_CRFA_INCLUDEDIR}
    PATHS ${CMAKE_INSTALL_PREFIX}/include
          /usr/local/include
          /usr/include
)

FIND_LIBRARY(
    CRFA_LIBRARIES
    NAMES gnuradio-multirds
    HINTS $ENV{CRFA_DIR}/lib
        ${PC_CRFA_LIBDIR}
    PATHS ${CMAKE_INSTALL_PREFIX}/lib
          ${CMAKE_INSTALL_PREFIX}/lib64
          /usr/local/lib
          /usr/local/lib64
          /usr/lib
          /usr/lib64
)

INCLUDE(FindPackageHandleStandardArgs)
FIND_PACKAGE_HANDLE_STANDARD_ARGS(CRFA DEFAULT_MSG CRFA_LIBRARIES CRFA_INCLUDE_DIRS)
MARK_AS_ADVANCED(CRFA_LIBRARIES CRFA_INCLUDE_DIRS)

