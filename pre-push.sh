#!/usr/bin/env bash
set -euxo pipefail

make check
make test
make fmt
