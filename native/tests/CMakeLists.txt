cmake_minimum_required(VERSION 3.20)
project(mcp_transport_tests LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
add_executable(transport_tests transport_tests.cpp ../src/main_thread_executor.cpp)
target_include_directories(transport_tests PRIVATE ../include)
target_compile_definitions(transport_tests PRIVATE UNICODE _UNICODE)
target_link_libraries(transport_tests PRIVATE user32)
enable_testing()
add_test(NAME transport_regressions COMMAND transport_tests)

# de-DE locale regression for the bridge's number <-> text helpers (SDK-free).
add_executable(number_text_tests number_text_tests.cpp)
target_include_directories(number_text_tests PRIVATE ../include)
add_test(NAME number_text_locale COMMAND number_text_tests)
