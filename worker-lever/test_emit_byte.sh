#!/bin/bash
# Build + run the emit byte-equivalence test.
# Does NOT require mlx or libane — pure C++ stdio behavior test.
set -e

cd "$(dirname "$0")"
g++ -O2 -std=c++17 -o emit_byte_test emit_byte_test.cpp
./emit_byte_test
