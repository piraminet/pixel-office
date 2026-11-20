#!/bin/bash

# Script para controlar a Pep (agente 2) - Gestor de Correo
# Se ejecuta cada X minutos, va al despacho, se sienta, revisa email, vuelve

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
LOCK_FILE="${PIXEL_DATA_DIR}/pep_email_checker.lock"
PEP_AGENT_ID=2

# Silla verde en Despacho financiera (coordenadas exactas)
SILLA_X=15
SILLA_Y=22

# Sala principal - zona de ordenadores (varias sillas disponibles)
SALA_X=10
SALA_Y=14

# Sillas en la sala (para elegir una aleatoria)
SILLAS_SALA=(
    "8:13"
    "12:13" 
    "8:16"
    "12:16"
)

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

# Obtener posición actual del agente desde la API
get_agent_pos() {
    curl -s "$SERVER/api/config" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); a=[x for x in d['agents'] if x['id']==$PEP_AGENT_ID][0]; print(f\"{a['x']} {a['y']}\")" 2>/dev/null || echo "0 0"
}

# Evitar ejecuciones simultáneas
if [ -f "$LOCK_FILE" ]; then
    echo "[$(current_time)] Pep ya está ejecutándose. Saliendo."
    exit 0
fi

touch "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

echo "[$(current_time)] Pep iniciando ronda de revisión..."
add_log $PEP_AGENT_ID "start" "Iniciando ronda"

# 1. Ir a la silla del Despacho financiero
echo "[$(current_time)] Pep yendo a Despacho Financiero..."
send_command $PEP_AGENT_ID "move" $SILLA_X $SILLA_Y "Voy a revisar el correo..." true
set_message $PEP_AGENT_ID "Yendo a revisar correo..."
add_log $PEP_AGENT_ID "walking" "Yendo a Despacho Financiero"

# 2. Darle margen para llegar (el cliente gestiona la animación)
echo "[$(current_time)] Dando margen para que Pep se siente..."
sleep 15
set_message $PEP_AGENT_ID "Revisando correo..."
add_log $PEP_AGENT_ID "checking" "Revisando emails"

# Esperar un momento sentado antes de revisar (simula abrir el ordenador)
sleep 3

EMAIL_COUNT=0
EMAIL_SUBJECT=""
if [ -f "/tmp/email_alert_pending.txt" ]; then
    # Leer datos del email (formato: "count|subject")
    EMAIL_DATA=$(cat /tmp/email_alert_pending.txt 2>/dev/null || echo "1|Nuevo mensaje")
    EMAIL_COUNT=$(echo "$EMAIL_DATA" | cut -d'|' -f1)
    EMAIL_SUBJECT=$(echo "$EMAIL_DATA" | cut -d'|' -f2-)
    if [ -z "$EMAIL_COUNT" ] || [ "$EMAIL_COUNT" = "0" ]; then
        EMAIL_COUNT=1
    fi
    
    # Formatear mensaje: si el asunto es largo, ponerlo en 2 líneas
    if [ ${#EMAIL_SUBJECT} -gt 25 ]; then
        # Asunto largo: dividir en 2 líneas
        if [ "$EMAIL_COUNT" = "1" ]; then
            MSG="¡1 mensaje!\n$EMAIL_SUBJECT"
        else
            MSG="¡$EMAIL_COUNT mensajes!\n$EMAIL_SUBJECT"
        fi
    else
        # Asunto corto: todo en una línea
        if [ "$EMAIL_COUNT" = "1" ]; then
            MSG="¡1 mensaje! $EMAIL_SUBJECT"
        else
            MSG="¡$EMAIL_COUNT mensajes! Último: $EMAIL_SUBJECT"
        fi
    fi
    
    # Actualizar mensaje en globo (enviar comando de nuevo con el mensaje)
    send_command $PEP_AGENT_ID "move" $SILLA_X $SILLA_Y "$MSG" true
    set_message $PEP_AGENT_ID "$MSG"
    add_log $PEP_AGENT_ID "alert" "$MSG"
    
    # Borrar la alerta (ya se procesó)
    rm -f /tmp/email_alert_pending.txt
    
    # Simular tiempo de lectura
    sleep 5
else
    # No hay emails
    MSG="No hay mensajes nuevos"
    send_command $PEP_AGENT_ID "move" $SILLA_X $SILLA_Y "$MSG" true
    set_message $PEP_AGENT_ID "$MSG"
    add_log $PEP_AGENT_ID "empty" "No hay emails"
    sleep 2
fi

# 4. Terminar y levantarse
echo "[$(current_time)] Pep terminó de revisar, volviendo..."
send_command $PEP_AGENT_ID "idle" 0 0 "Correo revisado ✓" false
set_message $PEP_AGENT_ID "Correo revisado"
add_log $PEP_AGENT_ID "done" "Revisión completada"

# 5. Volver a la sala principal (elegir silla aleatoria o quedarse de pie)
sleep 2

# Elegir aleatoriamente: 70% sentarse en silla, 30% quedarse de pie
RANDOM_CHOICE=$((RANDOM % 10))
if [ $RANDOM_CHOICE -lt 7 ]; then
    # Sentarse en una silla aleatoria de la sala
    RANDOM_SILLA=${SILLAS_SALA[$RANDOM % ${#SILLAS_SALA[@]}]}
    SILLA_SALA_X=$(echo $RANDOM_SILLA | cut -d':' -f1)
    SILLA_SALA_Y=$(echo $RANDOM_SILLA | cut -d':' -f2)
    send_command $PEP_AGENT_ID "move" $SILLA_SALA_X $SILLA_SALA_Y "Vuelvo a trabajar..." true
    set_message $PEP_AGENT_ID "En mi puesto 💻"
    add_log $PEP_AGENT_ID "working" "Trabajando en sala"
else
    # Quedarse de pie en la sala
    send_command $PEP_AGENT_ID "move" $SALA_X $SALA_Y "Vuelvo a la sala..." false
    set_message $PEP_AGENT_ID "De vuelta en la sala"
    add_log $PEP_AGENT_ID "idle" "En sala (de pie)"
fi

echo "[$(current_time)] Pep finalizó ronda."
