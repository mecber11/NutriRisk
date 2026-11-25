"""User and role administration (Administrador only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select

from app.core.deps import DbSession, PageParams, paginated, require_permission
from app.core.rbac import Action, Module, RoleCode, permissions_for_role
from app.core.security import PasswordPolicyError, hash_password, validate_password_strength
from app.models.user import Role, User
from app.schemas.auth import AdminPasswordReset, PermissionMatrix, RoleOut, UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["Usuarios y roles"])
AdminOnly = Depends(require_permission(Module.USERS, Action.READ))


def _serialize(user: User) -> UserOut:
    return UserOut.model_validate(user)


@router.get("/roles", response_model=list[RoleOut], summary="Listar roles")
def list_roles(db: DbSession, _: User = AdminOnly) -> list[RoleOut]:
    roles = db.execute(select(Role).order_by(Role.id)).scalars().all()
    return [RoleOut.model_validate(role) for role in roles]


@router.get("/permissions", response_model=PermissionMatrix, summary="Matriz de permisos por rol")
def permission_matrix(db: DbSession, _: User = AdminOnly) -> PermissionMatrix:
    roles = db.execute(select(Role).order_by(Role.id)).scalars().all()
    matrix = {role.code: permissions_for_role(role.code) for role in roles}
    modules = sorted({module for role in matrix.values() for module in role})
    actions = sorted({action for role in matrix.values() for action_list in role.values() for action in action_list})
    return PermissionMatrix(
        roles=[RoleOut.model_validate(role) for role in roles],
        modules=modules,
        actions=actions,
        matrix={code: {module: sorted(actions) for module, actions in value.items()} for code, value in matrix.items()},
    )


@router.get("", summary="Listar usuarios")
def list_users(
    db: DbSession,
    _: User = AdminOnly,
    page: PageParams = None,  # type: ignore[assignment]
    search: str | None = Query(default=None, description="Buscar por nombre o correo"),
    role_code: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
) -> dict:
    page = page or PageParams()
    stmt = select(User)
    count_stmt = select(func.count(User.id))
    conditions = []
    if search:
        pattern = f"%{search.lower()}%"
        conditions.append(or_(func.lower(User.email).like(pattern), func.lower(User.full_name).like(pattern)))
    if role_code:
        conditions.append(User.role.has(Role.code == role_code))
    if is_active is not None:
        conditions.append(User.is_active.is_(is_active))
    if conditions:
        stmt = stmt.where(*conditions)
        count_stmt = count_stmt.where(*conditions)
    total = db.scalar(count_stmt) or 0
    users = db.execute(stmt.order_by(User.id).offset(page.offset).limit(page.limit)).scalars().all()
    return paginated([_serialize(user).model_dump() for user in users], total, page.page, page.page_size)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED, summary="Crear usuario")
def create_user(payload: UserCreate, db: DbSession, actor: User = Depends(require_permission(Module.USERS, Action.CREATE))) -> UserOut:
    if db.scalar(select(User).where(User.email == payload.email.lower())):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El correo ya está registrado")
    role = db.scalar(select(Role).where(Role.code == payload.role_code))
    if role is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Rol inválido")
    try:
        validate_password_strength(payload.password)
    except PasswordPolicyError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role_id=role.id,
        is_active=payload.is_active,
        organization=payload.organization,
        position=payload.position,
        phone=payload.phone,
        must_change_password=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _serialize(user)


@router.get("/{user_id}", response_model=UserOut, summary="Detalle de usuario")
def get_user(user_id: int, db: DbSession, _: User = AdminOnly) -> UserOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    return _serialize(user)


@router.patch("/{user_id}", response_model=UserOut, summary="Actualizar usuario")
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: DbSession,
    actor: User = Depends(require_permission(Module.USERS, Action.UPDATE)),
) -> UserOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    data = payload.model_dump(exclude_unset=True)
    role_code = data.pop("role_code", None)
    if role_code:
        role = db.scalar(select(Role).where(Role.code == role_code))
        if role is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Rol inválido")
        user.role_id = role.id
    if user.id == actor.id and data.get("is_active") is False:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No puede desactivar su propia cuenta")
    for field, value in data.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return _serialize(user)


@router.delete("/{user_id}", response_model=UserOut, summary="Desactivar usuario")
def deactivate_user(
    user_id: int,
    db: DbSession,
    actor: User = Depends(require_permission(Module.USERS, Action.DELETE)),
) -> UserOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    if user.id == actor.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No puede desactivar su propia cuenta")
    user.is_active = False
    db.commit()
    db.refresh(user)
    return _serialize(user)


@router.post("/{user_id}/reset-password", summary="Restablecer contraseña (administrador)")
def admin_reset_password(
    user_id: int,
    payload: AdminPasswordReset,
    db: DbSession,
    _: User = Depends(require_permission(Module.USERS, Action.UPDATE)),
) -> dict[str, str]:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    try:
        validate_password_strength(payload.new_password)
    except PasswordPolicyError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    user.hashed_password = hash_password(payload.new_password)
    user.must_change_password = payload.must_change_password
    user.failed_login_count = 0
    user.locked_until = None
    db.commit()
    return {"message": "Contraseña restablecida"}


@router.get("/meta/roles", response_model=list[RoleOut], summary="Roles disponibles (compatibilidad)")
def roles_alias(db: DbSession, _: User = AdminOnly) -> list[RoleOut]:
    roles = db.execute(select(Role).order_by(Role.id)).scalars().all()
    return [RoleOut.model_validate(role) for role in roles]


_ = RoleCode  # keep import for type reference in documentation

