import firebase_admin
from firebase_admin import credentials, messaging
from pathlib import Path

from app.core.config import settings


def initialize_firebase():
    try:
        return firebase_admin.get_app()
    except ValueError:
        pass

    key_path = Path("firebase-service-account.json")
    if key_path.is_file():
        credential = credentials.Certificate(str(key_path))
    elif settings.FIREBASE_CLIENT_EMAIL and settings.FIREBASE_PRIVATE_KEY:
        if not settings.FIREBASE_PROJECT_ID:
            raise RuntimeError(
                "FIREBASE_PROJECT_ID is required with inline Firebase credentials."
            )
        credential = credentials.Certificate(
            {
                "type": "service_account",
                "project_id": settings.FIREBASE_PROJECT_ID,
                "private_key": settings.FIREBASE_PRIVATE_KEY.replace("\\n", "\n"),
                "client_email": settings.FIREBASE_CLIENT_EMAIL,
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        )
    elif settings.FIREBASE_CLIENT_EMAIL or settings.FIREBASE_PRIVATE_KEY:
        raise RuntimeError(
            "FIREBASE_CLIENT_EMAIL and FIREBASE_PRIVATE_KEY must be configured together."
        )
    else:
        credential = credentials.ApplicationDefault()

    options = {}
    if settings.FIREBASE_PROJECT_ID:
        options["projectId"] = settings.FIREBASE_PROJECT_ID
    if settings.FIREBASE_STORAGE_BUCKET:
        options["storageBucket"] = settings.FIREBASE_STORAGE_BUCKET
    return firebase_admin.initialize_app(credential, options=options)


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