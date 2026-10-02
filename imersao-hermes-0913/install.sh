#!/usr/bin/env bash
set -euo pipefail

KIT_URL="https://hlreboques-oss.github.io/projeto-sites-demos/imersao-hermes-0913/imersao-hermes-0913.tar.gz"

printf '\n=== Instalador Hermes VPS - Imersao ===\n\n'

if [ "$(id -u)" -eq 0 ]; then
  HOME_DIR="/root"
else
  HOME_DIR="$HOME"
fi

printf 'Home detectado: %s\n' "$HOME_DIR"

if command -v apt-get >/dev/null 2>&1; then
  printf '\n1/6 Instalando dependencias basicas...\n'
  sudo apt-get update -y
  sudo apt-get install -y curl git ca-certificates python3 python3-pip ffmpeg tmux unzip nano tar
else
  printf 'apt-get nao encontrado. Continuando mesmo assim.\n'
fi

printf '\n2/6 Instalando Hermes Agent...\n'
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash

export PATH="$HOME_DIR/.local/bin:$HOME_DIR/.cargo/bin:$PATH"

printf '\n3/6 Criando pastas...\n'
mkdir -p "$HOME_DIR/imersao-hermes" "$HOME_DIR/projetos" "$HOME_DIR/crm" "$HOME_DIR/midia" "$HOME_DIR/relatorios"

printf '\n4/6 Baixando kit da imersao...\n'
TMP_TAR="/tmp/imersao-hermes-0913.tar.gz"
if curl -fsSL "$KIT_URL" -o "$TMP_TAR"; then
  tar -xzf "$TMP_TAR" -C /tmp
  cp -r /tmp/imersao-hermes-0913/* "$HOME_DIR/imersao-hermes/" || true
  cp -r /tmp/imersao-hermes-0913/.[!.]* "$HOME_DIR/imersao-hermes/" 2>/dev/null || true
  printf 'Kit copiado para %s/imersao-hermes\n' "$HOME_DIR"
else
  printf 'Nao consegui baixar o kit automaticamente. Voce pode copiar manualmente depois.\n'
fi

printf '\n5/6 Verificando Hermes...\n'
if command -v hermes >/dev/null 2>&1; then
  hermes --version || true
else
  printf 'Hermes ainda nao apareceu no PATH desta sessao. Rode:\n'
  printf 'export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"\n'
fi

cat > "$HOME_DIR/imersao-hermes/PROXIMOS_PASSOS.txt" <<'TXT'
PROXIMOS PASSOS

1. Configurar modelo/portal:
   hermes setup --portal

2. Testar no terminal:
   hermes

3. Criar bot no Telegram com @BotFather e pegar token.

4. Pegar Telegram user ID com @userinfobot.

5. Configurar Telegram:
   hermes gateway setup

6. Testar:
   hermes gateway

7. Se respondeu no Telegram, deixar permanente:
   hermes gateway install
   hermes gateway start
   hermes gateway status

8. Pedir ao agente:
   Leia todos os arquivos da pasta ~/imersao-hermes, começando por ~/imersao-hermes/01_BASE_DO_AGENTE_HERMES.md. Use isso como base operacional.
TXT

printf '\n6/6 Base instalada.\n\n'
printf 'Agora rode:\n'
printf '  hermes setup --portal\n\n'
printf 'Depois configure Telegram:\n'
printf '  hermes gateway setup\n\n'
printf 'Guia local: %s/imersao-hermes/PROXIMOS_PASSOS.txt\n' "$HOME_DIR"
