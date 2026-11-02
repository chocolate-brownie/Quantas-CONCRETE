#!/usr/bin/env bash
# Check that this cluster node can build and run Concrete ZeroMQ. Changes nothing.
# Run inside an interactive job, from the repository root.

fail=0

echo "node: $(hostname)  folder: $(pwd)"
echo "open files limit: $(ulimit -n)  (20 peers need about 40 each)"

for tool in g++ make python3 oarsh; do
	if command -v "$tool" >/dev/null; then
		echo "ok: $tool ($("$tool" --version 2>&1 | head -1))"
	else
		echo "MISSING: $tool"
		fail=1
	fi
done

test_dir=$(mktemp -d)
trap 'rm -rf -- "$test_dir"' EXIT
cat >"$test_dir/check.cpp" <<'EOF'
#include <boost/archive/binary_oarchive.hpp>
#include <optional>
#include <sstream>
#include <zmq.hpp>
int main() {
    zmq::context_t context;
    std::stringstream stream;
    boost::archive::binary_oarchive archive(stream);
    return 0;
}
EOF
if g++ -std=c++17 "$test_dir/check.cpp" -o "$test_dir/check" -lboost_serialization -lzmq -lrt &&
	"$test_dir/check"; then
	echo "ok: C++17, Boost and ZeroMQ (with zmq.hpp) compile and run"
else
	echo "MISSING: see the compiler error above (g++ C++17, Boost serialization, libzmq or cppzmq)"
	fail=1
fi

exit "$fail"
