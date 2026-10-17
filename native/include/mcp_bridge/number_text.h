#pragma once
// Locale-independent number <-> text conversion for the bridge.
//
// 3ds Max runs with the C runtime locale taken from the Windows region. On a
// German system LC_NUMERIC uses ',' as the decimal separator, so std::stof,
// sscanf("%f"), printf("%g") and std::to_string(double) silently read "4.5"
// as 4 and write 4.5 as "4,5". MAXScript and JSON always use '.', so every
// numeric conversion in the bridge must go through these helpers instead.
//
// std::from_chars / std::to_chars never consult the locale. This header has no
// SDK dependency so native/tests can exercise it directly.

#include <charconv>
#include <cmath>
#include <string>
#include <string_view>
#include <system_error>

namespace mcp_bridge {
namespace number_text {

inline std::string_view Trim(std::string_view s) {
    const char* ws = " \t\r\n";
    const size_t b = s.find_first_not_of(ws);
    if (b == std::string_view::npos) return {};
    const size_t e = s.find_last_not_of(ws);
    return s.substr(b, e - b + 1);
}

// Parse the WHOLE string as one floating-point number ('.' decimal point).
// Returns false on anything else ("4,5", "4.5cm", "5*2", "") so callers can
// fall back to MAXScript instead of storing a truncated value.
inline bool ParseDouble(std::string_view s, double& out) {
    s = Trim(s);
    if (!s.empty() && s.front() == '+') s.remove_prefix(1);
    if (s.empty()) return false;
    double v = 0.0;
    const auto [ptr, ec] = std::from_chars(s.data(), s.data() + s.size(), v);
    if (ec != std::errc() || ptr != s.data() + s.size() || !std::isfinite(v)) return false;
    out = v;
    return true;
}

inline bool ParseFloat(std::string_view s, float& out) {
    double d = 0.0;
    if (!ParseDouble(s, d)) return false;
    out = static_cast<float>(d);
    return true;
}

// Parse the WHOLE string as one integer. Rejects "4.5" rather than truncating.
inline bool ParseInt(std::string_view s, int& out) {
    s = Trim(s);
    if (!s.empty() && s.front() == '+') s.remove_prefix(1);
    if (s.empty()) return false;
    int v = 0;
    const auto [ptr, ec] = std::from_chars(s.data(), s.data() + s.size(), v);
    if (ec != std::errc() || ptr != s.data() + s.size()) return false;
    out = v;
    return true;
}

// Parse exactly `count` numbers from "[a,b,c]", "a,b,c" or "a b c".
inline bool ParseDoubleList(std::string_view s, double* out, int count) {
    s = Trim(s);
    if (!s.empty() && s.front() == '[') {
        if (s.back() != ']') return false;
        s = Trim(s.substr(1, s.size() - 2));
    }
    const bool commaSeparated = s.find(',') != std::string_view::npos;
    for (int i = 0; i < count; ++i) {
        s = Trim(s);
        size_t end = commaSeparated ? s.find(',') : s.find_first_of(" \t");
        if (i == count - 1) {
            if (end != std::string_view::npos) return false;  // too many values
            end = s.size();
        } else if (end == std::string_view::npos) {
            return false;  // too few values
        }
        if (!ParseDouble(s.substr(0, end), out[i])) return false;
        s = (end < s.size()) ? s.substr(end + 1) : std::string_view{};
    }
    return true;
}

// Parse MAXScript colour syntax "(color r g b)", "(color r g b a)",
// "color r g b" (0-255 components). Writes 3 or 4 values; `count` reports which.
inline bool ParseMaxColor(std::string_view s, double* out, int& count) {
    s = Trim(s);
    if (!s.empty() && s.front() == '(') {
        if (s.back() != ')') return false;
        s = Trim(s.substr(1, s.size() - 2));
    }
    constexpr std::string_view kw = "color";
    if (s.size() <= kw.size() || s.substr(0, kw.size()) != kw) return false;
    s = Trim(s.substr(kw.size()));
    if (ParseDoubleList(s, out, 4)) { count = 4; return true; }
    if (ParseDoubleList(s, out, 3)) { count = 3; return true; }
    return false;
}

// Shortest text that round-trips the value, always with '.' and never ','.
inline std::string FormatDouble(double v) {
    if (std::isnan(v)) return "0";  // MAXScript has no NaN literal
    if (std::isinf(v)) return v > 0 ? "1e38" : "-1e38";
    char buf[64];
    const auto [ptr, ec] = std::to_chars(buf, buf + sizeof(buf), v);
    if (ec != std::errc()) return "0";
    return std::string(buf, ptr);
}

inline std::string FormatFloat(float v) {
    if (std::isnan(v)) return "0";
    if (std::isinf(v)) return v > 0 ? "1e38" : "-1e38";
    char buf[48];
    const auto [ptr, ec] = std::to_chars(buf, buf + sizeof(buf), v);
    if (ec != std::errc()) return "0";
    return std::string(buf, ptr);
}

// "[x,y,z]" / "[x,y,z,w]" with invariant formatting.
inline std::string FormatList(const float* v, int count) {
    std::string out = "[";
    for (int i = 0; i < count; ++i) {
        if (i) out += ',';
        out += FormatFloat(v[i]);
    }
    out += ']';
    return out;
}

// "(color r g b)" with 0-255 components from 0-1 inputs when `scale255`.
inline std::string FormatMaxColor(float r, float g, float b, bool scale255) {
    const float k = scale255 ? 255.0f : 1.0f;
    return "(color " + FormatFloat(r * k) + " " + FormatFloat(g * k) + " " + FormatFloat(b * k) + ")";
}

}  // namespace number_text
}  // namespace mcp_bridge
