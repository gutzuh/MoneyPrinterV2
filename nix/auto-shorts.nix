{ config, lib, pkgs, ... }:
let cfg = config.services.auto-shorts;
in {
  options.services.auto-shorts = {
    enable = lib.mkEnableOption "automatic YouTube Shorts";
    user = lib.mkOption { type = lib.types.str; };
    projectDir = lib.mkOption { type = lib.types.str; };
    times = lib.mkOption { type = lib.types.listOf lib.types.str; default = [ "11:30" "18:30" ]; };
  };
  config = lib.mkIf cfg.enable {
    systemd.services.auto-shorts = {
      description = "Generate and upload one original YouTube Short";
      serviceConfig = { Type = "oneshot"; User = cfg.user; WorkingDirectory = cfg.projectDir; };
      path = [ pkgs.bash pkgs.ffmpeg-full pkgs.python312 pkgs.fontconfig pkgs.dejavu_fonts ];
      script = ''
        set -eu
        source ${cfg.projectDir}/.env
        source ${cfg.projectDir}/venv/bin/activate
        python scripts/auto_short.py --upload
      '';
      environment.LD_LIBRARY_PATH = lib.makeLibraryPath [ pkgs.gcc.cc.lib pkgs.zlib ];
    };
    systemd.timers.auto-shorts = {
      wantedBy = [ "timers.target" ];
      timerConfig = { OnCalendar = map (time: "*-*-* ${time}:00") cfg.times; Persistent = true; RandomizedDelaySec = "8m"; };
    };
  };
}
