from sqlalchemy.orm import Session

from app.models.saint import Saint


class SaintService:

    @staticmethod
    def get_all(
        db: Session,
        skip: int = 0,
        limit: int = 100,
    ):
        return (
            db.query(Saint)
            .order_by(Saint.name.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_by_id(
        db: Session,
        saint_id: int,
    ):
        return (
            db.query(Saint)
            .filter(Saint.id == saint_id)
            .first()
        )

    @staticmethod
    def get_by_date(
        db: Session,
        month: int,
        day: int,
    ):
        return (
            db.query(Saint)
            .filter(
                Saint.month == month,
                Saint.day == day,
            )
            .all()
        )

    @staticmethod
    def search(
        db: Session,
        query: str,
    ):
        return (
            db.query(Saint)
            .filter(
                Saint.name.ilike(f"%{query}%")
            )
            .order_by(Saint.name.asc())
            .all()
        )

    @staticmethod
    def create(
        db: Session,
        saint: Saint,
    ):
        db.add(saint)
        db.commit()
        db.refresh(saint)
        return saint

    @staticmethod
    def update(
        db: Session,
        saint_id: int,
        data: dict,
    ):
        saint = (
            db.query(Saint)
            .filter(Saint.id == saint_id)
            .first()
        )

        if not saint:
            return None

        for key, value in data.items():
            if hasattr(saint, key):
                setattr(saint, key, value)

        db.commit()
        db.refresh(saint)

        return saint

    @staticmethod
    def delete(
        db: Session,
        saint_id: int,
    ):
        saint = (
            db.query(Saint)
            .filter(Saint.id == saint_id)
            .first()
        )

        if not saint:
            return False

        db.delete(saint)
        db.commit()

        return True