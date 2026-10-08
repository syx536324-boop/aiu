// Public configuration contract for the native ONNX Runtime benchmark.
#pragma once

#include <filesystem>

struct BenchmarkOptions {
    std::filesystem::path runtime_dll;
    std::filesystem::path model;
    std::filesystem::path input_directory;
    std::filesystem::path output_directory;
    int iterations = 80;
    int warmups = 12;
    int threads = 4;
};

void run_native_benchmark(const BenchmarkOptions& options);
