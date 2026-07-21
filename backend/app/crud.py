from typing import Any

from sqlalchemy.orm import Session


class CRUDBase:
    """
    Generic CRUD helper.
    """

    def __init__(self, model):
        self.model = model

    def get(self, db: Session, obj_id: int):
        return (
            db.query(self.model)
            .filter(self.model.id == obj_id)
            .first()
        )

    def get_all(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100,
    ):
        return (
            db.query(self.model)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create(
        self,
        db: Session,
        obj,
    ):
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def update(
        self,
        db: Session,
        obj_id: int,
        data: dict[str, Any],
    ):
        obj = self.get(db, obj_id)

        if obj is None:
            return None

        for key, value in data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)

        db.commit()
        db.refresh(obj)

        return obj

    def delete(
        self,
        db: Session,
        obj_id: int,
    ):
        obj = self.get(db, obj_id)

        if obj is None:
            return False

        db.delete(obj)
        db.commit()

        return True

    def exists(
        self,
        db: Session,
        **filters,
    ):
        query = db.query(self.model)

        for key, value in filters.items():
            query = query.filter(
                getattr(self.model, key) == value
            )

        return query.first() is not None

    def first(
        self,
        db: Session,
        **filters,
    ):
        query = db.query(self.model)

        for key, value in filters.items():
            query = query.filter(
                getattr(self.model, key) == value
            )

        return query.first()

    def filter(
        self,
        db: Session,
        **filters,
    ):
        query = db.query(self.model)

        for key, value in filters.items():
            query = query.filter(
                getattr(self.model, key) == value
            )

        return query.all()

    def count(self, db: Session):
        return db.query(self.model).count()