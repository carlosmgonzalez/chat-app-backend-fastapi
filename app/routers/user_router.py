from fastapi import APIRouter, Depends, HTTPException, status
from app.db.session import get_session
from sqlmodel import Session, select
from app.models.user_model import User
from app.models.common_model import UserResponse

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=UserResponse)
async def get_user_by_email(email: str, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with email {email} not found",
        )
    return user
