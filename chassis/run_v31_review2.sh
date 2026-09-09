#!/bin/bash
# Review v3.1 print-final par Claude Opus (auth OAuth Pro, MCP désactivé, images interdites)
cd ~/balance-bot
env -u ANTHROPIC_API_KEY CLAUDE_CODE_MAX_OUTPUT_TOKENS=96000 \
  claude -p "$(cat /tmp/v31-review2-brief.md)" \
  --model opus \
  --mcp-config /tmp/empty-mcp.json --strict-mcp-config \
  --allowedTools "Read,Write,Edit,Bash" \
  --disallowedTools "Bash(sudo*),Bash(curl*),Bash(git*),Bash(rm*),Bash(mv*),Bash(systemctl*),Bash(service*),Bash(chmod*),Read(*.png),Read(*.jpg),Read(*.jpeg),Read(*.gif),Read(*.bmp)" \
  --max-turns 60 --output-format json > /tmp/claude-v31review2.json 2> /tmp/claude-v31review2.err
echo "EXIT=$?" >> /tmp/claude-v31review2.json
