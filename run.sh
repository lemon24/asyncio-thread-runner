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
    pip install \
        --editable . \
        --group dev --group tests --group typing \
        --upgrade --upgrade-strategy eager
    pre-commit install --install-hooks
}

function test {
    pytest "$@"
}

function coverage {
    coverage-run
    coverage-report
}

function typing {
    mypy "$@"
}


# "watch" versions of the main commands

function watch {
    entr-project-files -cdr "$SCRIPT" "$@"
}

function test-dev {
    watch test "$@"
}

function typing-dev {
    watch typing "$@"
}


# low level commands

function coverage-run {
    command coverage run "$@" -m pytest -v
}

function coverage-report {
    [[ -z ${CI+x} ]] && command coverage html
    command coverage report --skip-covered --show-missing --fail-under 100
}


# utilities

function ls-project-files {
    git ls-files "$@"
    git ls-files --exclude-standard --others "$@"
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


"$@"
