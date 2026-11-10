{
  description = "Pyhydronic -- heat flow and Fanger's comfort equation; CPython 2.7 / 3.x dev shells";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";

  outputs = { self, nixpkgs }:
    let
      forAllSystems = nixpkgs.lib.genAttrs [
        "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin"
      ];
    in {
      #
      # devShells.<system>.{default,py314,py313,py312,py311,py27}
      #
      #     nix develop                    # default (CPython 3.13)
      #     nix develop .#py27             # CPython 2.7
      #     make TARGET=py312 nix-test     # see the Makefile's nix-% target
      #
      devShells = forAllSystems (system:
        let
          pkgs = import nixpkgs {
            inherit system;
            config.permittedInsecurePackages = [   # Python 2.7 is long past EOL
              "python-2.7.18.12"
              "python-2.7.18.12-env"
            ];
          };

          commonInputs = with pkgs; [
            cacert
            git                # Also used by the py27 shellHook, to find the repo root
            gnumake
            openssh
            bash
            which
          ];

          # Pyhydronic has no runtime dependencies; Nix provides only the build/test tooling.
          py3 = python: python.withPackages (ps: with ps; [
            pip
            setuptools
            wheel
            build              # make build
            pytest             # make test
            flake8             # make analyze
          ]);

          py3Shell = python: pkgs.mkShell {
            packages = [ (py3 python) ] ++ commonInputs;
            shellHook = ''
              # Resolve modules only through this interpreter's Nix site-packages (or a venv's)
              unset PYTHONPATH
              export PY=python3
              echo "pyhydronic: python3 $(python3 --version 2>&1 | cut -d' ' -f2)  $(which python3)"
            '';
          };

          # Python 2.7 with pip/setuptools only.  nixpkgs' python2 virtualenv has unresolvable
          # dependencies, so bootstrap it via pip into the repo; 'make venv' then uses it (via
          # PYTHONPATH) to create a virtualenv, where pip installs pytest.
          py2 = pkgs.python27.withPackages (ps: with ps; [
            pip
            setuptools
          ]);

          py27Shell = pkgs.mkShell {
            packages = [ py2 ] ++ commonInputs;
            shellHook = ''
              unset PYTHONPATH
              export PY=python2
              export VENV_MOD=virtualenv
              export PYTHONPATH_PY2_VIRTUALENV_BOOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)/.nix-py2-bootstrap"
              if [ ! -f "$PYTHONPATH_PY2_VIRTUALENV_BOOT/bin/virtualenv" ]; then
                echo "Bootstrapping virtualenv for python2.7..."
                python2 -m pip install --quiet --target="$PYTHONPATH_PY2_VIRTUALENV_BOOT" virtualenv
              fi
              echo "pyhydronic: python2 $(python2 --version 2>&1 | cut -d' ' -f2)  $(which python2)"
            '';
          };

        in {
          default = py3Shell pkgs.python313;

          py314   = py3Shell pkgs.python314;
          py313   = py3Shell pkgs.python313;
          py312   = py3Shell pkgs.python312;
          py311   = py3Shell pkgs.python311;

          py27    = py27Shell;
        }
      );
    };
}
