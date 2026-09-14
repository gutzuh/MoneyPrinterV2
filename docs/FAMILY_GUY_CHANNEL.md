# Canal narrado de Family Guy no NixOS

Este fluxo cria um Short vertical a partir de um **arquivo local que você tem
direito de reutilizar**. Ele não remove DRM e não baixa episódios de fontes não
autorizadas.

## 1. Preparar o ambiente

```bash
git clone https://github.com/gutzuh/MoneyPrinterV2.git
cd MoneyPrinterV2
nix develop
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
python scripts/preflight_shorts.py
```

Crie uma chave em <https://console.groq.com/keys> e carregue-a somente na sessão:

```bash
export GROQ_API_KEY='COLE_SUA_CHAVE_AQUI'
```

A voz padrão é `pt-BR-AntonioNeural`. Para voz feminina, altere `tts_voice` no
`config.json` para `pt-BR-FranciscaNeural`.

## 2. Gerar o primeiro vídeo

Coloque um arquivo autorizado em `input/` e execute:

```bash
mkdir -p input
python scripts/family_guy_short.py input/video.mp4
```

O resultado fica em `.mp/shorts/`. Assista e revise antes de enviar.

Para colocar vários arquivos na fila e gerar um por execução:

```bash
python scripts/process_short_queue.py
```

Depois de autorizar o YouTube, processe e envie como privado:

```bash
python scripts/process_short_queue.py --upload
```

Arquivos concluídos vão para `input/processed/`; erros vão para `input/failed/`.
Isso permite chamar o comando por um timer do systemd sem repetir o mesmo vídeo.

## 3. Autorizar o canal do YouTube

1. Abra <https://console.cloud.google.com/>.
2. Crie um projeto.
3. Ative **YouTube Data API v3**.
4. Configure a tela de consentimento OAuth como **External** e adicione seu
   e-mail como usuário de teste.
5. Crie uma credencial **OAuth client ID > Desktop app**.
6. Baixe o JSON, renomeie para `client_secret.json` e coloque na raiz do projeto.
7. Execute `python scripts/auth_youtube.py` e autorize o canal correto no navegador.

O segredo e o token estão ignorados pelo Git e não devem ser publicados.

Para renderizar e enviar como privado:

```bash
python scripts/family_guy_short.py input/video.mp4 --upload
```

Para agendar, informe data/hora em UTC:

```bash
python scripts/family_guy_short.py input/video.mp4 \
  --upload --publish-at 2026-09-15T21:00:00Z
```

## Fontes oficiais

- Página oficial da série na FOX: <https://www.fox.com/family-guy/>
- Catálogo oficial Disney+: <https://www.disneyplus.com/>
- Canal oficial Family Guy no YouTube: <https://www.youtube.com/@FamilyGuyFOX>

Assinar um streaming permite assistir, mas não concede automaticamente licença
para republicar. Para uma operação comercial estável, solicite autorização ao
detentor ou trabalhe com material promocional cuja licença permita reutilização.
