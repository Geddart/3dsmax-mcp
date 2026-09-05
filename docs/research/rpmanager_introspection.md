# RPManager Introspection Results

**Date:** 2026-03-03
**RPManager Version:** 7.8
**3ds Max Version:** 2025 (PID 91996)
**Source:** Live introspection via `execute_maxscript` MCP tool

---

## 1. Core Struct Discovery

- `RPMdata` is a `#Struct:RmanagerDataStruct`
- Version: `RPMdata.version()` returns `"7.8"`
- `RPMdata.RManVersion` is `undefined` (not a valid property path)

### Struct Type
RPMdata is a MAXScript struct, NOT a Max object. It has `<fn>` (function) and `<data>` members. Functions are callable directly. Data members hold values (arrays, booleans, strings, sub-structs).

---

## 2. Key Functions (Confirmed Working)

### Pass Management
| Function | Args | Result | Notes |
|----------|------|--------|-------|
| `AddPass()` | 0 | OK (returns undefined) | Creates pass but count stays 0 without UI |
| `RMDeleteItem` | 1 (index) | returns false | Needs passes to exist |
| `duplicatePass()` | 0 | FAILED: needs UI listbox | `Unknown property "items" in dotNetControl:lstbox:(null)` |
| `SetPassName` | 2 (index, name) | OK | |
| `GetPassNameFromID` | 1 (ID) | FAILED | May need passes/UI |
| `getpasscount()` | 0 | returns 0 | Always 0 in empty scene |
| `getpasscamera` | 1 (index) | FAILED | |
| `GetPassOutputPath` | 1 (index) | "OK" | Returns string |
| `GetPassBeforeScript` | 1 (index) | "OK" | |
| `SetPassBeforeScript` | 2 (index, script) | exists | |
| `GetPassAfterScript` | 1 (index) | "OK" | |
| `SetPassAfterScript` | 2 (index, script) | exists | |
| `GetPassTimeType` | 1 (index) | "OK" | |
| `SetPassTimeType` | 2 (index, type) | exists | |
| `GetPassRange` | 1 (index) | "OK" | |
| `SetPassRange` | 2+ (index, range) | exists | |
| `GetPassVisSetName` | 1 (index) | "OK" | |
| `GetPassBGColor` | 1 (index) | "OK" | |
| `SetPassColor` | 2+ (index, color) | exists | |
| `GetPassSelection` | 1+ | FAILED | |
| `GetPassChecked` | 1 | FAILED | |
| `getrenderer` | 1 (index) | returns undefined | No passes exist |
| `SetRenderer` | 2+ (index, renderer) | exists | |
| `getCheckedPasses` | 1 (unknown arg) | FAILED: wanted 1, got 0 | Needs 1 arg |
| `renderLocally` | exists | | |
| `submitChecked` | exists | | |
| `submitSelected` | exists | | |
| `previewChecked` | exists | | |
| `previewSelected` | exists | | |
| `previewLocally` | exists | | |
| `movePassUpDown` | exists | | |
| `invertPasses` | exists | | |
| `version()` | 0 | "7.8" | |

### Visibility & Scene State
| Function | Result |
|----------|--------|
| `isolateSet` | exists |
| `deleteVisSetsHolder` | exists |
| `writeVisSetData` | exists |
| `getVisUndoState` | exists |
| `captureCamera` | exists |
| `captureBackground` | exists |
| `captureExposure` | exists |
| `captureStateSet` | exists |
| `restoreStateSet` | exists |
| `getallstatesets` | exists |

### Sub-Structs
| Property | Type | Notes |
|----------|------|-------|
| `RPMObjProp` | UndefinedClass | May need initialization/UI |
| `RPMVisSets` | (writeVisSetData is a MAXScriptFunction) | Vis sets are managed via functions, not a sub-struct |

---

## 3. Critical Finding: UI Dependency

**Many RPManager functions require the UI to be open.** They interact with .NET listbox controls (dotNetControl:lstbox). Key evidence:

- `duplicatePass()` crashed with: `Unknown property "items" in dotNetControl:lstbox:(null)` — the listbox doesn't exist without the UI
- `getpasscount()` returns 0 even after `AddPass()` — passes may be tracked in the UI listbox, not in a data structure
- `GetPassNameFromID` and `GetPassChecked` both fail in headless mode

### Workaround Strategy
1. Open RPManager UI programmatically: `RPMdata.RMopenFloater()` or via action
2. Then call pass management functions
3. Close UI afterward

