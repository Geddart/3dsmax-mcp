// Unit conventions for ParamBlock2 read-back (2026-10-12): TYPE_ANGLE is
// written/reported in degrees and TYPE_PCNT_FRAC in 0-100, matching MAXScript.
// Before the fix the bridge stored the user's "30" as 30 radians and "50" as
// a 50.0 fraction (5000 %).

#include "mcp_bridge/param_units.h"

#include <cmath>
#include <iostream>
#include <stdexcept>
#include <string>

namespace pu = mcp_bridge::param_units;

static void Check(bool ok, const char* what) {
    if (!ok) throw std::runtime_error(what);
}

static bool Near(double a, double b, double tol = 1e-9) { return std::fabs(a - b) < tol; }

int main() {
    try {
        // Degrees <-> radians round trip.
        Check(Near(pu::UserToStorage(pu::UnitKind::Degrees, 30.0), pu::kPi / 6.0), "30 deg -> pi/6 rad");
        Check(Near(pu::StorageToUser(pu::UnitKind::Degrees, pu::kPi / 6.0), 30.0), "pi/6 rad -> 30 deg");
        // The reported bug: 30 written raw reads back as 1718.87 deg.
        Check(Near(pu::StorageToUser(pu::UnitKind::Degrees, 30.0), 1718.873385, 1e-5),
              "raw 30 rad reads as 1718.87 deg (documents the bug)");

        // Percent <-> fraction round trip.
        Check(Near(pu::UserToStorage(pu::UnitKind::Percent, 50.0), 0.5), "50 % -> 0.5");
        Check(Near(pu::StorageToUser(pu::UnitKind::Percent, 0.5), 50.0), "0.5 -> 50 %");
        Check(Near(pu::StorageToUser(pu::UnitKind::Percent, 50.0), 5000.0), "raw 50 reads as 5000 % (documents the bug)");

        // Unitless passes through.
        Check(Near(pu::UserToStorage(pu::UnitKind::None, 4.5), 4.5), "None passthrough in");
        Check(Near(pu::StorageToUser(pu::UnitKind::None, 4.5), 4.5), "None passthrough out");
        Check(std::string(pu::UnitLabel(pu::UnitKind::Degrees)) == "degrees", "label degrees");
        Check(std::string(pu::UnitLabel(pu::UnitKind::Percent)) == "percent", "label percent");
        Check(std::string(pu::UnitLabel(pu::UnitKind::None)).empty(), "label none");

        // Read-back tolerance: relative 1e-5 with a floor of 1.
        Check(pu::FloatsMatch(6.5, static_cast<float>(6.5)), "exact float");
        Check(pu::FloatsMatch(pu::kPi / 6.0, static_cast<float>(pu::kPi / 6.0)), "float-rounded radians match");
        Check(pu::FloatsMatch(0.0, 5e-6), "absolute floor near zero");
        Check(!pu::FloatsMatch(0.0, 2e-5), "near-zero mismatch detected");
        Check(pu::FloatsMatch(100000.0, 100000.5), "relative tolerance on large values");
        Check(!pu::FloatsMatch(100000.0, 100002.0), "large mismatch detected");
        Check(!pu::FloatsMatch(12.5, 12.0), "int-truncated value is a mismatch");
        Check(!pu::FloatsMatch(1.0, std::nan("")), "NaN never matches");

        const double a[3] = {1.0, 2.0, 3.0};
        const double b[3] = {1.0, 2.0, 3.000001};
        const double c[3] = {1.0, 2.5, 3.0};
        Check(pu::ComponentsMatch(a, b, 3), "components within tolerance");
        Check(!pu::ComponentsMatch(a, c, 3), "component mismatch detected");

        // Rotation helpers used by transform_object read-back.
        Check(Near(pu::CanonicalRotationAngle(pu::kPi * 2.0 - 0.1), 0.1, 1e-12), "350-ish deg == 10-ish deg");
        Check(Near(pu::CanonicalRotationAngle(-pu::kPi / 2.0), pu::kPi / 2.0, 1e-12), "negative angle");
        const double qi[4] = {0.0, 0.0, 0.0, 1.0};
        const double qn[4] = {0.0, 0.0, 0.0, -1.0};
        const double s = std::sin(pu::kPi / 8.0), co = std::cos(pu::kPi / 8.0);
        const double q45[4] = {0.0, 0.0, s, co};  // 45 deg about Z
        Check(Near(pu::QuatRelativeAngle(qi, qn), 0.0, 1e-7), "q and -q are the same orientation");
        Check(Near(pu::QuatRelativeAngle(qi, q45), pu::kPi / 4.0, 1e-9), "45 deg relative rotation");

        std::cout << "param_units tests passed\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "FAIL: " << e.what() << "\n";
        return 1;
    }
}
