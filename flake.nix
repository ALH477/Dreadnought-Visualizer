{
  description = "Dreadnought Visualizer – Warhammer 40k JACK Audio Oscilloscope";

  inputs = {
    nixpkgs.url     = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};

        # ── Native runtime libs ─────────────────────────────────────────────
        nativeLibs = with pkgs; [
          jack2
          SDL2
          SDL2_image
          SDL2_mixer
          SDL2_ttf
          libGL
          wayland
          mesa
        ];

        # PipeWire ships a libjack.so drop-in at a non-standard path.
        # Prepending it means the app connects through PipeWire's JACK
        # compatibility layer (what qjackctl uses on modern NixOS) rather
        # than looking for a bare jackd socket.
	pipewireJackLib = "${pkgs.pipewire.jack}/lib";
        # ── JACK-Client Python binding ──────────────────────────────────────
        # Not packaged in nixpkgs directly. Pure-Python cffi wrapper;
        # libjack is resolved at runtime via LD_LIBRARY_PATH.
        jackClientPy = pkgs.python312Packages.buildPythonPackage rec {
          pname   = "JACK-Client";
          version = "0.5.4";
          format  = "pyproject";

          src = pkgs.fetchPypi {
            inherit pname version;
            hash = "sha256-3UopPjpum96Zclabm8RjCl/NT4B1bMWQ3lcsx0TlqEg=";
          };

          build-system = with pkgs.python312Packages; [ setuptools ];
          dependencies  = with pkgs.python312Packages; [ cffi ];

          doCheck = false;  # tests require a running JACK daemon
        };

        # ── Python environment ──────────────────────────────────────────────
        pythonEnv = pkgs.python312.withPackages (ps: [
          ps.pygame
          ps.pyopengl
          ps.numpy
          jackClientPy
        ]);

        # Full LD_LIBRARY_PATH: PipeWire's libjack *first* so it wins over
        # jack2's when PipeWire is the sound server, then the rest.
        ldPath = pkgs.lib.concatStringsSep ":" [
          pipewireJackLib
          (pkgs.lib.makeLibraryPath nativeLibs)
        ];

        # ── Application derivation ──────────────────────────────────────────
        app = pkgs.stdenv.mkDerivation {
          pname   = "dreadnought-viz";
          version = "1.3.0";

          src = ./.;

          nativeBuildInputs = [ pkgs.makeWrapper ];
          buildInputs       = [ pythonEnv ] ++ nativeLibs;

          dontConfigure = true;
          dontBuild     = true;

          installPhase = ''
            mkdir -p $out/bin
            cp dreadnought_visualizer.py $out/bin/dreadnought-viz
            chmod +x $out/bin/dreadnought-viz

            substituteInPlace $out/bin/dreadnought-viz \
              --replace "#!/usr/bin/env python3" "#!${pythonEnv}/bin/python3"

            wrapProgram $out/bin/dreadnought-viz \
              --prefix LD_LIBRARY_PATH : "${ldPath}"
          '';

          meta = with pkgs.lib; {
            description = "Warhammer 40k Sarcophagus-style JACK Audio Oscilloscope";
            license     = licenses.mit;
            platforms   = platforms.linux;
            mainProgram = "dreadnought-viz";
          };
        };

      in {
        packages.default = app;

        apps.default = flake-utils.lib.mkApp {
          drv     = app;
          exePath = "/bin/dreadnought-viz";
        };

        devShells.default = pkgs.mkShell {
          packages = [
            pythonEnv
            pkgs.jack2
            pkgs.qjackctl
            pkgs.pipewire
          ];

          LD_LIBRARY_PATH = ldPath;

          shellHook = ''
            echo "╔════════════════════════════════════════════════════╗"
            echo "║      DREADNOUGHT DEV SHELL ACTIVATED               ║"
            echo "║                                                    ║"
            echo "║  Run:  python dreadnought_visualizer.py            ║"
            echo "║  Nix:  nix run .                                   ║"
            echo "║                                                    ║"
            echo "║  JACK: qjackctl → mic → dreadnought-viz            ║"
            echo "║                                                    ║"
            echo "║  For the Emperor! ⚔️                               ║"
            echo "╚════════════════════════════════════════════════════╝"
          '';
        };
      }
    );
}