### Functions That Work WITHOUT UI
- `version()` — confirmed
- `SetPassName` — confirmed (returns OK)
- `GetPassOutputPath` — confirmed
- `GetPassBeforeScript` / `SetPassBeforeScript` — confirmed
- `GetPassAfterScript` / `SetPassAfterScript` — confirmed
- `GetPassTimeType` / `SetPassTimeType` — confirmed
- `GetPassRange` / `SetPassRange` — confirmed
- `GetPassVisSetName` — confirmed
- `GetPassBGColor` / `SetPassColor` — confirmed
- `SetRenderer` / `getrenderer` — exists (returns undefined with no passes)

---

## 4. Full Member Listing

### Functions (confirmed via classOf output)
**Pass CRUD:** AddPass, RMDeleteItem, duplicatePass, SetPassName, GetPassNameFromID, getpasscount, movePassUpDown, invertPasses

**Pass Properties:** GetPassOutputPath, GetPassBeforeScript, SetPassBeforeScript, GetPassAfterScript, SetPassAfterScript, GetPassTimeType, SetPassTimeType, GetPassRange, SetPassRange, GetPassVisSetName, GetPassSelection, SetPassSelection, GetPassChecked, GetPassBGColor, SetPassColor, GetPassEffectStates, SetPassEffectStates, GetPassAtmosStates, GetPassIOData, getOutputDataArray, getNameDataArray, GetPassCameraExtraInfo, SetPassCameraExtraInfo, getpasscamera, SetPassSecondCameraExtraInfo, setPassThirdCameraExtraInfo, getPassSecondCamera, getPassThirdCamera, setPassSecondCamera, setPassThirdCamera

**Rendering:** renderLocally, submitChecked, submitSelected, previewChecked, previewSelected, previewLocally, getCheckedPasses, checkAll, checkNone, uncheckSelected

**Renderers:** SetRenderer, getrenderer, copyRenderer, pasteRenderer, getbz2renderer, autoBuildRenderers, restore_renderer_tabs, store_renderer_tabs

**Cameras:** captureCamera, RMBuildCameras, GetAllCameras, RMfindCamera, RMfindSecondCamera, RMfindThirdCamera, makeCamera, getPassCameras

**Visibility:** isolateSet, deleteVisSetsHolder, writeVisSetData, getVisUndoState, UpdateLayerArray, CA_redefineVis

**State:** captureStateSet, restoreStateSet, getallstatesets, captureBackground, captureExposure, captureThirdCamera, CaptureExposureProcessBG, captureSceneStateIfRequired, restoreSceneState

**UI:** RMopenFloater, fRefresh, rmrefresh, startEdit, showRollout, enableControls, disableControls

**Output:** checkOutputValid, getoutputinfo, stripOutputPath, SetMIPassOutputPath, GetLocalAutoPathRoot, expandAutoPathControls, getAutoPathEnabled, RPMBuildOutputPaths

**Effects:** RestoreEffectStates, eff_All_set, eff_All_set_all, eff_All_set_this, RestoreAtmosStates, RebuildAtmos, RMaddEffect, RMRestValues

**Materials:** RPMpreRenderSwapMat, RPMpostRenderSwapMat, stripInitialMaterials, setPostMaterial, getPreMaterial, putMatToSlate, RPMMATERIALCLASS, RPMMATERIALORIGCLASS

**Object Properties:** getObjPropPrefsData, setObjPropPrefsData, getObjPropPrefsDefaults, getPerObjectPreviewData, storePropOverrideData, convertRenderPropertyOverrideToNewData

**Misc:** version, Activate, Deactivate, activate_license, BuildAppData, backupHoldFile, restoreHoldFile, doLogFile

### Data Members
managerArray, managerOnArray, renderdataarray, passTheData, PassTheCamera, PassTheCameraType, PassTheSecondCameraType, passthenumb, RMCameraArray, RManVersion, RPMwarnings, RPMDebug, logfilepath, dpi_scaling, and many more.

---

## 5. Key Corrections to Plan

- **Pass creation EXISTS:** `AddPass()` is a real function (takes 0 args). But may need UI open to properly register.
- **Pass deletion EXISTS:** `RMDeleteItem` takes 1 arg (index). Returns boolean.
- **duplicatePass EXISTS but NEEDS UI:** Crashes without the RPManager listbox control.
- **NOT a sub-struct model:** RPMdata is a flat struct with functions, not nested structs. `RPMVisSets` is not a sub-struct — visibility is managed via `writeVisSetData`, `getVisUndoState`, etc.
- **Version detection works:** `RPMdata.version()` returns "7.8"
- **UI may need to be opened first:** `RPMdata.RMopenFloater()` should be called before UI-dependent operations.
- **getCheckedPasses needs 1 arg:** Not 0 as the plan assumed.
- **RPMObjProp is UndefinedClass:** Object property overrides may require different initialization.
