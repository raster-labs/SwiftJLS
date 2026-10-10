// Test-only adapter, Apache-2.0. CharLS remains a separate BSD-3-Clause oracle.
#include <charls/charls.h>
#include <fstream>
#include <iostream>
#include <iterator>
#include <vector>
static std::vector<unsigned char> read(const char* p) {
    std::ifstream f(p, std::ios::binary);
    if (!f) throw std::runtime_error("Cannot open input");
    return {std::istreambuf_iterator<char>(f), std::istreambuf_iterator<char>()};
}
static void write(const char* p, const std::vector<unsigned char>& b) {
    std::ofstream f(p, std::ios::binary); f.write(reinterpret_cast<const char*>(b.data()), b.size());
    if (!f) throw std::runtime_error("Cannot write output");
}
int main(int argc, char** argv) {
    try {
        if (argc == 8 && std::string(argv[1]) == "encode") {
            auto source = read(argv[6]);
            charls::jpegls_encoder e;
            e.frame_info({static_cast<uint32_t>(std::stoul(argv[2])), static_cast<uint32_t>(std::stoul(argv[3])), std::stoi(argv[4]), 1}).near_lossless(std::stoi(argv[5]));
            std::vector<unsigned char> bytes(e.estimated_destination_size());
            e.destination(bytes); bytes.resize(e.encode(source)); write(argv[7], bytes);
        } else if (argc == 4 && std::string(argv[1]) == "decode") {
            auto source = read(argv[2]);
            charls::jpegls_decoder d{source, true};
            std::vector<unsigned char> bytes(d.destination_size()); d.decode(bytes); write(argv[3], bytes);
            auto f = d.frame_info(); std::cout << f.width << " " << f.height << " " << f.bits_per_sample << " " << d.near_lossless() << "\n";
        } else { throw std::runtime_error("encode WIDTH HEIGHT BITS NEAR RAW JLS | decode JLS RAW"); }
        return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << "\n"; return 1; }
}
