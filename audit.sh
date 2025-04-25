#!/bin/bash

set -euxo pipefail

hatch fmt
hatch run dev:check
hatch run dev:test
