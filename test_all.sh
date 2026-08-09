#!/bin/bash

set -euo pipefail

# Run the fast dependency audit before the longer frontend, backend, and Docker
# gates so known advisories fail immediately instead of after a full test run.
./test_security.sh --full && ./test_frontend.sh && ./test_backend.sh --full && ./test_docker.sh
