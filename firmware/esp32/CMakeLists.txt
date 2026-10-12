cmake_minimum_required(VERSION 3.16)
set(EXTRA_COMPONENT_DIRS
    "${CMAKE_CURRENT_LIST_DIR}/components/pmars_core"
    "${CMAKE_CURRENT_LIST_DIR}/components/pmars_hal"
    "${CMAKE_CURRENT_LIST_DIR}/components/pmars_proto")
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(pmars_esp32)
