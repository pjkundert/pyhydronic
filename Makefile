#
# GNU 'make' file for pyhydronic
#
#     make help                         # Targets
#     make test                         # Test with $(PY) (default: python3)
#     make nix-test                     # ... in the flake.nix default devShell
#     make TARGET=py27 nix-venv-test    # ... in a CPython 2.7 virtualenv
#

SHELL		= /bin/bash

# PY is the target Python interpreter.  The flake.nix devShells export PY (python3 or python2) and,
# for py27, VENV_MOD=virtualenv (Python 2 has no stdlib venv module).
PY		?= python3
PY_V		= $(shell $(PY) -c "import sys; print('-'.join((next(iter(filter(None,sys.executable.split('/')))),sys.platform,getattr(sys,'implementation',None) and sys.implementation.cache_tag or 'cpython-{}{}'.format(*sys.version_info[:2]))))" 2>/dev/null )
PY_MAJOR	= $(shell $(PY) -c "import sys; print(sys.version_info[0])" 2>/dev/null )
VENV_MOD	?= venv

VERSION		= $(shell $(PY) -c 'exec(open("hydronic/version.py").read()); print( __version__ )')
WHEEL		= dist/pyhydronic-$(VERSION)-py2.py3-none-any.whl

# TARGET=... selects the flake.nix devShell: py27, py3{11,12,13,14}; default: latest stable CPython 3
export TARGET
NIX_OPTS	?= # eg. -i (--ignore-environment, ie. a "pure" shell)

# Virtual envs are created next to (not in) this repo: ../pyhydronic-<version>-<interpreter>
VENV_DIR	= $(abspath $(dir $(abspath $(lastword $(MAKEFILE_LIST))))/.. )
VENV		= $(VENV_DIR)/pyhydronic-$(VERSION)-$(PY_V)

PYTEST_OPTS	?= -v
PYTEST		= $(PY) -m pytest $(PYTEST_OPTS)

.PHONY: all help test analyze examples build wheel install venv clean FORCE
all:		help

help:
	@echo "pyhydronic $(VERSION) targets ($(PY) == $(PY_V)):"
	@echo "  test			Run unit tests (and examples) under $(PY)"
	@echo "  unit-<pattern>		Run unit tests matching <pattern>"
	@echo "  analyze		Lint with flake8"
	@echo "  examples		Run the examples"
	@echo "  build			Build the sdist and $(WHEEL)"
	@echo "  install		Install the wheel into the current $(PY) environment"
	@echo "  venv			Create $(VENV), and start an interactive shell in it"
	@echo "  venv-<target>		Run 'make <target>' in the venv"
	@echo "  nix-<target>		Run 'make <target>' in the flake.nix devShell (TARGET=py27, py312, ...)"
	@echo "  clean			Remove build artifacts"
	@echo
	@echo "EXAMPLES"
	@echo "  make nix-test			# Test under the default CPython 3"
	@echo "  make TARGET=py27 nix-venv-test	# Test under CPython 2.7, in a virtualenv"
	@echo "  make nix-build			# Build the sdist and wheel"

test:
	$(PYTEST) tests

unit-%:
	$(PYTEST) -k $* tests

analyze:
	$(PY) -m flake8 hydronic tests examples

examples:
	PYTHONPATH=$(CURDIR) $(PY) examples/comfort_lines.py
	PYTHONPATH=$(CURDIR) $(PY) examples/radiant_room.py --mode air
	PYTHONPATH=$(CURDIR) $(PY) examples/radiant_room.py --mode comfort

#
# build:	Build the sdist and the universal (py2.py3) wheel.  Requires Python 3.  Releases are
#		built and published to PyPI by .github/workflows/release.yml, on pushing a vX.Y.Z tag.
#
build:		clean wheel

wheel:		$(WHEEL)

$(WHEEL):	FORCE
	$(PY) -m build .
	@ls -l dist

install:	$(WHEEL)
	$(PY) -m pip install --force-reinstall $<

#
# venv:		Create a virtual env (and start an interactive shell in it), eg. under Nix:
#
#     make nix-venv                     # CPython 3, w/ pyhydronic installed in editable mode
#     make TARGET=py27 nix-venv         # CPython 2.7; tests run from this source tree
#
venv:		$(VENV)
	@echo; echo "*** Activating $< VirtualEnv for Interactive $(SHELL)"
	@bash --init-file $</bin/activate -i

venv-%:		$(VENV)
	source $</bin/activate && $(MAKE) $*

$(VENV):
	@echo; echo "*** Building $@ VirtualEnv..."
	rm -rf $@
	PYTHONPATH=$(PYTHONPATH_PY2_VIRTUALENV_BOOT) $(PY) -m $(VENV_MOD) $@
	source $@/bin/activate && if [ "$(PY_MAJOR)" = 2 ]; then \
	    python -m pip install "pytest < 5" "flake8 < 4"; \
	else \
	    python -m pip install -e ".[tests,dev]"; \
	fi

#
# nix-...:	Run a make target in a Nix flake devShell, eg. make TARGET=py312 nix-test
#
nix-%:
	nix develop .#$(or $(TARGET),default) $(NIX_OPTS) --command $(MAKE) $*

clean:
	rm -rf build dist *.egg-info .pytest_cache
	find . \( -name '__pycache__' -o -name '*.pyc' \) -prune -exec rm -rf {} +

print-%:
	@echo $* = $($*)
	@echo $*\'s origin is $(origin $*)

FORCE:
