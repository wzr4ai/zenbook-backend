"""Authentication routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.security import create_access_token
from src.modules.auth.schemas import LoginRequest, PhoneLoginRequest, SmsCodeRequest, TokenResponse
from src.modules.auth.sms import request_sms_code, validate_sms_code
from src.modules.users.models import User
from src.shared.enums import UserRole

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
PHONE_OPENID_PREFIX = "phone:"


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


@router.post("/sms")
async def send_sms_code(payload: SmsCodeRequest) -> dict[str, str]:
    phone = payload.phone_number.strip()
    if not phone:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid phone number")
    request_sms_code(phone)
    return {"status": "sent"}


@router.post("/login/phone", response_model=TokenResponse)
async def login_with_phone(payload: PhoneLoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Create or fetch a user by phone number and issue a JWT."""
    phone = payload.phone_number.strip()
    if not phone:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid phone number")
    verification_code = payload.verification_code.strip()
    if not verification_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing verification code")
    validate_sms_code(phone, verification_code)

    result = await db.execute(select(User).where(User.phone_number == phone))
    user = result.scalar_one_or_none()
    if user is None:
        phone_openid = f"{PHONE_OPENID_PREFIX}{phone}"
        user = User(
            wechat_openid=phone_openid,
            role=UserRole.CUSTOMER,
            display_name=f"phone_{phone[-4:]}",
            phone_number=phone,
        )
        db.add(user)
    else:
        if user.phone_number != phone:
            user.phone_number = phone
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.user_id, user.role)
    return TokenResponse(token=token, user_info=user)
