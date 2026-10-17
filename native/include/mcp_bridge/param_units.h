#pragma once
// User-unit conventions for ParamBlock2 values, shared by every native setter
// and every inspect formatter so a value written through the bridge reads back
// in the same units it was written in.
//
// MAXScript (and therefore every caller of the bridge) speaks DEGREES for
// TYPE_ANGLE and 0-100 for TYPE_PCNT_FRAC, while the parameter block stores
// radians and 0-1. Writing the user's text straight into storage turned
// sliceFrom:30 into 30 rad (1718.87 deg) and opacity:50 into 5000 %.
//
// No SDK dependency: native/tests exercises this header directly.

#include <algorithm>
#include <cmath>

namespace mcp_bridge {
namespace param_units {

enum class UnitKind { None, Degrees, Percent };

constexpr double kPi = 3.14159265358979323846;

inline double UserToStorage(UnitKind kind, double userValue) {
    switch (kind) {
    case UnitKind::Degrees: return userValue * (kPi / 180.0);
    case UnitKind::Percent: return userValue / 100.0;
    default: return userValue;
    }
}

inline double StorageToUser(UnitKind kind, double storedValue) {
    switch (kind) {
    case UnitKind::Degrees: return storedValue * (180.0 / kPi);
    case UnitKind::Percent: return storedValue * 100.0;
    default: return storedValue;
    }
}

// Label reported next to inspected values ("" when the value is unitless or
// already in storage units).
inline const char* UnitLabel(UnitKind kind) {
    switch (kind) {
    case UnitKind::Degrees: return "degrees";
    case UnitKind::Percent: return "percent";
    default: return "";
    }
}

// Read-back comparison in STORAGE units: |want - got| <= relTol * max(1, |want|).
inline bool FloatsMatch(double want, double got, double relTol = 1e-5) {
    if (!std::isfinite(want) || !std::isfinite(got)) return want == got;
    return std::fabs(want - got) <= relTol * std::max(1.0, std::fabs(want));
}

inline bool ComponentsMatch(const double* want, const double* got, int count, double relTol = 1e-5) {
    for (int i = 0; i < count; ++i) {
        if (!FloatsMatch(want[i], got[i], relTol)) return false;
    }
    return true;
}

// Smallest angle (radians, in [0, pi]) equivalent to `angle` — a rotation by
// 350 deg and by -10 deg move a node the same way.
inline double CanonicalRotationAngle(double angle) {
    double a = std::fmod(std::fabs(angle), 2.0 * kPi);
    if (a > kPi) a = 2.0 * kPi - a;
    return a;
}

// Angle (radians, in [0, pi]) of the rotation between two unit quaternions,
// treating q and -q as the same orientation.
inline double QuatRelativeAngle(const double* q1, const double* q2) {
    double dot = q1[0] * q2[0] + q1[1] * q2[1] + q1[2] * q2[2] + q1[3] * q2[3];
    dot = std::min(1.0, std::fabs(dot));
    return 2.0 * std::acos(dot);
}

// ── Scale read-back (transform_object) ───────────────────────────────────
// 3x3 matrices are row-major double[9] in Max's row-vector convention
// (p_world = p_local * M; row r is local axis r in world space).

inline double Det3(const double* m) {
    return m[0] * (m[4] * m[8] - m[5] * m[7]) - m[1] * (m[3] * m[8] - m[5] * m[6]) +
           m[2] * (m[3] * m[7] - m[4] * m[6]);
}

inline bool Invert3(const double* m, double* out) {
    const double det = Det3(m);
    double scale = 0.0;
    for (int i = 0; i < 9; ++i) scale = std::max(scale, std::fabs(m[i]));
    if (!std::isfinite(det) || scale == 0.0 || std::fabs(det) <= 1e-12 * scale * scale * scale) return false;
    out[0] = (m[4] * m[8] - m[5] * m[7]) / det;
    out[1] = (m[2] * m[7] - m[1] * m[8]) / det;
    out[2] = (m[1] * m[5] - m[2] * m[4]) / det;
    out[3] = (m[5] * m[6] - m[3] * m[8]) / det;
    out[4] = (m[0] * m[8] - m[2] * m[6]) / det;
    out[5] = (m[2] * m[3] - m[0] * m[5]) / det;
    out[6] = (m[3] * m[7] - m[4] * m[6]) / det;
    out[7] = (m[1] * m[6] - m[0] * m[7]) / det;
    out[8] = (m[0] * m[4] - m[1] * m[3]) / det;
    return true;
}

inline void Mul3(const double* a, const double* b, double* out) {
    for (int r = 0; r < 3; ++r)
        for (int c = 0; c < 3; ++c)
            out[r * 3 + c] = a[r * 3] * b[c] + a[r * 3 + 1] * b[3 + c] + a[r * 3 + 2] * b[6 + c];
}

// |m - diag(s)| element-wise within relTol * max|s|.
inline bool IsDiagonal(const double* m, const double* s, double relTol) {
    double mag = 0.0;
    for (int i = 0; i < 3; ++i) mag = std::max(mag, std::fabs(s[i]));
    const double tol = relTol * std::max(mag, 1e-9);
    for (int r = 0; r < 3; ++r)
        for (int c = 0; c < 3; ++c)
            if (std::fabs(m[r * 3 + c] - (r == c ? s[r] : 0.0)) > tol) return false;
    return true;
}

enum class ScaleFrame { None, World, Local };

// Which axis frame the node's 3x3 was scaled by `s` in, comparing the FULL
// transform (a determinant ratio accepted [2,0.5,1] refused as "volume x1"
// and hid two-axis sign flips). World: after = before * diag(s) (scale along
// world axes about the pivot). Local: after = diag(s) * before (scale along
// the node's own axes, how a Max scale controller may apply it). None: the
// basis did not change by s in either frame (refused, partly applied, or a
// degenerate starting basis).
inline ScaleFrame AppliedScaleFrame(const double* before, const double* after, const double* s,
                                    double relTol = 1e-3) {
    double inv[9];
    if (!Invert3(before, inv)) return ScaleFrame::None;
    double d[9];
    Mul3(inv, after, d);
    if (IsDiagonal(d, s, relTol)) return ScaleFrame::World;
    Mul3(after, inv, d);
    if (IsDiagonal(d, s, relTol)) return ScaleFrame::Local;
    return ScaleFrame::None;
}

}  // namespace param_units
}  // namespace mcp_bridge
