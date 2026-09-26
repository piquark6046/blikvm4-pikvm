#!/bin/bash
# Shared verification boundary for historical and clean-release build modes.
RELEASE_LOCK_TOOL=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lock.py
release_verify_file() {
    local expected=$1 path=$2
    if [[ ${BLIKVM_RELEASE_BUILD:-0} == 1 && $path == *'/artifacts/'* ]]; then
        python3 "$RELEASE_LOCK_TOOL" verify "$path"
    else
        printf '%s  %s\n' "$expected" "$path" | sha256sum -c -
    fi
}
release_verify_list() {
    local list=$1
    if [[ ${BLIKVM_RELEASE_BUILD:-0} == 1 ]]; then
        python3 "$RELEASE_LOCK_TOOL" verify-list "$list"
    else
        sha256sum -c "$list"
    fi
}
release_verify_builder() {
    local actual=$1 historical=$2
    if [[ ${BLIKVM_RELEASE_BUILD:-0} != 1 ]]; then
        test "$actual" = "$historical"
    fi
}
