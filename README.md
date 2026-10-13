# Agente autónomo de gestión inteligente de correo con IA

He diseñado e implementado un agente autónomo que monitoriza una cuenta de Gmail, analiza automáticamente los correos entrantes mediante IA y decide qué tratamiento aplicar en función de su contenido, relevancia y prioridad.

El sistema está desplegado en una máquina Linux con Xubuntu y funciona de forma autónoma mediante servicios y timers de systemd, sin necesidad de intervención manual.

## Principales funcionalidades

- Monitorización automática de Gmail cada 15 minutos mediante Gmail API + OAuth 2.0.
- Extracción y normalización de mensajes MIME para convertir emails de diferentes formatos en una estructura común.
- Procesamiento mediante un agente especializado de OpenClaw, conectado a un modelo de OpenAI GPT-5.6 Luna.
- Clasificación estructurada de cada correo por categoría, importancia y prioridad.
- Detección de recruiters, entrevistas, candidaturas, ofertas laborales, alertas de seguridad, newsletters, actividad social y mensajes irrelevantes.
- Validación estricta de la respuesta de la IA mediante JSON y reglas deterministas antes de permitir cualquier acción.
- Organización automática de correos no importantes mediante etiquetas de Gmail y marcado como leído.
- Los mensajes importantes permanecen intactos en Inbox y sin leer.
- Sistema conservador de REVISION ante errores técnicos, respuestas inválidas o incertidumbre.
- Notificaciones inmediatas mediante Telegram Bot API para mensajes importantes.
- Resúmenes automáticos por Telegram varias veces al día.
- Persistencia completa en SQLite para auditoría, deduplicación, estados, errores, notificaciones y trazabilidad.
- Procesamiento idempotente: un mismo mensaje no se procesa ni notifica dos veces.
- Protección frente a prompt injection: el contenido del email se trata siempre como dato no confiable.
- Guards específicos que limitan técnicamente las operaciones permitidas sobre Gmail.
- Recuperación ante errores de OAuth, fallos del modelo, timeouts o problemas de infraestructura.
- Suite automatizada de más de 40 tests, incluyendo casos de clasificación, seguridad, deduplicación, Gmail, Telegram y regresiones.

## Flujo de funcionamiento

```text
Gmail
  ↓
Gmail API / OAuth 2.0
  ↓
Polling automático en Python
  ↓
Extracción MIME + normalización
  ↓
Deduplicación
  ↓
Agente OpenClaw
  ↓
OpenAI GPT-5.6 Luna
  ↓
JSON estructurado
  ↓
Validator + reglas de seguridad
  ↓
┌─────────────────────────────────┐
│ IMPORTANTE → Inbox + Telegram   │
│ NO_IMPORTANTE → organizar Gmail │
│ REVISION → no modificar Gmail   │
└─────────────────────────────────┘
  ↓
SQLite / auditoría / estadísticas
```

## Stack tecnológico

Python 3.12 · Gmail API · OAuth 2.0 · OpenClaw · OpenAI GPT-5.6 Luna · SQLite · Telegram Bot API · systemd · Linux/Xubuntu · Git/GitHub · pytest

También he trabajado en aspectos de arquitectura orientada a eventos, integración de APIs, diseño de agentes IA, salida estructurada de LLMs, validación, idempotencia, gestión segura de secretos, observabilidad, tolerancia a fallos y automatización de procesos Linux.
