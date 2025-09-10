#!/bin/bash
#
# usage: ./run.sh command [argument ...]
#
# Executable documentation for the development workflow.
#
# See https://death.andgravity.com/run-sh for how this works.


# preamble

set -o nounset
set -o pipefail
set -o errexit

PROJECT_ROOT=${0%/*}
if [[ $0 != $PROJECT_ROOT && $PROJECT_ROOT != "" ]]; then
    cd "$PROJECT_ROOT"
fi
readonly PROJECT_ROOT=$( pwd )
readonly SCRIPT="$PROJECT_ROOT/$( basename "$0" )"


# main development workflow

function install {
    pip install -e . --group dev --upgrade --upgrade-strategy eager
    pre-commit install --install-hooks
}

function test {
    pytest "$@"
}

function test-all {
    tox p "$@"
}

function coverage {
    unset -f coverage
    coverage run -m pytest "$@"
    coverage html
    coverage report
}

function typing {
    mypy "$@"
}


# "watch" versions of the main commands

function test-dev {
    watch test "$@"
}

function typing-dev {
    watch typing "$@"
}


# utilities

function watch {
    entr-project-files -cdr "$SCRIPT" "$@"
}

function entr-project-files {
    set +o errexit
    while true; do
        ls-project-files | entr "$@"
        if [[ $? -eq 0 ]]; then
            break
        fi
    done
}

function ls-project-files {
    git ls-files "$@"
    git ls-files --exclude-standard --others "$@"
}


"$@"
