#!/bin/bash
# Wrapper to activate venv and launch ai-chat-ui

# Activate venv
source /home/jacques/dev/ai_app/shared/runtime/venv/bin/activate

# Launch UI
exec ai-chat-ui
