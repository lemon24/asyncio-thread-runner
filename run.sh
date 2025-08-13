#!/bin/bash
#
# usage: ./run.sh command [argument ...]
#
# See https://death.andgravity.com/run-sh for how this works.

set -o nounset
set -o pipefail
set -o errexit

PROJECT_ROOT=${0%/*}
if [[ $0 != $PROJECT_ROOT && $PROJECT_ROOT != "" ]]; then
    cd "$PROJECT_ROOT"
fi
readonly PROJECT_ROOT=$( pwd )
readonly SCRIPT="$PROJECT_ROOT/$( basename "$0" )"


function install-dev {
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

function coverage-run {
    command coverage run "$@" -m pytest -v
}

function coverage-report {
    [[ -z ${CI+x} ]] && command coverage html
    command coverage report --skip-covered --show-missing --fail-under 100
}


function typing {
    if on-pypy; then
        echo "mypy does not work on pypy, doing nothing"
        return
    fi
    mypy "$@"
}


function on-pypy {
    [[ $( python -c 'import sys; print(sys.implementation.name)' ) == pypy ]]
}

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

function test-dev {
    entr-project-files -cdr "$SCRIPT" test "$@"
}

function typing-dev {
    entr-project-files -cdr "$SCRIPT" typing "$@"
}


"$@"
