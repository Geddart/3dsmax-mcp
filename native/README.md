# Native MCP bridge builds

Build each plugin against its matching 3ds Max SDK using Visual Studio 2022
(v143), x64 Release. Keep build directories short to avoid MSBuild FTK1011
errors when `.tlog` paths exceed MAX_PATH.

## Build matrix

| Max | C++ standard | Packaged binary status |
| --- | --- | --- |
| 2023 | C++17 | Older binary; rebuild with matching SDK before shipping |
| 2024 | C++17 | Older binary; rebuild with matching SDK before shipping |
| 2025 | C++17 | Contains transport/executor and `vfb:false` fixes; rebuild verified against committed binary |
| 2026 | C++17 | Older binary; rebuild with matching SDK before shipping |
| 2027 | C++20 | Rebuilt from this worktree with the 2027 SDK; not yet live-tested |

The 2023/2024/2026 binaries predate the transport/executor and `vfb:false` fixes.
`MAX_SDK_VERSION` is defined by CMake as the target year (for example, 2027),
distinct from the SDK's major version 29.

## Verified commands

Run from the repository root in PowerShell:

```powershell
cmake -S native -B C:\mcpwt\bld27 -G "Visual Studio 17 2022" -A x64 -DMAX_VERSION=2027
cmake --build C:\mcpwt\bld27 --config Release
Copy-Item -LiteralPath C:\mcpwt\bld27\Release\mcp_bridge.gup -Destination native/bin/mcp_bridge_2027.gup

cmake -S native -B C:\mcpwt\bld25 -G "Visual Studio 17 2022" -A x64 -DMAX_VERSION=2025 "-DMAXSDK_PATH=H:\001_ProjectCache\1000_Coding\maxsdk_2025\Program Files\Autodesk\3ds Max 2025 SDK\maxsdk"
cmake --build C:\mcpwt\bld25 --config Release

cmake -S native/tests -B C:\mcpwt\bldtests -G "Visual Studio 17 2022" -A x64
cmake --build C:\mcpwt\bldtests --config Release
& C:\mcpwt\bldtests\Release\transport_tests.exe
```

The 2027 SDK was found at its default path,
`C:\Program Files\Autodesk\3ds Max 2027 SDK\maxsdk`.
These builds used MSVC 19.43.34810.0 (toolset directory 14.43.34808),
MSBuild 17.14.40 and Windows SDK 10.0.26100.0. No compiler/linker warnings
were reported. No additional source compatibility guards were needed.

The rebuilt 2027 binary is 2,066,944 bytes. Both the committed and rebuilt
2025 binaries are 2,135,552 bytes and have identical imports. Their extracted
strings differ only in two compiler-generated anonymous-namespace RTTI names;
their COFF timestamps also differ. The 2025 rebuild is not byte-identical,
but the size/import/string comparison found no material difference, so the
committed 2025 binary was retained.

All three binaries contain `GetOverlappedResult`,
`MainThreadExecutor is shutting down` and `vfb:false`, and lack `vfb:true`.
The 2027 dependency check includes `core.dll`, `maxutil.dll`, `gup.dll`,
`ParamBlk2.dll`, `MAXScrpt.dll`, `Geom.dll` and `MSVCP140.dll`, with no debug CRT.
Native transport regression tests passed. These are build/static checks;
the new 2027 binary has not been deployed or live-tested.

`build.bat` also supports year selection and stages binaries in both
`native/bin` and `bundle/Contents/bin`, but uses build directories under
`native`. The explicit commands above permit shorter build paths. CMake's
install target writes to `MAX_PLUGINS_DIR`; do not run it for a build-only check.
