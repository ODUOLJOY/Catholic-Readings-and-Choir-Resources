from app.services.firebase import (
    notify_daily_reading,
    notify_major_feast,
    notify_new_choir_resource,
    send_push_notification,
    send_multicast_notification,
)


class NotificationService:
    """
    Central notification service for the Catholic Readings
    & Choir Resources App.
    """

    @staticmethod
    def send_to_device(
        token: str,
        title: str,
        body: str,
        data: dict | None = None,
    ):
        return send_push_notification(
            token=token,
            title=title,
            body=body,
            data=data,
        )

    @staticmethod
    def send_to_many(
        tokens: list[str],
        title: str,
        body: str,
        data: dict | None = None,
    ):
        return send_multicast_notification(
            tokens=tokens,
            title=title,
            body=body,
            data=data,
        )

    @staticmethod
    def daily_readings(tokens: list[str]):
        return notify_daily_reading(tokens)

    @staticmethod
    def feast_day(
        tokens: list[str],
        feast_name: str,
    ):
        return notify_major_feast(
            tokens,
            feast_name,
        )

    @staticmethod
    def choir_upload(
        tokens: list[str],
        title: str,
    ):
        return notify_new_choir_resource(
            tokens,
            title,
        )

    @staticmethod
    def custom_notification(
        tokens: list[str],
        title: str,
        message: str,
        data: dict | None = None,
    ):
        return send_multicast_notification(
            tokens=tokens,
            title=title,
            body=message,
            data=data,
        )