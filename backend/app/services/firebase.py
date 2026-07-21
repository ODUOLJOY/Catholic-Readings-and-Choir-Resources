import firebase_admin
from firebase_admin import credentials, messaging
from pathlib import Path

_initialized = False


def initialize_firebase():
    global _initialized

    if _initialized:
        return

    key_path = Path("firebase-service-account.json")

    if not key_path.exists():
        print("Firebase service account not found.")
        return

    cred = credentials.Certificate(str(key_path))
    firebase_admin.initialize_app(cred)

    _initialized = True
    print("Firebase initialized successfully.")


def send_push_notification(
    token: str,
    title: str,
    body: str,
    data: dict | None = None,
):
    initialize_firebase()

    message = messaging.Message(
        token=token,
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        data=data or {},
    )

    response = messaging.send(message)

    return {
        "success": True,
        "message_id": response,
    }


def send_multicast_notification(
    tokens: list[str],
    title: str,
    body: str,
    data: dict | None = None,
):
    initialize_firebase()

    if not tokens:
        return {
            "success": False,
            "message": "No device tokens supplied.",
        }

    message = messaging.MulticastMessage(
        tokens=tokens,
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        data=data or {},
    )

    response = messaging.send_each_for_multicast(message)

    return {
        "success": True,
        "success_count": response.success_count,
        "failure_count": response.failure_count,
    }


def notify_daily_reading(tokens: list[str]):
    return send_multicast_notification(
        tokens=tokens,
        title="Daily Catholic Readings",
        body="Today's Mass readings are now available.",
    )


def notify_new_choir_resource(
    tokens: list[str],
    resource_title: str,
):
    return send_multicast_notification(
        tokens=tokens,
        title="New Choir Resource",
        body=f"{resource_title} has been uploaded.",
    )


def notify_major_feast(
    tokens: list[str],
    feast_name: str,
):
    return send_multicast_notification(
        tokens=tokens,
        title="Major Feast Day",
        body=f"Today we celebrate {feast_name}.",
    )