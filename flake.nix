{
  description = "MoneyPrinterV2 development environment";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in {
      devShells = forAllSystems (system:
        let pkgs = import nixpkgs { inherit system; };
        in {
          default = pkgs.mkShell {
            packages = with pkgs; [ python312 ffmpeg-full imagemagick git stdenv.cc.cc zlib dejavu_fonts ];
            shellHook = ''
              export PYTHONNOUSERSITE=1
              export LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath [ pkgs.stdenv.cc.cc pkgs.zlib ]}''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
              echo "MoneyPrinterV2: Python $(python --version 2>&1), FFmpeg disponível"
            '';
          };
        });
    };
}
