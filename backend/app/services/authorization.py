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

CHOIR_RESOURCE_MANAGER_ROLES = {
    "parish_admin",
    "diocesan_admin",
    "parish_music_director",
    "choir_director",
}

# Roles that may act on moderation queues. Moderators are deliberately kept
# separate from administrators: a moderator may hide content and resolve
# reports, but must never inherit role assignment or system configuration.
MODERATOR_ROLES = {
    "moderator",
    "parish_admin",
    "diocesan_admin",
}


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


def scope_contains(
    db: Session,
    ancestor_type: str,
    ancestor_id: int,
    scope_type: str,
    scope_id: int,
) -> bool:
    """Whether ``scope_type/scope_id`` sits at or below ``ancestor_type/ancestor_id``.

    Reports and suggestions are normally scoped to a parish or a group, but the
    people trusted to review them are appointed at diocese, deanery, or parish
    level. Requiring an exact scope match would leave every diocesan and deanery
    moderator locked out of their own queue, so authority is resolved downward
    through the hierarchy instead. It never resolves upward or sideways: a parish
    moderator still cannot reach a sibling parish, and a moderator of one parish
    cannot reach another.
    """
    if ancestor_type == scope_type and ancestor_id == scope_id:
        return True
    if scope_type == "parish":
        parish = db.query(Parish).filter(Parish.id == scope_id).first()
        if parish is None:
            return False
        if ancestor_type == "diocese":
            return parish.diocese_id == ancestor_id
        if ancestor_type == "deanery":
            return parish.deanery_id == ancestor_id
        return False
    if scope_type == "group" and ancestor_type == "parish":
        group = db.query(CommunityGroup).filter(
            CommunityGroup.id == scope_id
        ).first()
        return (
            group is not None
            and group.scope_type == "parish"
            and group.scope_id == ancestor_id
        )
    return False


def can_moderate_community_scope(
    db: Session,
    user: User,
    scope_type: str | None,
    scope_id: int | None,
) -> bool:
    """Whether ``user`` may moderate content belonging to a scope.

    Platform administrators may act anywhere. Everyone else must hold an active
    moderator/administrator assignment whose scope contains the content's scope,
    so a parish moderator can never reach a sibling parish and a diocesan
    moderator can never reach another diocese.
    """
    if user.role == "super_admin":
        return True
    if scope_type is None or scope_id is None:
        return False
    assignments = (
        db.query(RoleAssignment)
        .filter(
            RoleAssignment.user_id == user.id,
            RoleAssignment.is_active.is_(True),
            RoleAssignment.role.in_(MODERATOR_ROLES),
        )
        .all()
    )
    return any(
        assignment.scope_id is not None
        and scope_contains(
            db, assignment.scope_type, assignment.scope_id, scope_type, scope_id
        )
        for assignment in assignments
    )


def can_moderate_platform_content(db: Session, user: User) -> bool:
    """Whether ``user`` may moderate content that has no organizational scope.

    Readings, saints, and choir resources are platform-wide, so a report about
    one carries no parish. Restricting those reports to super admins would leave
    them unreviewable in practice, so a moderator or administrator holding a
    global assignment may action them. Ordinary members never qualify.
    """
    if user.role == "super_admin":
        return True
    return (
        db.query(RoleAssignment.id)
        .filter(
            RoleAssignment.user_id == user.id,
            RoleAssignment.is_active.is_(True),
            RoleAssignment.scope_type == "global",
            RoleAssignment.role.in_(MODERATOR_ROLES),
        )
        .first()
        is not None
    )


def can_review_moderation_report(
    db: Session,
    user: User,
    scope_type: str | None,
    scope_id: int | None,
) -> bool:
    """Combined scope check for a single report."""
    if scope_type is None or scope_id is None:
        return can_moderate_platform_content(db, user)
    return can_moderate_community_scope(db, user, scope_type, scope_id)


