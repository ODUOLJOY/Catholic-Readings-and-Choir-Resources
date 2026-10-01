from sqlalchemy.orm import Session

from app.models.community import (
    CommunityGroup,
    GroupMembership,
    ParishMembership,
    RoleAssignment,
)
from app.models.locations import Deanery, Diocese
from app.models.parish import Parish
from app.models.user import User


def user_belongs_to_scope(
    db: Session,
    user: User,
    scope_type: str,
    scope_id: int,
) -> bool:
    active_parishes = db.query(ParishMembership.parish_id).filter(
        ParishMembership.user_id == user.id,
        ParishMembership.status == "active",
    )
    if scope_type == "parish":
        return db.query(ParishMembership.id).filter(
            ParishMembership.user_id == user.id,
            ParishMembership.parish_id == scope_id,
            ParishMembership.status == "active",
        ).first() is not None
    if scope_type == "diocese":
        return db.query(Parish.id).filter(
            Parish.id.in_(active_parishes),
            Parish.diocese_id == scope_id,
        ).first() is not None
    if scope_type == "deanery":
        return db.query(Parish.id).filter(
            Parish.id.in_(active_parishes),
            Parish.deanery_id == scope_id,
        ).first() is not None
    if scope_type == "group":
        group = db.query(CommunityGroup).filter(
            CommunityGroup.id == scope_id,
            CommunityGroup.is_active.is_(True),
        ).first()
        member = db.query(GroupMembership.id).filter(
            GroupMembership.user_id == user.id,
            GroupMembership.group_id == scope_id,
        ).first()
        return bool(
            group
            and member
            and user_belongs_to_scope(db, user, group.scope_type, group.scope_id)
        )
    return False


def scope_exists(db: Session, scope_type: str, scope_id: int) -> bool:
    models = {
        "diocese": Diocese,
        "deanery": Deanery,
        "parish": Parish,
        "group": CommunityGroup,
    }
    model = models.get(scope_type)
    if model is None:
        return False
    query = db.query(model).filter(model.id == scope_id)
    if hasattr(model, "is_active"):
        query = query.filter(model.is_active.is_(True))
    return query.first() is not None


def _assignment_covers(
    db: Session,
    assignment: RoleAssignment,
    scope_type: str,
    scope_id: int,
) -> bool:
    if assignment.scope_type == "global":
        return True
    if assignment.scope_type == scope_type and assignment.scope_id == scope_id:
        return True
    if scope_type not in {"parish", "deanery", "group"}:
        return False
    if assignment.scope_type == "diocese":
        if scope_type == "parish":
            target = db.query(Parish.diocese_id).filter(Parish.id == scope_id).scalar()
            return target == assignment.scope_id
        if scope_type == "deanery":
            target = db.query(Deanery.diocese_id).filter(Deanery.id == scope_id).scalar()
            return target == assignment.scope_id
        group = db.query(CommunityGroup).filter(CommunityGroup.id == scope_id).first()
        if not group:
            return False
        if group.scope_type == "diocese":
            return group.scope_id == assignment.scope_id
        return _assignment_covers(
            db,
            assignment,
            group.scope_type,
            group.scope_id,
        )
    if assignment.scope_type == "deanery" and scope_type == "parish":
        target = db.query(Parish.deanery_id).filter(Parish.id == scope_id).scalar()
        return target == assignment.scope_id
    if assignment.scope_type in {"parish", "group"} and scope_type == "group":
        group = db.query(CommunityGroup).filter(CommunityGroup.id == scope_id).first()
        return bool(
            group
            and group.scope_type == assignment.scope_type
            and group.scope_id == assignment.scope_id
        )
    return False


def has_scoped_role(
    db: Session,
    user: User,
    roles: set[str],
    scope_type: str,
    scope_id: int,
) -> bool:
    if user.role == "super_admin":
        return True
    assignments = (
        db.query(RoleAssignment)
        .filter(
            RoleAssignment.user_id == user.id,
            RoleAssignment.is_active.is_(True),
            RoleAssignment.role.in_(roles),
        )
        .all()
    )
    return any(
        _assignment_covers(db, assignment, scope_type, scope_id)
        for assignment in assignments
    )


def can_manage_community_scope(
    db: Session,
    user: User,
    scope_type: str,
    scope_id: int,
) -> bool:
    return has_scoped_role(
        db,
        user,
        {"parish_admin", "diocesan_admin"},
        scope_type,
        scope_id,
    )


def can_review_role_request(
    db: Session,
    reviewer: User,
    requested_role: str,
    scope_type: str,
    scope_id: int,
) -> bool:
    if reviewer.role == "super_admin":
        return True
    if requested_role == "diocesan_admin":
        return False
    if requested_role == "parish_admin":
        return has_scoped_role(
            db,
            reviewer,
            {"diocesan_admin"},
            scope_type,
            scope_id,
        )
    return has_scoped_role(
        db,
        reviewer,
        {"parish_admin", "diocesan_admin"},
        scope_type,
        scope_id,
    )
