from typing import Union

from fastapi import Depends
from fastapi import HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from jose import JWTError
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

import settings
from db.dals import UserDAL
from db.models import User, PortalRole
from db.session import get_db
from hashing import Hasher

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login/token")


async def _get_user_by_email_for_auth(email: str, session: AsyncSession):
    async with session.begin():
        user_dal = UserDAL(session)
        return await user_dal.get_user_by_email(
            email=email,
        )


async def authenticate_user(
    email: str, password: str, db: AsyncSession
) -> Union[User, None]:
    user = await _get_user_by_email_for_auth(email=email, session=db)
    if user is None:
        return
    if not Hasher.verify_password(password, user.hashed_password):
        return
    return user


async def get_current_user_from_token(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        email: str = payload.get("sub")
        if email is None:
            logger.error('Отсутсвует почта')
            raise credentials_exception
    except JWTError:
        logger.error(JWTError)
        raise credentials_exception
    user = await _get_user_by_email_for_auth(email=email, session=db)
    if user is None:
        logger.error(f'Пользователь не найден {email}')
        raise credentials_exception
    if PortalRole.ROLE_PORTAL_SUPERADMIN not in user.roles and PortalRole.ROLE_PORTAL_ADMIN not in user.roles:
        logger.error(f'Пользователь {user.name} {user.surname} не имеет достаточно прав')
        raise credentials_exception

    return user
