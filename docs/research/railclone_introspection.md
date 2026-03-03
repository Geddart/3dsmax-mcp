# RailClone Pro Introspection Results

**Date:** 2026-03-03
**3ds Max Version:** 2025 (PID 91996)
**Source:** Live introspection via `execute_maxscript` MCP tool

---

## 1. Class Discovery

```
RailClone_Pro(RailClone Pro) : GeometryClass {39712def,10a72959}
RailClone_Tools(RailClone Tools) : UtilityPlugin {38ad7fa2,6c63900}
RailClone_Exporter(RailClone Exporter) : ExporterPlugin {6e84346a,200916ea}
RailClone_Importer(RailClone Importer) : ImporterPlugin {7bd112f6,604c74aa}
RailClone_Color(RailClone Color) : textureMap {7db47ecb,2e0566c9}
RC_Slice(RC Slice) : modifier {717436f2,346b4bd6}
RC_Spline(RC Spline) : modifier {8e36fd98,a6d5096a}
```

---

## 2. RailClone_Pro Properties (166 total)

```
.spline : node
.maxtime : integer
.seed : integer
.iconsize : float
.style : string
.maxpath : integer
.geomtex : texturemap
.geomver : integer
.savedversion : string
.createdversion : integer
.rcSplineCustom : string
.gscale : float
.curvesteps : integer
.surfinterp : worldUnits
.renderid : string
.simpleoffset : boolean
.freeobject : boolean
.stylelink : node
.stylelinkmat : boolean
.nodemat : boolean
.surfedgetolerance : float
```

### Base Object Arrays (ba*)
```
.baid : string array
.batype : integer array
.baname : string array
.banode : node array
.bafull : boolean array
.bastart : float array
.balength : float array
.badesc : string array
```

### Exposed Parameter Arrays (pa*)
```
.paid : string array
.patype : integer array          -- 0=int, 1=float, 3=worldUnits, others TBD
.paname : string array
.palimit : boolean array
.paintval : integer array
.paintmin : integer array
.paintmax : integer array
.pafloatval : float array
.pafloatmin : float array
.pafloatmax : float array
.paunitval : worldUnits array
.paunitmin : worldUnits array
.paunitmax : worldUnits array
.paboolval : boolean array
.pastrval : string array
.paselector : string array
.padesc : string array
.pamodified : boolean array
.paretain : integer array
```

### Segment Arrays (s*)
```
.sid : string array
.sname : string array
.sflags : integer array
.sobjref : maxObject array
.sobjoffset : matrix3 array
.sobjnodetm : matrix3 array
.sobjnode : node array
.sobjmtl : material array
.slicesrc : integer array
.spos : point3 array
.srot : point3 array
.ssca : point3 array
.sxalign : integer array
.syalign : integer array
.szalign : integer array
.spadin : worldUnits array
.spadout : worldUnits array
.spadtop : worldUnits array
.spadbottom : worldUnits array
.sfixedsize : point3 array
.ssizescale : boolean array
.sinstance : boolean array
.sbend : boolean array
.sslice : boolean array
.snesting : boolean array
.szdeform : integer array
.ssurfconform : boolean array
.ssurfnormal : boolean array
.sslopefix : boolean array
.sflattop : worldUnits array
.sflatbottom : worldUnits array
.srandtrans : boolean array
.srandrot : boolean array
.srandscale : boolean array
.srandmat : boolean array
.srt1 : point3 array
.srt2 : point3 array
.srr1 : point3 array
.srr2 : point3 array
.srs1 : point3 array
.srs2 : point3 array
.smaterial : integer array
.smatrange : integer array
.smapping : boolean array
.smapreal : boolean array
.smapchans : string array
.smapsize : point3 array
.smapoff : point3 array
.smaprotx : float array
.smaproty : float array
.smaprotz : float array
```

### V1 Legacy Properties
```
.v1yoffset, .v1zoffset, .v1gscale, .v1mirror, .v1flipa, .v1flipb, .v1flatstepped
.v1beveloffset, .v1filletrad, .v1distance, .v1distadjust
```

