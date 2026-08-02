#!/bin/sh
# Report a non-mutating Compose volume plan for a Bambuddy-derived deployment.
# It never creates, changes, deletes, or inspects application data contents.
set -eu

docker_bin="${DOCKER_BIN:-docker}"
legacy_data="${LEGACY_DATA_VOLUME:-bambuddy_data}"
legacy_logs="${LEGACY_LOGS_VOLUME:-bambuddy_logs}"
new_data="${GOO_BUDDY_DATA_VOLUME:-goo_buddy_data}"
new_logs="${GOO_BUDDY_LOGS_VOLUME:-goo_buddy_logs}"

exists() {
    "$docker_bin" volume inspect "$1" >/dev/null 2>&1
}

legacy_data_exists=0
legacy_logs_exists=0
new_data_exists=0
new_logs_exists=0
exists "$legacy_data" && legacy_data_exists=1
exists "$legacy_logs" && legacy_logs_exists=1
exists "$new_data" && new_data_exists=1
exists "$new_logs" && new_logs_exists=1

if [ "$legacy_data_exists" -ne "$legacy_logs_exists" ]; then
    echo "ambiguous legacy layout: expected both legacy volumes or neither" >&2
    exit 2
fi
if { [ "$legacy_data_exists" -eq 1 ] || [ "$legacy_logs_exists" -eq 1 ]; } && \
   { [ "$new_data_exists" -eq 1 ] || [ "$new_logs_exists" -eq 1 ]; }; then
    echo "ambiguous layout: both legacy and Goo Buddy volume names exist" >&2
    exit 2
fi

if [ "$legacy_data_exists" -eq 1 ]; then
    cat <<EOF
Legacy volumes detected. Reuse them without renaming or copying data:
GOO_BUDDY_DATA_VOLUME=$legacy_data
GOO_BUDDY_LOGS_VOLUME=$legacy_logs
EOF
else
    cat <<EOF
No complete legacy volume pair detected. Use the fresh-install defaults:
GOO_BUDDY_DATA_VOLUME=$new_data
GOO_BUDDY_LOGS_VOLUME=$new_logs
EOF
fi
