# Canal automático no NixOS

O modo automático coleta um fato da Wikipédia/Wikimedia, cria roteiro original
com Groq, voz, arte vertical, legendas, metadata e upload. Ele mantém um histórico
dos últimos assuntos para evitar repetição.

## Teste manual

```bash
nix develop
source venv/bin/activate
python scripts/auto_short.py
python scripts/auto_short.py --category tecnologia
python scripts/auto_short.py --upload
```

Use `youtube_privacy: private` durante os primeiros testes. O arquivo `.env` deve
conter `export GROQ_API_KEY='...'` e ter permissão `chmod 600 .env`.

## Timer NixOS

Importe `nix/auto-shorts.nix` na configuração do NixOS e adicione:

```nix
services.auto-shorts = {
  enable = true;
  user = "miguel";
  projectDir = "/home/miguel/Projects/MoneyPrinterV2";
  times = [ "11:30" "18:30" ];
};
```

Depois rode `sudo nixos-rebuild switch`. Consulte com:

```bash
systemctl list-timers auto-shorts.timer
journalctl -u auto-shorts.service -n 100
sudo systemctl start auto-shorts.service
```

Projetos YouTube API não auditados podem ter uploads forçados para privado pelo
Google. Só mude para `public` depois de revisar resultados e confirmar o status
do projeto no Google Cloud.