### Display/Render
```
.autoupdate : boolean
.disabled : boolean
.vmesh : integer
.adaptfaces : integer
.cloudens : integer
.cloudcid : boolean
.rmesh : integer
.rendermode : boolean
.maxseg : integer
.maxfaces : float
.nongeomatid : integer
.showinst : boolean
.debugmatid : integer
.drawgizmopolys : integer
.proxymode : integer
.proxyfile : filename
.proxyversion : integer
```

---

## 3. Interfaces

### global Interface
```
RegisterEngine()
version() -> integer
SetEngineFeatures(integerPtr features)
Instantiate(integer mode, &string layer, boolean autoDelete, boolean separatedMeshes, boolean forceInstances, boolean disableAtEnd)
InstantiateDelete()
InstantiateEnable()
exportData(string filename, string fieldlist, integer format) -> integer
```

### railclone Interface
```
segmentsUpdate(integer n1, integer n2)
getStyleDesc() -> string
setStyleDesc(&string description)
resetCreatedVersion()
setCreatedVersion(integer version)
upgradeFromVersion(integer version)
setNodesCache(integer state)
setProxyMode(integer mode, &string proxyfile)
loadLibraryItemByPath(&string path) -> integer
```

### scatalog Interface (same as Forest Pack)
```
openBrowser(), closeBrowser(), refresh(), getMacroCount(), evalMacro(), getMacro(), setMacro(), setOverlay(), getSelItemName(), getSelItemProp(), getSelItemCustomProp()
```

---

## 4. Base Object (banode) Testing

- `rc.banode[1] = splineObject` — **WORKS**
- `rc.banode.count` starts at 0, becomes 1 after assignment
- `rc.batype` and `rc.baname` arrays start empty (populated by library loading)
- banode accepts any node (tested with SplineShape)

---

## 5. Library Loading

- `rc.railclone.loadLibraryItemByPath "\\RailClone Library\\Architecture\\Exterior\\Railings\\Handrail 1"` returned **1** (success)
- After loading: `paname.count = 0` (this particular style had no exposed parameters)
- The `style` property remained empty string (style data is stored internally)

### Notable Finding
Library loading works but exposed parameters depend on the style. Need to test with styles that have Numeric nodes wired to parameters.

---

## 6. Helper Classes

### RailClone_Color (textureMap)
```
.mapbase : texturemap
.mapidmode : integer
.colorbase : color
.maplist : texturemap array
.maponlist : boolean array
.colorlist : color array
.problist : float array
.tintmixmode : integer
.tintvariation : float
.override : boolean
.tintcolor1 : color
.tintcolor2 : color
.tintmin : integer
.tintmax : integer
.tintmode : integer
.tintmap : texturemap
.tintmapmode : integer
```

### RC_Slice (modifier)
28 properties for slice positioning:
```
.start, .stasize, .end, .endsize
.xde, .xdepos, .xdesize, .xev, .xevpos, .xevsize, .xcr, .xcrpos, .xcrsize
.adjusty, .top, .topsize, .bottom, .botsize
.yde, .ydepos, .ydesize, .yev, .yevpos, .yevsize
.adjustx, .output, .operateon, .exname
```

### RC_Spline (modifier)
34 properties for spline marker control:
```
.mktype, .mkdesc, .mkuserid, .mkspline, .mkallsplines, .mkpercent, .mkdist
.mkreference, .mkrefid, .mkuserdata0-8, .mkuserlabel0-8, .mkusertype0-8
.mkshowgidzmos, .bkgizmosize, .bkspline, .bkpercent, .bkangle, .bkshowgidzmos
```

---

## 7. Key Corrections to Plan

- **Class name confirmed:** `RailClone_Pro` (not `RailClone` or `RC_Pro`)
- **loadLibraryItemByPath confirmed working** — library-first approach is viable
- **banode indexing confirmed**: `rc.banode[1]` for X path (tested with spline)
- **Exposed parameter arrays confirmed**: extensive pa* arrays with type/min/max/value
- **Segment arrays are read-only from MAXScript** — cannot construct style graphs programmatically (as plan noted)
- **Additional classes found**: RailClone_Exporter, RailClone_Importer — could enable .rcproxy export/import
