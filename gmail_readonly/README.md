# Gmail local controller

Componente local para leer Gmail mediante OAuth `gmail.modify`, deduplicar por `account_id + message_id` y enviar cada correo nuevo a `mail_reader` con una sesión `gmail-<messageId>`.

La única mutación implementada está cerrada en `GmailReadStateGuard.mark_as_read(message_id)`: elimina exactamente la etiqueta `UNREAD`. No hay API para enviar, redactar, borrar, archivar, usar papelera o modificar etiquetas arbitrarias. La autorización OAuth y las llamadas a Google se ejecutan solo mediante comandos explícitos; las pruebas locales no las invocan.

Las notificaciones se encolan exclusivamente en SQLite. Este paquete no contiene un cliente de Telegram.

Las credenciales reales pertenecen fuera del repositorio, por ejemplo en `~/.local/state/mail-agent/gmail/`, con permisos de propietario únicamente.
