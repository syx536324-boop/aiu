// Load the official runtime, execute identical float tensors, and record native timings/results.
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#if defined(__MINGW32__) && !defined(_stdcall)
// The Windows SDK spells ORT_API_CALL as _stdcall; MinGW accepts the attribute spelling.
#define _stdcall __attribute__((__stdcall__))
#endif
#define ORT_API_MANUAL_INIT
#include <onnxruntime_cxx_api.h>
#include "runner.hpp"

#include <algorithm>
#include <chrono>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
struct RuntimeLibrary {
    HMODULE handle;
    explicit RuntimeLibrary(const std::filesystem::path& path) {
        SetDllDirectoryW(path.parent_path().wstring().c_str());
        handle = LoadLibraryW(path.wstring().c_str());
        if (!handle) throw std::runtime_error("Cannot load ONNX Runtime DLL, Windows error " + std::to_string(GetLastError()));
        using GetApiBase = const OrtApiBase* (ORT_API_CALL*)();
        auto entry = reinterpret_cast<GetApiBase>(GetProcAddress(handle, "OrtGetApiBase"));
        if (!entry) throw std::runtime_error("OrtGetApiBase export missing");
        const OrtApi* api = entry()->GetApi(ORT_API_VERSION);
        if (!api) throw std::runtime_error("Runtime/header API mismatch");
        Ort::InitApi(api);
    }
    ~RuntimeLibrary() { if (handle) FreeLibrary(handle); }
};

std::vector<float> read_tensor(const std::filesystem::path& path, size_t expected_count) {
    std::ifstream file(path, std::ios::binary | std::ios::ate);
    if (!file || static_cast<size_t>(file.tellg()) != expected_count * sizeof(float)) {
        throw std::runtime_error("Input tensor has incorrect size: " + path.string());
    }
    std::vector<float> values(expected_count);
    file.seekg(0);
    file.read(reinterpret_cast<char*>(values.data()), static_cast<std::streamsize>(values.size() * sizeof(float)));
    if (!file) throw std::runtime_error("Failed to read input tensor");
    return values;
}

double percentile(std::vector<double> values, double quantile) {
    std::sort(values.begin(), values.end());
    const double index = (values.size() - 1) * quantile;
    const auto lower = static_cast<size_t>(index);
    const auto upper = std::min(lower + 1, values.size() - 1);
    return values[lower] + (values[upper] - values[lower]) * (index - lower);
}
}

void run_native_benchmark(const BenchmarkOptions& options) {
    RuntimeLibrary library(options.runtime_dll);
    Ort::Env environment(ORT_LOGGING_LEVEL_WARNING, "aiu-yolo-benchmark");
    Ort::ThrowOnError(Ort::GetApi().DisableTelemetryEvents(environment));
    Ort::SessionOptions session_options;
    session_options.SetIntraOpNumThreads(options.threads);
    session_options.SetInterOpNumThreads(1);
    session_options.SetExecutionMode(ORT_SEQUENTIAL);
    session_options.SetGraphOptimizationLevel(ORT_ENABLE_ALL);
    session_options.AddConfigEntry("session.intra_op.allow_spinning", "0");
    Ort::Session session(environment, options.model.wstring().c_str(), session_options);
    Ort::AllocatorWithDefaultOptions allocator;
    auto input_name_holder = session.GetInputNameAllocated(0, allocator);
    auto output_name_holder = session.GetOutputNameAllocated(0, allocator);
    const char* input_name = input_name_holder.get();
    const char* output_name = output_name_holder.get();
    const auto shape = session.GetInputTypeInfo(0).GetTensorTypeAndShapeInfo().GetShape();
    if (shape != std::vector<int64_t>{1, 3, 640, 640}) throw std::runtime_error("Expected fixed input shape [1,3,640,640]");
    const size_t input_count = 1 * 3 * 640 * 640;
    std::vector<std::filesystem::path> paths;
    for (const auto& entry : std::filesystem::directory_iterator(options.input_directory)) {
        if (entry.path().extension() == ".bin") paths.push_back(entry.path());
    }
    std::sort(paths.begin(), paths.end());
    if (paths.empty()) throw std::runtime_error("No input tensors found");
    std::vector<std::vector<float>> buffers;
    for (const auto& path : paths) buffers.push_back(read_tensor(path, input_count));
    const auto memory = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
    std::vector<Ort::Value> tensors;
    for (auto& buffer : buffers) {
        tensors.push_back(Ort::Value::CreateTensor<float>(memory, buffer.data(), buffer.size(), shape.data(), shape.size()));
    }
    auto infer = [&](size_t index) {
        return session.Run(Ort::RunOptions{nullptr}, &input_name, &tensors[index], 1, &output_name, 1);
    };
    for (int i = 0; i < options.warmups; ++i) infer(i % tensors.size());
    std::vector<double> samples;
    for (int i = 0; i < options.iterations; ++i) {
        const auto start = std::chrono::steady_clock::now();
        auto output = infer(i % tensors.size());
        const auto stop = std::chrono::steady_clock::now();
        samples.push_back(std::chrono::duration<double, std::milli>(stop - start).count());
    }
    std::filesystem::create_directories(options.output_directory);
    std::vector<int64_t> output_shape;
    for (size_t i = 0; i < tensors.size(); ++i) {
        auto output = infer(i);
        const auto info = output[0].GetTensorTypeAndShapeInfo();
        output_shape = info.GetShape();
        std::ofstream file(options.output_directory / ("cpp_output_" + std::to_string(i) + ".bin"), std::ios::binary);
        file.write(reinterpret_cast<const char*>(output[0].GetTensorData<float>()), static_cast<std::streamsize>(info.GetElementCount() * sizeof(float)));
        if (!file) throw std::runtime_error("Failed to write output tensor");
    }
    const double mean = std::accumulate(samples.begin(), samples.end(), 0.0) / samples.size();
    std::ofstream result(options.output_directory / "cpp_benchmark.json");
    result << std::setprecision(10) << "{\"backend\":\"C++ ONNX Runtime CPU\",\"iterations\":" << options.iterations
           << ",\"warmups\":" << options.warmups << ",\"threads\":" << options.threads
           << ",\"mean_ms\":" << mean << ",\"p50_ms\":" << percentile(samples, 0.5)
           << ",\"p95_ms\":" << percentile(samples, 0.95) << ",\"output_shape\":[";
    for (size_t i = 0; i < output_shape.size(); ++i) result << (i ? "," : "") << output_shape[i];
    result << "]}";
    std::cout << "C++ mean inference latency: " << mean << " ms\n";
}
