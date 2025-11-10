"""Authentication routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.security import create_access_token
from src.modules.auth.schemas import LoginRequest, TokenResponse
from src.modules.auth.wechat import exchange_code_for_openid
from src.modules.users.models import User
from src.shared.enums import UserRole

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Exchange a WeChat login code for a JWT."""
    code = payload.code.strip()
    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid code")

    openid = await exchange_code_for_openid(code)
    result = await db.execute(select(User).where(User.wechat_openid == openid))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            wechat_openid=openid,
            role=UserRole.CUSTOMER,
            display_name=f"wx_{openid[-4:]}",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        await db.commit()

    token = create_access_token(user.user_id, user.role)
    return TokenResponse(token=token, user_info=user)
