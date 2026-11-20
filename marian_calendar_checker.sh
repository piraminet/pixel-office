#!/bin/bash

# Script para controlar a Marian (agente 3) - Gestora de Calendario
# Se ejecuta cada 3 minutos, va a la sala de reuniones, revisa calendario, vuelve

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
LOCK_FILE="${PIXEL_DATA_DIR}/marian_calendar_checker.lock"
MARIAN_AGENT_ID=1
MARIAN_NEW_EVENT_FILE="${PIXEL_DATA_DIR}/marian_new_event.txt"
MARIAN_MODE_FILE="${PIXEL_DATA_DIR}/marian_mode.txt"
MARIAN_LAST_EVENT_LOG="${PIXEL_DATA_DIR}/marian_last_event.log"

# === COORDENADAS DE LA SILLA VERDE EN SALA DE REUNIONES ===
# Silla frente al portátil en la mesa roja (ajustada según movimiento real)
SILLA_X=11
SILLA_Y=5

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

# Obtener posición actual del agente desde la API (en tiles)
get_agent_pos() {
    local pos=$(curl -s "$SERVER/api/config" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); a=[x for x in d['agents'] if x['id']==$MARIAN_AGENT_ID][0]; print(f\"{a['x']} {a['y']}\")" 2>/dev/null)
    if [ -n "$pos" ]; then
        local x=$(echo $pos | cut -d' ' -f1)
        local y=$(echo $pos | cut -d' ' -f2)
        # Convertir a tiles (GRID_SIZE = 32)
        echo "$((x / 32)) $((y / 32))"
    else
        echo "16 11"  # Default según imagen
    fi
}

# Evitar ejecuciones simultáneas
if [ -f "$LOCK_FILE" ]; then
    echo "[$(current_time)] Marian ya está ejecutándose. Saliendo."
    exit 0
fi

touch "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

# === OBTENER POSICIÓN ACTUAL DE MARIAN ===
ORIGINAL_POS=$(get_agent_pos)
ORIGINAL_X=$(echo $ORIGINAL_POS | cut -d' ' -f1)
ORIGINAL_Y=$(echo $ORIGINAL_POS | cut -d' ' -f2)

echo "[$(current_time)] Marian en posición ($ORIGINAL_X, $ORIGINAL_Y)"

# === VERIFICAR SI HAY EVENTO NUEVO PENDIENTE ===
NEW_EVENT_MODE=""
if [ -f "$MARIAN_NEW_EVENT_FILE" ]; then
    NEW_EVENT_MODE="true"
    EVENT_DATA=$(cat "$MARIAN_NEW_EVENT_FILE")
    EVENT_TITLE=$(echo "$EVENT_DATA" | cut -d'|' -f1)
fi

echo "[$(current_time)] Marian iniciando ronda de calendario..."
add_log $MARIAN_AGENT_ID "start" "Iniciando ronda desde ($ORIGINAL_X, $ORIGINAL_Y)"

# 1. Ir a la silla de la Sala de Reuniones
if [ "$NEW_EVENT_MODE" = "true" ]; then
    echo "[$(current_time)] Marian yendo a Sala de Reuniones para añadir evento..."
    send_command $MARIAN_AGENT_ID "move" $SILLA_X $SILLA_Y "Voy a añadir un evento..." true
    set_message $MARIAN_AGENT_ID "Añadiendo evento..."
    add_log $MARIAN_AGENT_ID "walking" "Yendo a añadir evento"
else
    echo "[$(current_time)] Marian yendo a Sala de Reuniones..."
    send_command $MARIAN_AGENT_ID "move" $SILLA_X $SILLA_Y "Voy a revisar el calendario..." true
    set_message $MARIAN_AGENT_ID "Yendo a revisar calendario..."
    add_log $MARIAN_AGENT_ID "walking" "Yendo a Sala de Reuniones"
fi

# 2. Dejarle tiempo para llegar (el cliente web confirma internamente)
echo "[$(current_time)] Dando margen para que Marian llegue y se siente..."
sleep 20
set_message $MARIAN_AGENT_ID "Gestionando calendario..."

# 3. Ahora sí, revisar calendario o añadir evento estando sentada
echo "[$(current_time)] Marian en la sala de reuniones..."

# Esperar un momento sentada antes de actuar
sleep 3

