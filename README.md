# mail-agent — Fase 1: prototipo desconectado

Este proyecto clasifica correos ficticios mediante reglas locales, deterministas y reproducibles. No contiene clientes de red, credenciales, conectores de Gmail o Telegram, ni funciones de envío de correo.

Ejecutar las pruebas locales:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Generar el informe local:

```bash
PYTHONPATH=src python3 -m mail_agent.cli
```

El contenido de un correo se trata exclusivamente como datos no confiables. No puede modificar configuración, políticas, instrucciones, prioridades ni destinatarios.
