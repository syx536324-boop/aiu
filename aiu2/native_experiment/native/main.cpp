// Composition entry point: parse CLI paths/options and invoke the native runner.
#include "runner.hpp"
#include <exception>
#include <iostream>
#include <stdexcept>
#include <string>

int main(int argc, char** argv) {
    try {
        if (argc != 8) {
            std::cerr << "Usage: yolo_ort_bench runtime.dll model.onnx input_dir output_dir iterations warmups threads\n";
            return 2;
        }
        BenchmarkOptions options;
        options.runtime_dll = argv[1];
        options.model = argv[2];
        options.input_directory = argv[3];
        options.output_directory = argv[4];
        options.iterations = std::stoi(argv[5]);
        options.warmups = std::stoi(argv[6]);
        options.threads = std::stoi(argv[7]);
        if (options.iterations < 1 || options.warmups < 0 || options.threads < 1) {
            throw std::runtime_error("Invalid benchmark counts or thread count");
        }
        run_native_benchmark(options);
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
