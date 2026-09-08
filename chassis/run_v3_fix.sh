#!/bin/bash
# Finition v3 par Claude Code (clé API lue dans ~/.hermes/.env, jamais en argument)
export CLAUDE_CODE_MAX_OUTPUT_TOKENS=96000
export ANTHROPIC_API_KEY=$(grep -E "^ANTHROPIC_API_KEY=" ~/.hermes/.env | cut -d= -f2-)
cd ~/balance-bot/chassis
claude -p "$(cat /tmp/v3-fix-brief.md)" --model claude-fable-5-1 \
  --allowedTools "Read,Edit,Write,Bash(blender*),Bash(bash*),Bash(ls*),Bash(grep*),Bash(cat*),Bash(head*),Bash(tail*),Bash(cd*),Bash(python3*),Bash(echo*)" \
  --disallowedTools "Bash(sudo*),Bash(curl*),Bash(git*),Bash(rm*),Bash(mv*),Bash(systemctl*),Bash(service*),Bash(chmod*)" \
  --max-turns 60 --output-format json > /tmp/claude-v3fix.json 2>/tmp/claude-v3fix.err
echo "EXIT: $?" >> /tmp/claude-v3fix.json
