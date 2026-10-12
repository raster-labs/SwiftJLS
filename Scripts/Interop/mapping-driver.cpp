// SPDX-License-Identifier: Apache-2.0
// Test-only adapter. CharLS is an isolated BSD-3-Clause oracle.
#include <charls/jpegls_encoder.hpp>
#include <charls/jpegls_decoder.hpp>
#include <fstream>
#include <iostream>
#include <iterator>
#include <vector>
static std::vector<uint8_t> read(const char* p) {
    std::ifstream f(p, std::ios::binary); if (!f) throw std::runtime_error("input");
    return {std::istreambuf_iterator<char>(f), {}};
}
static void write(const std::string& p, const std::vector<uint8_t>& b) {
    std::ofstream f(p, std::ios::binary); f.write(reinterpret_cast<const char*>(b.data()), b.size());
    if (!f) throw std::runtime_error("output");
}
int main(int argc, char** argv) {
    try {
        if (argc == 12 && std::string(argv[1]) == "encode") {
            const int bits = std::stoi(argv[4]), count = std::stoi(argv[5]), ilv = std::stoi(argv[6]), wt = std::stoi(argv[7]);
            auto samples = read(argv[9]); auto table = read(argv[10]);
            charls::jpegls_encoder e;
            e.frame_info({static_cast<uint32_t>(std::stoul(argv[2])), static_cast<uint32_t>(std::stoul(argv[3])), bits, count})
                .interleave_mode(static_cast<charls::interleave_mode>(ilv)).near_lossless(std::stoi(argv[8]));
            for (int c = 0; c < count; ++c) e.set_mapping_table_id(c, 7);
            std::vector<uint8_t> bytes(e.estimated_destination_size() + table.size() + 1024);
            e.destination(bytes).write_mapping_table(7, wt, table);
            e.write_comment("mapping oracle");
            bytes.resize(e.encode(samples)); write(argv[11], bytes);
        } else if (argc == 4 && std::string(argv[1]) == "decode") {
            auto source = read(argv[2]); charls::jpegls_decoder d{source, true};
            std::vector<uint8_t> samples(d.get_destination_size()); d.decode(samples); write(argv[3], samples);
            for (int i = 0; i < d.mapping_table_count(); ++i) {
                auto info = d.get_mapping_table_info(i);
                std::vector<uint8_t> table(info.data_size); d.get_mapping_table_data(i, table);
                write(std::string(argv[3]) + ".table" + std::to_string(info.table_id), table);
            }
            auto f = d.frame_info(); std::cout << f.width << " " << f.height << " " << f.bits_per_sample << " " << d.mapping_table_count() << "\n";
        } else throw std::runtime_error("encode W H BITS COMPONENTS ILV WT NEAR RAW TABLE JLS | decode JLS RAW");
        return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << "\n"; return 1; }
}
