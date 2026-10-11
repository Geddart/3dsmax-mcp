// Regression test for the de-DE locale bug (Kaschmir, 2026-10-12).
// 3ds Max runs with the CRT locale of the Windows region. Under German
// LC_NUMERIC, std::stof("4.5") == 4 and printf("%g", 4.5) == "4,5", which
// silently dropped every fractional parameter sent through the bridge.
// The bridge's number_text helpers must be immune to that locale.

#include "mcp_bridge/number_text.h"

#include <clocale>
#include <cmath>
#include <cstdio>
#include <iostream>
#include <stdexcept>
#include <string>

namespace nt = mcp_bridge::number_text;

static void Check(bool ok, const char* what) {
    if (!ok) throw std::runtime_error(what);
}

static bool Near(double a, double b) { return std::fabs(a - b) < 1e-6; }

int main() {
    try {
        // Reproduce Max's environment: a German numeric locale for the CRT.
        if (!std::setlocale(LC_ALL, "de-DE") && !std::setlocale(LC_ALL, "German_Germany.1252")) {
            std::cerr << "SKIP: German locale not available on this machine\n";
            return 0;
        }
        // Prove the trap is live in this process, otherwise the test proves nothing.
        Check(std::stof("4.5") == 4.0f, "harness: std::stof should truncate under de-DE");
        char buf[32];
        std::snprintf(buf, sizeof(buf), "%g", 4.5);
        Check(std::string(buf) == "4,5", "harness: printf should emit a decimal comma under de-DE");

        double d = 0;
        Check(nt::ParseDouble("4.5", d) && Near(d, 4.5), "ParseDouble 4.5");
        Check(nt::ParseDouble(" 0.7 ", d) && Near(d, 0.7), "ParseDouble trims");
        Check(nt::ParseDouble("+6.5", d) && Near(d, 6.5), "ParseDouble leading plus");
        Check(nt::ParseDouble("-3", d) && Near(d, -3.0), "ParseDouble integer");
        Check(!nt::ParseDouble("4,5", d), "ParseDouble must reject a decimal comma");
        Check(!nt::ParseDouble("4.5cm", d), "ParseDouble must reject trailing units");
        Check(!nt::ParseDouble("5*2", d), "ParseDouble must reject expressions");
        Check(!nt::ParseDouble("", d), "ParseDouble must reject empty");

        int i = 0;
        Check(nt::ParseInt("12", i) && i == 12, "ParseInt");
        Check(!nt::ParseInt("4.5", i), "ParseInt must not truncate 4.5");

        double v[4] = {};
        Check(nt::ParseDoubleList("[-276.8,-3.5,-3]", v, 3) && Near(v[0], -276.8) && Near(v[1], -3.5) && Near(v[2], -3),
              "Point3 bracket form");
        Check(nt::ParseDoubleList("1.5, 2.5, 3.5", v, 3) && Near(v[2], 3.5), "Point3 comma form");
        Check(nt::ParseDoubleList("1.5 2.5 3.5", v, 3) && Near(v[1], 2.5), "Point3 space form");
        Check(!nt::ParseDoubleList("[1,2]", v, 3), "Point3 too few values");
        Check(!nt::ParseDoubleList("[1,2,3,4]", v, 3), "Point3 too many values");

        int n = 0;
        Check(nt::ParseMaxColor("(color 48 32 22)", v, n) && n == 3 && Near(v[0], 48) && Near(v[2], 22), "colour rgb");
        Check(nt::ParseMaxColor("color 48.5 32 22 255", v, n) && n == 4 && Near(v[0], 48.5) && Near(v[3], 255), "colour rgba");
        Check(!nt::ParseMaxColor("[48,32,22]", v, n), "list is not colour syntax");

        Check(nt::FormatDouble(4.5) == "4.5", "FormatDouble 4.5");
        Check(nt::FormatFloat(0.7f) == "0.7", "FormatFloat shortest round-trip");
        Check(nt::FormatFloat(-276.8f) == "-276.8", "FormatFloat negative");
        const float p3[3] = {-276.8f, -3.5f, -3.0f};
        Check(nt::FormatList(p3, 3) == "[-276.8,-3.5,-3]", "FormatList");
        Check(nt::FormatMaxColor(48.0f / 255.0f, 32.0f / 255.0f, 22.0f / 255.0f, true) == "(color 48 32 22)",
              "FormatMaxColor 0-1 to 0-255");

        // Round trip text -> value -> text stays exact for typical scene values.
        for (const char* text : {"4.5", "10.25", "0.7", "6.5", "-276.8", "1e-05"}) {
            float f = 0;
            Check(nt::ParseFloat(text, f), text);
            float back = 0;
            Check(nt::ParseFloat(nt::FormatFloat(f), back) && back == f, text);
        }

        std::cout << "PASS: number_text is locale-independent under de-DE "
                     "(parse 4.5/0.7/Point3/colour, reject 4,5 and units, format with '.')\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "FAIL: " << e.what() << "\n";
        return 1;
    }
}
