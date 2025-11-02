DAEMON STATISTICS ENHANCEMENT - STEP-BY-STEP EXECUTION
You are now tasked with enhancing the ai-cli-bridge daemon to track and report additional statistics. You have received the full daemon codebase context.
STATISTICS TO ADD:

Token Breakdown: sent_tokens (prompt) and response_tokens (completion)
Response Timing: last_response_time_ms
Token Velocity: tokens_per_sec (last message)
Session Averages: avg_response_time_ms and avg_tokens_per_sec

STRICT EXECUTION PROTOCOL:
YOU MUST WORK ONE STEP AT A TIME. NO EXCEPTIONS.
For each step:

YOU present the change: Show the specific file, location, and code modification needed
I execute: I will apply the change and run tests
I report results: I will tell you if it worked or if there are errors
YOU wait: Do NOT proceed to the next step until I explicitly say "next step" or "continue"

WORKFLOW:
Step N: [Description]

File: path/to/file.py
Location: Line X or function function_name()
Change: [Detailed explanation]
Code: [Show the exact modification]

Then STOP and WAIT for my confirmation before proceeding.
IMPORTANT RULES:

❌ Do NOT present multiple steps at once
❌ Do NOT assume a step worked without my confirmation
❌ Do NOT skip ahead
✅ Wait for me to say "next" or "continue" after each step
✅ If I report an error, help me fix it before moving on
✅ Keep changes minimal and focused per step

SUCCESS CRITERIA:
After all steps, the daemon's status endpoint should return something like:
json"claude": {
  "turn_count": 5,
  "token_count": 2450,
  "sent_tokens": 1200,
  "response_tokens": 1250,
  "last_response_time_ms": 4200,
  "tokens_per_sec": 185.5,
  "avg_response_time_ms": 3800,
  "avg_tokens_per_sec": 178.3,
  ...
}
Begin with Step 1 once you've analyzed the daemon code structure.
WAIT FOR MY "GO" COMMAND BEFORE STARTING.
