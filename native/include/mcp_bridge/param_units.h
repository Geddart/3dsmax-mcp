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

}  // namespace param_units
}  // namespace mcp_bridge
