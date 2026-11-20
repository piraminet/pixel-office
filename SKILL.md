---
name: pixel-startup
description: "Plataforma de operaciones Pixel Startup: oficina visual (Pixel Office), dashboard seguro, API y agentes de los harnesses Hermes/OpenClaw."
---

# Pixel Startup Skill

Esta guía orienta la puesta en marcha y el mantenimiento de la plataforma Pixel Startup y su oficina visual (Pixel Office). Úsala cuando necesites (1) reinstalar, (2) ajustar la configuración o (3) enseñar a otra persona a personalizar su propia oficina.

---

## 0. ¿Qué es Pixel Startup?

> "Pixel Startup es una plataforma Node que muestra la oficina pixelada (Pixel Office), expone una API para mover agentes y trae un dashboard protegido por contraseña para editar habitaciones, colisiones y personajes de forma visual."

Recuerda contárselo así al usuario antes de ponerte manos a la obra.

---

## 1. Puesta en marcha express

```bash
cd services/pixel
cp -n .env.example .env   # solo la primera vez (respeta el existente)
npm install
npm start
```

* El servidor queda en `http://127.0.0.1:${PORT:-19000}`.
* El dashboard vive en `http://127.0.0.1:${PORT}/dashboard.html`.
* El archivo `.env` controla el puerto, la carpeta de datos compartidos y la contraseña.

---

## 2. Ficheros críticos (para copiar / hacer backup)

| Propósito             | Ruta                                   | Comentario |
|-----------------------|----------------------------------------|------------|
| Configuración general | `services/pixel/.env`                  | PORT, GEMINI_API_KEY y DASHBOARD_PASSWORD. |
| Estado de agentes     | `services/pixel/data/agents.json`      | Lo toca el dashboard. Puedes editarlo a mano. |
| Mapas/colisiones      | `services/pixel/data/map.json`         | Guarda `rooms` y `collision`. Se sincroniza con la UI. |
| Logs + globos         | `${PIXEL_DATA_DIR}/pixel_actions.jsonl`| Se alimenta desde los scripts Bash. |

Haz copia de esos archivos antes de grandes cambios (además del directorio completo si el usuario lo pide).

---

## 3. Dashboard protegido

* La contraseña se define en `.env` (`DASHBOARD_PASSWORD`).
* El login se verifica en `POST /api/auth/login`, así que cambiar la clave ya no requiere editar HTML.
* Si el usuario olvida la contraseña, actualízala en `.env`, reinicia `npm start` y prueba.

---

## 4. Scripts automáticos

Hay tres scripts Bash que usan la API para mover agentes (Pep, Marian y Dustin/Doc). Todos leen `.env`, respetan `PIXEL_DATA_DIR` y escriben globos de estado:

* `dustin_doc_tokens.sh`
* `pep_email_checker.sh`
* `marian_calendar_checker.sh`
* `add_calendar_event.sh` (inyecta eventos para Marian)

Revísalos si algo no aparece en la oficina: suelen dejar trazas en `pixel_actions.jsonl`.

### Presencia nativa de Hermes y OpenClaw (nuevo)

* `integrations.js` + `GET /api/presence` exponen el estado real de **Hermes Agent** (sesiones y gateway de `~/.hermes`) y **OpenClaw** (probe HTTP del gateway, `OPENCLAW_GATEWAY_URL`/`OPENCLAW_GATEWAY_TOKEN`).
* `index.html` sondea esa API cada 15 s y dibuja chips de estado (verde/gris) sobre el canvas.
* Ambos runtimes mueven personajes por la misma API REST: ver la sección "First-class agent runtimes" del README.

---

## 5. Publicar o compartir

1. Levanta el servidor con `npm start`.
2. Si hace falta acceso externo, reutiliza la instrucción: `cloudflared tunnel --url http://127.0.0.1:${PORT}` (o cualquier proxy que uses normalmente).
3. Entrega al usuario:
   * URL del dashboard
   * Contraseña (`DASHBOARD_PASSWORD`)
   * Ruta del repo y scripts relevantes.

---

## 6. Checklist antes de decir "listo"

- [ ] `.env` actualizado (PORT correcto, claves opcionales y contraseña definida).
- [ ] `agents.json` y `map.json` existen bajo `services/pixel/data/`.
- [ ] Dashboard abre, login funciona y guarda cambios.
- [ ] Scripts Bash apuntan al mismo `PIXEL_DATA_DIR` (si moviste rutas).
- [ ] Documentaste cualquier contraseña nueva al usuario.

Si algo falla, revisa `npm start` (el server loguea cualquier error de lectura/escritura) o los archivos de log en la carpeta de datos.
