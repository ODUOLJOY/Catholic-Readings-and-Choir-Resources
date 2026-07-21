from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.readings import Reading
from app.models.saint import Saint
from app.services.notifications import NotificationService
from app.services.missal_engine import MissalEngine


class SchedulerService:
    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone="Africa/Nairobi")

    def start(self):
        self.scheduler.add_job(
            self.daily_update,
            CronTrigger(hour=0, minute=5),
            id="daily_readings_update",
            replace_existing=True,
        )

        self.scheduler.add_job(
            self.send_daily_notifications,
            CronTrigger(hour=6, minute=0),
            id="daily_notifications",
            replace_existing=True,
        )

        self.scheduler.start()

    def shutdown(self):
        self.scheduler.shutdown()

    @staticmethod
    def daily_update():
        db: Session = SessionLocal()

        try:
            MissalEngine.sync_today(db)
        finally:
            db.close()

    @staticmethod
    def send_daily_notifications():
        db: Session = SessionLocal()

        try:
            NotificationService.send_daily_reading_notifications(db)
        finally:
            db.close()


scheduler = SchedulerService()