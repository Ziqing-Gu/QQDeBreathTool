// Limit denormal suppression to the calling analysis thread and restore its state.
#include <immintrin.h>
#include <cstdint>
#if defined(_WIN32)
#define QQ_EXPORT extern "C" __declspec(dllexport)
#else
#define QQ_EXPORT extern "C" __attribute__((visibility("default")))
#endif
QQ_EXPORT std::uint32_t qq_fp_get() { return _mm_getcsr(); }
QQ_EXPORT std::uint32_t qq_fp_enter()
{
    const auto previous = _mm_getcsr();
    _mm_setcsr(previous | (1u << 15) | (1u << 6)); // FTZ and DAZ; x64 SSE2.
    return previous;
}
QQ_EXPORT void qq_fp_restore(std::uint32_t previous) { _mm_setcsr(previous); }
