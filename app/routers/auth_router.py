from typing import Annotated
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import (
    OAuth2PasswordBearer,
    OAuth2PasswordRequestForm,
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel
from app.db.session import get_session
from app.models.user_model import User, UserCreate
from app.models.common_model import UserResponse
from sqlmodel import select, Session
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from app.core.env_config import env
import jwt

SECRET_KEY = env.SECRET_KEY
ALGORITHM = env.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = env.ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter(prefix="/auth")


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    id: uuid.UUID
    email: str
    name: str


bcrypt = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
security = HTTPBearer()


def verify_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
):
    try:
        token = credentials.credentials

        payload = jwt.decode(token, SECRET_KEY, algorithms=ALGORITHM)

        user_id = payload.get("id")
        email = payload.get("email")
        name = payload.get("name")

        if user_id is None or email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return TokenData(id=uuid.UUID(user_id), email=email, name=name)

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )


def verify_password(plain_password: str, hashed_password: str):
    return bcrypt.verify(plain_password, hashed_password)


def get_password_hash(password: str):
    return bcrypt.hash(password)


def create_access_token(data: dict[str, str | datetime], expires_delta: timedelta):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, key=SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_user_from_token(token: str) -> TokenData:
    """
    Decodifica un token para obtener los datos del usuario.
    Lanza ValueError si el token es inválido o ha expirado.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("id")
        email = payload.get("email")
        name = payload.get("name")

        if user_id is None or email is None:
            raise ValueError("Token inválido: faltan datos del usuario.")

        return TokenData(id=uuid.UUID(user_id), email=email, name=name)

    except jwt.InvalidTokenError as e:
        raise ValueError(f"Token inválido o expirado: {e}") from e


def get_user(email: str, session: Session) -> User | None:
    user = session.exec(select(User).where(User.email == email)).first()
    if user:
        return user
    return None


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[Session, Depends(get_session)],
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, key=SECRET_KEY, algorithms=ALGORITHM)
        email = payload.get("email")
        if email is None:
            raise credentials_exception
    except InvalidTokenError:
        raise credentials_exception
    user = get_user(email=email, session=session)
    if user is None:
        raise credentials_exception
    return user


def authenticate_user(email: str, password: str, session: Session) -> User | None:
    user = get_user(email, session)
    if user:
        is_correct_password = verify_password(password, user.hashed_password)
        if is_correct_password:
            return user
    return None


@router.post("/token")
async def login_for_access_token(
    *,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[Session, Depends(get_session)],
) -> Token:
    """
    Endpoint para obtener un token de acceso usando email y password.
    Este ES el endpoint de login principal.
    """
    user = authenticate_user(
        email=form_data.username, password=form_data.password, session=session
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"id": str(user.id), "email": user.email, "name": user.name},
        expires_delta=access_token_expires,
    )
    return Token(access_token=access_token, token_type="bearer")


@router.post("/register")
def register(
    *, user_create: UserCreate, session: Annotated[Session, Depends(get_session)]
):
    user_in_db = session.exec(
        select(User).where((User.email == user_create.email))
    ).first()
    if user_in_db:
        raise HTTPException(status_code=400, detail="Email already exists")

    hashed_password = get_password_hash(user_create.password)

    user = User(
        name=user_create.name, email=user_create.email, hashed_password=hashed_password
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
    )


@router.get("/me", response_model=UserResponse)
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Obtener información del usuario actual"""
    return UserResponse(
        id=current_user.id, name=current_user.name, email=current_user.email
    )
