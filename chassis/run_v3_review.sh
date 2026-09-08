#!/bin/bash
# Review v3 par Claude Code (auth OAuth Pro — pas de clé API)
export CLAUDE_CODE_MAX_OUTPUT_TOKENS=96000
cd ~/balance-bot/chassis
env -u ANTHROPIC_API_KEY claude -p "$(cat /tmp/v3-review-brief.md)" --model opus \
  --allowedTools "Read,Edit,Bash(ls*),Bash(grep*),Bash(cat*),Bash(head*),Bash(tail*)" \
  --disallowedTools "Bash(sudo*),Bash(curl*),Bash(git*),Bash(rm*),Bash(mv*),Bash(python*),Bash(blender*),Bash(systemctl*),Write" \
  --max-turns 30 --output-format json > /tmp/claude-v3review.json 2>/tmp/claude-v3review.err
echo "EXIT: $?" >> /tmp/claude-v3review.json
