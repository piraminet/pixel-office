#!/bin/bash

# Dustin (agente 0) y Doc (agente 3) se reúnen cada 5 minutos
# para preguntar y responder cuántos tokens llevamos.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    . "$ENV_FILE"
    set +a
fi
PIXEL_DATA_DIR="${PIXEL_DATA_DIR:-/tmp}"
if [[ "$PIXEL_DATA_DIR" != /* ]]; then
    PIXEL_DATA_DIR="$SCRIPT_DIR/$PIXEL_DATA_DIR"
fi

DEFAULT_PORT="${PORT:-19000}"
SERVER_DEFAULT="http://127.0.0.1:${DEFAULT_PORT}"
SERVER="${PIXEL_SERVER:-${SERVER_DEFAULT}}"
# Auth for POST endpoints (G2): token from .env (PIXEL_API_TOKEN)
AUTH_ARGS=()
[ -n "${PIXEL_API_TOKEN:-}" ] && AUTH_ARGS=(-H "Authorization: Bearer ${PIXEL_API_TOKEN}")
LOG_FILE="${PIXEL_DATA_DIR}/pixel_actions.jsonl"
DUSTIN_AGENT_ID=0
DOC_AGENT_ID=3

# Baldosas dentro de la sala de reuniones (cerca de Marian, sin ocupar su silla)
DUSTIN_MEETING_X=8
DUSTIN_MEETING_Y=6
DOC_MEETING_X=11
DOC_MEETING_Y=6

ARRIVAL_SLEEP=6
REPLY_SLEEP=4
LOOP_SLEEP=300

current_time() {
    date +"%H:%M"
}

add_log() {
    local agent=$1
    local action=$2
    local msg=$3
    echo "{\"time\":\"$(current_time)\",\"agent\":$agent,\"action\":\"$action\",\"msg\":\"$msg\"}" >> "$LOG_FILE"
    tail -n 100 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
}

set_message() {
    local agent=$1
    local msg=$2
    echo "$msg" > "${PIXEL_DATA_DIR}/agent_${agent}_message.txt"
}

send_command() {
    local agent=$1
    local action=$2
    local tileX=$3
    local tileY=$4
    local msg=$5
    local sitAfter=$6

    curl -s "${AUTH_ARGS[@]}" -X POST "$SERVER/api/agent/$agent/command" \
        -H "Content-Type: application/json" \
        -d "{\"action\":\"$action\",\"tileX\":$tileX,\"tileY\":$tileY,\"msg\":\"$msg\",\"sitAfter\":$sitAfter}" > /dev/null
}

fetch_token_summary() {
    local json
    json=$(openclaw status --json 2>/dev/null)
    if [ -z "$json" ]; then
        echo "sin datos"
        return
    fi
    TOKENS_JSON="$json" python3 - <<'PY'
import json, os
try:
    payload = os.environ.get('TOKENS_JSON', '')
    data = json.loads(payload) if payload else {}
    sessions = data.get('sessions', {}).get('recent', [])
    main = next((s for s in sessions if s.get('key') == 'agent:main:main'), None)
    if not main:
        raise ValueError('missing session')
    inp = main.get('inputTokens')
    out = main.get('outputTokens')
    if inp is None or out is None:
        raise ValueError('counts null')
    print(f"{inp} in / {out} out")
except Exception:
    print('sin datos')
PY
}

printf "[%s] Iniciando ritual Dustin-Doc (cada %ds)\n" "$(date)" "$LOOP_SLEEP"

while true; do
    TOKENS=$(fetch_token_summary)
    QUESTION="Doc, ¿cuántos tokens llevamos?"
    ANSWER="Llevamos $TOKENS en gpt-5.1-codex."

    send_command $DUSTIN_AGENT_ID "move" $DUSTIN_MEETING_X $DUSTIN_MEETING_Y "" true
    send_command $DOC_AGENT_ID "move" $DOC_MEETING_X $DOC_MEETING_Y "" true
    set_message $DUSTIN_AGENT_ID ""
    set_message $DOC_AGENT_ID ""

    sleep $ARRIVAL_SLEEP

    set_message $DUSTIN_AGENT_ID "$QUESTION"
    add_log $DUSTIN_AGENT_ID "question" "$QUESTION"

    sleep $REPLY_SLEEP

    set_message $DOC_AGENT_ID "$ANSWER"
    add_log $DOC_AGENT_ID "answer" "$ANSWER"

    sleep $REPLY_SLEEP


    send_command $DUSTIN_AGENT_ID "idle" 0 0 "Gracias, Doc" false
    set_message $DUSTIN_AGENT_ID "Gracias, Doc 🙌"
    add_log $DUSTIN_AGENT_ID "ack" "Gracias, Doc"

    send_command $DOC_AGENT_ID "idle" 0 0 "Cuando quieras" false
    set_message $DOC_AGENT_ID "Cuando quieras 💬"
    add_log $DOC_AGENT_ID "ack" "Respuesta tokens"

    sleep $LOOP_SLEEP
done
