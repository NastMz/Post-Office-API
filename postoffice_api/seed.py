"""Seeds demo accounts and a few conversations through the real SMTP/IMAP path.

Runs at container start when ``SEED_DEMO_DATA=true``. It is idempotent: if any
user already exists, nothing is changed.

    python -m postoffice_api.seed
"""

from __future__ import annotations

import logging
import time

from postoffice_api.app import build_services
from postoffice_api.config import Settings
from postoffice_api.errors import ApiError
from postoffice_api.schemas import ComposeRequest, DraftRequest, MessageRef

log = logging.getLogger("postoffice.seed")

DEMO_PASSWORD = "postoffice"
DEMO_USERS = [
    ("ana", "Ana Torres"),
    ("bruno", "Bruno Díaz"),
    ("carla", "Carla Méndez"),
    ("diego", "Diego Rojas"),
]

# (sender, recipients, subject, body)
CONVERSATIONS = [
    (
        "bruno",
        ["ana"],
        "Laboratorio 3: captura de tráfico SMTP",
        "Hola Ana,\n\nYa subí la captura de Wireshark del laboratorio 3. Se ve claro el "
        "diálogo EHLO → AUTH → MAIL FROM → RCPT TO → DATA.\n\n¿La revisas antes del jueves?\n\n"
        "Bruno",
    ),
    (
        "carla",
        ["ana", "bruno"],
        "Reunión de proyecto — viernes 10:00",
        "Equipo,\n\nPropongo vernos el viernes a las 10:00 en la sala de redes para "
        "cerrar la demo del servidor de correo.\n\nAgenda:\n  1. Revisión de Postfix y Dovecot\n"
        "  2. Pruebas de IMAP con un cliente real\n  3. Ensayo de la presentación\n\nCarla",
    ),
    (
        "diego",
        ["ana"],
        "Diferencias entre IMAP y POP3",
        "Ana, te dejo el resumen que pediste:\n\n- POP3 descarga y normalmente borra del "
        "servidor.\n- IMAP mantiene los mensajes en el servidor, con carpetas y banderas "
        "(\\Seen, \\Flagged, \\Answered).\n\nPor eso usamos IMAP en el proyecto.\n\nDiego",
    ),
    (
        "bruno",
        ["ana"],
        "Puertos del laboratorio",
        "Recordatorio rápido:\n\n  25  SMTP entre servidores\n  587 envío autenticado "
        "(submission)\n  143 IMAP\n\nEn el docker compose quedan publicados en 8154, 8152 y "
        "8153.\n\nBruno",
    ),
    (
        "ana",
        ["carla"],
        "Re: Reunión de proyecto — viernes 10:00",
        "Perfecto, Carla. Llevo el portátil con el cliente de correo configurado.\n\nAna",
    ),
    (
        "ana",
        ["diego", "bruno"],
        "Informe final — borrador de la sección de DNS",
        "Hola a ambos,\n\nEscribí la parte de registros MX y cómo el MTA decide a qué "
        "servidor entregar. ¿Pueden revisarla?\n\nAna",
    ),
]


def _wait_for_dependencies(services, attempts: int = 30) -> None:
    for attempt in range(1, attempts + 1):
        try:
            services.users.list_all()
            return
        except ApiError as err:
            log.info("Waiting for dependencies (%s/%s): %s", attempt, attempts, err.message)
            time.sleep(2)
    raise SystemExit("Dependencies did not become available")


def seed(settings: Settings) -> bool:
    services = build_services(settings)
    _wait_for_dependencies(services)
    if services.users.list_all():
        log.info("Users already exist; skipping demo data")
        return False

    users = {
        username: services.auth.register(name, username, DEMO_PASSWORD)
        for username, name in DEMO_USERS
    }
    for sender, recipients, subject, body in CONVERSATIONS:
        services.mail.send(users[sender], ComposeRequest(to=recipients, subject=subject, body=body))
        time.sleep(1.1)  # distinct Date headers for a natural ordering

    ana = users["ana"]
    time.sleep(1)  # let LMTP finish delivering
    inbox = services.mail.list(ana, "inbox", None, 0, 50).items
    by_subject = {m.subject: m for m in inbox}
    ports = by_subject.get("Puertos del laboratorio")
    imap = by_subject.get("Diferencias entre IMAP y POP3")
    meeting = by_subject.get("Reunión de proyecto — viernes 10:00")
    lab = by_subject.get("Laboratorio 3: captura de tráfico SMTP")
    if imap:
        services.mail.set_flags(ana, "inbox", imap.uid, seen=True, flagged=True)
    if meeting:
        services.mail.set_flags(ana, "inbox", meeting.uid, seen=True, flagged=None)
    if ports:
        services.mail.set_flags(ana, "inbox", ports.uid, seen=True, flagged=None)
        services.mail.move(ana, "inbox", ports.uid, "archive")
    services.mail.save_draft(
        ana,
        DraftRequest(
            to=["bruno"],
            subject="Re: Laboratorio 3: captura de tráfico SMTP",
            body="Bruno, ya la revisé. Solo falta resaltar el código 250 de",
            reply_to=MessageRef(folder="inbox", uid=lab.uid) if lab else None,
        ),
    )
    services.mail.send(
        users["diego"],
        ComposeRequest(to=["ana"], subject="Oferta de prueba", body="Mensaje de prueba sin uso."),
    )
    time.sleep(1)
    for message in services.mail.list(ana, "inbox", "Oferta de prueba", 0, 5).items:
        services.mail.set_flags(ana, "inbox", message.uid, seen=True, flagged=None)
        services.mail.delete(ana, "inbox", message.uid)
    log.info("Seeded %s demo users", len(users))
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    seed(Settings.from_env())