if [ "$NEW_EVENT_MODE" = "true" ]; then
    # === AÑADIR NUEVO EVENTO ===
    EVENT_DATA=$(cat "$MARIAN_NEW_EVENT_FILE")
    EVENT_TITLE=$(echo "$EVENT_DATA" | cut -d'|' -f1)
    EVENT_DATE=$(echo "$EVENT_DATA" | cut -d'|' -f2)
    EVENT_START=$(echo "$EVENT_DATA" | cut -d'|' -f3)
    EVENT_END=$(echo "$EVENT_DATA" | cut -d'|' -f4)
    
    # Intentar añadir con gog
    if command -v gog &> /dev/null; then
        START_ISO=$(date -j -f "%Y-%m-%d %H:%M" "$EVENT_DATE $EVENT_START" "+%Y-%m-%dT%H:%M:00%z" 2>/dev/null)
        END_ISO=$(date -j -f "%Y-%m-%d %H:%M" "$EVENT_DATE $EVENT_END" "+%Y-%m-%dT%H:%M:00%z" 2>/dev/null)
        if [ -z "$START_ISO" ]; then START_ISO="${EVENT_DATE}T${EVENT_START}:00"; fi
        if [ -z "$END_ISO" ]; then END_ISO="${EVENT_DATE}T${EVENT_END}:00"; fi
        gog calendar create primary --summary "$EVENT_TITLE" --from "$START_ISO" --to "$END_ISO" >"$MARIAN_LAST_EVENT_LOG" 2>&1
        ADD_RESULT=$?
    else
        ADD_RESULT=1
    fi
    
    if [ $ADD_RESULT -eq 0 ]; then
        MSG="✅ Evento añadido: ${EVENT_TITLE:0:20}"
        add_log $MARIAN_AGENT_ID "added" "Evento añadido: $EVENT_TITLE"
    else
        MSG="📝 Evento registrado: ${EVENT_TITLE:0:20}"
        add_log $MARIAN_AGENT_ID "noted" "Evento anotado: $EVENT_TITLE"
    fi
    
    send_command $MARIAN_AGENT_ID "move" $SILLA_X $SILLA_Y "$MSG" true
    set_message $MARIAN_AGENT_ID "$MSG"
    
    # Limpiar archivo de evento
    rm -f "$MARIAN_NEW_EVENT_FILE"
    rm -f "$MARIAN_MODE_FILE"
    
    sleep 5
else
    # === REVISIÓN DE CALENDARIO (Google Calendar via gog) ===
    # Revisa eventos de los próximos 3 días
    
    EVENT_COUNT=0
    EVENT_INFO=""
    EVENTS_JSON=""
    
    # Intentar obtener eventos con gog
    if command -v gog &> /dev/null; then
        # Obtener eventos de los próximos 3 días en formato JSON
        EVENTS_JSON=$(gog calendar events list --days-ahead 3 --json 2>/dev/null)
        
        if [ -n "$EVENTS_JSON" ] && [ "$EVENTS_JSON" != "[]" ]; then
            # Contar eventos
            EVENT_COUNT=$(echo "$EVENTS_JSON" | grep -c '"summary"' 2>/dev/null || echo "0")
            
            # Obtener el primer evento
            if [ "$EVENT_COUNT" -gt 0 ]; then
                FIRST_EVENT=$(echo "$EVENTS_JSON" | grep -o '"summary":"[^"]*"' | head -1 | cut -d'"' -f4)
                EVENT_INFO="$FIRST_EVENT"
            fi
        fi
    fi
    
    # Si no hay gog o no hay eventos, mostrar vacío
    if [ "$EVENT_COUNT" = "0" ] || [ -z "$EVENT_COUNT" ]; then
        EVENT_COUNT=0
    fi
    
    if [ $EVENT_COUNT -gt 0 ]; then
        # Hay eventos próximos
        if [ $EVENT_COUNT -eq 1 ]; then
            MSG="📅 1 evento: ${EVENT_INFO:0:25}"
        else
            MSG="📅 $EVENT_COUNT eventos. Próximo: ${EVENT_INFO:0:20}"
        fi
        send_command $MARIAN_AGENT_ID "move" $SILLA_X $SILLA_Y "$MSG" true
        set_message $MARIAN_AGENT_ID "$MSG"
        add_log $MARIAN_AGENT_ID "alert" "$MSG"
        sleep 5
    else
        # No hay eventos
        MSG="Sin eventos próximos"
        send_command $MARIAN_AGENT_ID "move" $SILLA_X $SILLA_Y "$MSG" true
        set_message $MARIAN_AGENT_ID "$MSG"
        add_log $MARIAN_AGENT_ID "empty" "No hay eventos"
        sleep 2
    fi
fi

# 4. Terminar y levantarse
echo "[$(current_time)] Marian terminó de revisar, volviendo..."
send_command $MARIAN_AGENT_ID "idle" 0 0 "Calendario revisado ✓" false
set_message $MARIAN_AGENT_ID "Calendario revisado"
add_log $MARIAN_AGENT_ID "done" "Revisión completada"

# 5. Volver a su posición ORIGINAL
sleep 2
echo "[$(current_time)] Marian volviendo a ($ORIGINAL_X, $ORIGINAL_Y)..."
send_command $MARIAN_AGENT_ID "move" $ORIGINAL_X $ORIGINAL_Y "Vuelvo a mi puesto..." false
set_message $MARIAN_AGENT_ID "En mi puesto 💻"
add_log $MARIAN_AGENT_ID "working" "Trabajando en posición ($ORIGINAL_X, $ORIGINAL_Y)"

echo "[$(current_time)] Marian finalizó ronda."