def moderation_scope_ids(db: Session, user: User) -> set[tuple[str, int]] | None:
    """Scope pairs ``user`` may moderate, or ``None`` meaning unrestricted.

    Returning ``None`` for a super admin keeps callers simple: they can skip
    scope filtering entirely rather than materialising the whole hierarchy.
    """
    if user.role == "super_admin":
        return None
    assignments = (
        db.query(RoleAssignment)
        .filter(
            RoleAssignment.user_id == user.id,
            RoleAssignment.is_active.is_(True),
            RoleAssignment.role.in_(MODERATOR_ROLES),
        )
        .all()
    )
    if not assignments:
        return set()
    scopes: set[tuple[str, int]] = set()
    for assignment in assignments:
        if assignment.scope_type == "global":
            return None
        if assignment.scope_id is None:
            continue
        scopes.add((assignment.scope_type, assignment.scope_id))
        if assignment.scope_type in {"diocese", "deanery"}:
            # Expand to the concrete parish rows so a report queue query can be
            # expressed as a single scoped filter instead of a per-report check.
            parish_ids = [
                parish_id
                for (parish_id,) in db.query(Parish.id).filter(
                    Parish.diocese_id == assignment.scope_id
                    if assignment.scope_type == "diocese"
                    else Parish.deanery_id == assignment.scope_id
                ).all()
            ]
            scopes.update(("parish", parish_id) for parish_id in parish_ids)
            if assignment.scope_type == "diocese":
                scopes.update(
                    ("deanery", deanery_id)
                    for (deanery_id,) in db.query(Deanery.id)
                    .filter(Deanery.diocese_id == assignment.scope_id)
                    .all()
                )
        elif assignment.scope_type == "parish":
            parish_ids = [assignment.scope_id]
        else:
            parish_ids = []
        if parish_ids:
            # Groups are moderated by whoever moderates the parish that owns them,
            # which ``scope_contains`` already allows. The queue query has to name
            # those group rows explicitly or a parish moderator sees reports about
            # the parish but not about its groups.
            scopes.update(
                ("group", group_id)
                for (group_id,) in db.query(CommunityGroup.id)
                .filter(
                    CommunityGroup.scope_type == "parish",
                    CommunityGroup.scope_id.in_(parish_ids),
                )
                .all()
            )
    return scopes


def can_manage_choir_resource_scope(
    db: Session,
    user: User,
    parish_id: int | None,
) -> bool:
    if user.role == "super_admin":
        return True
    if parish_id is None and user.role == "admin":
        return True
    return bool(
        parish_id is not None
        and scope_exists(db, "parish", parish_id)
        and has_scoped_role(
            db,
            user,
            CHOIR_RESOURCE_MANAGER_ROLES,
            "parish",
            parish_id,
        )
    )


def manageable_choir_parish_ids(db: Session, user: User) -> list[int]:
    if user.role == "super_admin":
        return [
            parish_id
            for (parish_id,) in db.query(Parish.id).order_by(Parish.id).all()
        ]

    assignments = (
        db.query(RoleAssignment)
        .filter(
            RoleAssignment.user_id == user.id,
            RoleAssignment.is_active.is_(True),
            RoleAssignment.role.in_(CHOIR_RESOURCE_MANAGER_ROLES),
        )
        .all()
    )
    parish_ids: set[int] = set()
    for assignment in assignments:
        if assignment.scope_type == "global":
            return [
                parish_id
                for (parish_id,) in db.query(Parish.id).order_by(Parish.id).all()
            ]
        if assignment.scope_type == "parish" and assignment.scope_id is not None:
            parish_ids.add(assignment.scope_id)
        elif assignment.scope_type == "deanery" and assignment.scope_id is not None:
            parish_ids.update(
                parish_id
                for (parish_id,) in db.query(Parish.id).filter(
                    Parish.deanery_id == assignment.scope_id
                ).all()
            )
        elif assignment.scope_type == "diocese" and assignment.scope_id is not None:
            parish_ids.update(
                parish_id
                for (parish_id,) in db.query(Parish.id).filter(
                    Parish.diocese_id == assignment.scope_id
                ).all()
            )
    existing_parish_ids = {
        parish_id
        for (parish_id,) in db.query(Parish.id).filter(
            Parish.id.in_(parish_ids)
        ).all()
    } if parish_ids else set()
    return sorted(existing_parish_ids)


def can_view_choir_resource(
    db: Session,
    user: User | None,
    parish_id: int | None,
) -> bool:
    if parish_id is None:
        return True
    if user is None:
        return False
    return user_belongs_to_scope(db, user, "parish", parish_id) or (
        can_manage_choir_resource_scope(db, user, parish_id)
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
