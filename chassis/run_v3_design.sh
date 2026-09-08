#!/bin/bash
# Lance la conception ₿ BalanceBot v3 avec Claude Code sur claude-fable-5-1 (clé API).
# La clé est lue depuis ~/.hermes/.env dans l'environnement du process — jamais en argument.
set -u
export ANTHROPIC_API_KEY="$(grep -E '^ANTHROPIC_API_KEY=' "$HOME/.hermes/.env" | cut -d= -f2-)"
export CLAUDE_CODE_MAX_OUTPUT_TOKENS=96000
mkdir -p "$HOME/balance-bot/chassis/v3"
cd "$HOME/balance-bot/chassis" || exit 1
claude -p "$(cat /tmp/bitcoin-bot-brief.md)" \
  --model claude-fable-5-1 \
  --add-dir /home/silex/.hermes/skills/creative/3d-printing \
  --allowedTools "Read,Edit,Write,Bash(blender*),Bash(python*),Bash(ls*),Bash(grep*),Bash(cat*),Bash(head*),Bash(tail*),Bash(mkdir*),Bash(cp*),Bash(echo*),Bash(chmod*),Bash(wc*)" \
  --disallowedTools "Bash(sudo*),Bash(curl*),Bash(git*),Bash(systemctl*),Bash(rm*),Bash(mv*)" \
  --max-turns 200 \
  --output-format json > /tmp/claude-bitcoin-bot.json 2>/tmp/claude-bitcoin-bot.err
echo "EXIT: $?" >> /tmp/claude-bitcoin-bot.json
