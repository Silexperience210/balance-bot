#!/bin/bash
# Implémentation v3.1 par Claude Code (Opus, auth OAuth Pro) — MCP désactivé (blender-mcp bloquait le démarrage)
export CLAUDE_CODE_MAX_OUTPUT_TOKENS=96000
echo '{"mcpServers":{}}' > /tmp/empty-mcp.json
cd ~/balance-bot/chassis
env -u ANTHROPIC_API_KEY claude -p "$(cat /tmp/v31-impl-brief.md)" --model claude-sonnet-5 \
  --mcp-config /tmp/empty-mcp.json --strict-mcp-config \
  --allowedTools "Read,Edit,Write,Bash(blender*),Bash(bash*),Bash(ls*),Bash(grep*),Bash(cat*),Bash(head*),Bash(tail*),Bash(cd*),Bash(python3*),Bash(echo*),Bash(cp*)" \
  --disallowedTools "Bash(sudo*),Bash(curl*),Bash(git*),Bash(rm*),Bash(mv*),Bash(systemctl*),Bash(service*),Bash(chmod*),Read(*.png),Read(*.jpg),Read(*.jpeg),Read(*.gif),Read(*.bmp)" \
  --max-turns 90 --output-format json > /tmp/claude-v31.json 2>/tmp/claude-v31.err
echo "EXIT: $?" >> /tmp/claude-v31.json
