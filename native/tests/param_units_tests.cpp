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

        // Scale read-back (review 2026-10-12): the full basis is compared, not the
        // determinant ratio, so a refused [2,0.5,1] or [-1,-1,1] is caught.
        using F = pu::ScaleFrame;
        const double I[9] = {1, 0, 0, 0, 1, 0, 0, 0, 1};
        const double s1[3] = {2.0, 0.5, 1.0};
        const double scaled[9] = {2, 0, 0, 0, 0.5, 0, 0, 0, 1};
        Check(pu::AppliedScaleFrame(I, scaled, s1) == F::World, "identity basis scaled [2,0.5,1]");
        Check(pu::AppliedScaleFrame(I, I, s1) == F::None, "refused [2,0.5,1] (det ratio 1) is caught");
        const double flip[3] = {-1.0, -1.0, 1.0};
        Check(pu::AppliedScaleFrame(I, I, flip) == F::None, "ignored two-axis sign flip is caught");
        const double flipped[9] = {-1, 0, 0, 0, -1, 0, 0, 0, 1};
        Check(pu::AppliedScaleFrame(I, flipped, flip) == F::World, "applied sign flip");
        // Rotated (30 deg about Z) and non-uniformly scaled basis, scaled along world vs local axes.
        const double cz = std::cos(pu::kPi / 6.0), sz = std::sin(pu::kPi / 6.0);
        const double R[9] = {cz * 1.5, sz * 1.5, 0, -sz * 0.7, cz * 0.7, 0, 0, 0, 2.0};
        const double s2[3] = {1.5, 1.0, 2.0};
        double world[9], local[9];
        const double D[9] = {s2[0], 0, 0, 0, s2[1], 0, 0, 0, s2[2]};
        pu::Mul3(R, D, world);
        pu::Mul3(D, R, local);
        Check(pu::AppliedScaleFrame(R, world, s2) == F::World, "rotated node, world-axis scale");
        Check(pu::AppliedScaleFrame(R, local, s2) == F::Local, "rotated node, local-axis scale");
        Check(pu::AppliedScaleFrame(R, R, s2) == F::None, "rotated node, refused scale");
        double partly[9];
        const double s3[3] = {1.5, 1.0, 1.0};
        const double D3[9] = {1.5, 0, 0, 0, 1, 0, 0, 0, 1};
        pu::Mul3(R, D3, partly);
        Check(pu::AppliedScaleFrame(R, partly, s2) == F::None, "only one axis applied");
        float rounded[9];
        double back[9];
        for (int i = 0; i < 9; ++i) { rounded[i] = static_cast<float>(world[i]); back[i] = rounded[i]; }
        Check(pu::AppliedScaleFrame(R, back, s2) == F::World, "float32 TM rounding tolerated");
        const double flat[9] = {1, 0, 0, 0, 1, 0, 0, 0, 0};
        Check(pu::AppliedScaleFrame(flat, flat, s1) == F::None, "flat (singular) basis cannot be verified");
        double inv[9], prod[9];
        Check(pu::Invert3(R, inv), "invertible");
        pu::Mul3(R, inv, prod);
        const double ones[3] = {1.0, 1.0, 1.0};
        Check(pu::IsDiagonal(prod, ones, 1e-12), "R * inv(R) == I");

        std::cout << "param_units tests passed\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "FAIL: " << e.what() << "\n";
        return 1;
    }
}
