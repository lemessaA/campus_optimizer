# src/api/auth_routes.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from src.core.security import AuthService, Token, TokenData, require_permission, oauth2_scheme, get_current_user
from src.services.database import get_db
from src.database import crud

router = APIRouter(prefix="/auth", tags=["authentication"])
auth_service = AuthService()

@router.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login and get access token"""
    async with get_db() as db:
        user = await crud.get_user_by_username(db, form_data.username)
        
        if not user or not auth_service.verify_password(form_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if user.disabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )
        
        # Create tokens
        access_token = auth_service.create_access_token(
            data={
                "sub": user.username,
                "roles": user.roles,
                "campus_id": user.campus_id
            }
        )
        
        refresh_token = auth_service.create_refresh_token(
            data={
                "sub": user.username,
                "roles": user.roles,
                "campus_id": user.campus_id
            }
        )
        
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=30 * 60  # 30 minutes in seconds
        )

@router.post("/refresh")
async def refresh_token(refresh_token: str):
    """Get new access token using refresh token"""
    token_data = await auth_service.verify_token(refresh_token, "refresh")
    
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Create new access token
    new_access_token = auth_service.create_access_token(
        data={
            "sub": token_data.username,
            "roles": token_data.roles,
            "campus_id": token_data.campus_id
        }
    )
    
    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": 30 * 60
    }

@router.post("/logout")
async def logout(token: str = Depends(oauth2_scheme)):
    """Logout and invalidate token"""
    await auth_service.blacklist_token(token)
    return {"message": "Successfully logged out"}

@router.post("/register")
async def register(
    username: str,
    password: str,
    email: str,
    full_name: str,
    role: str = "student",
    campus_id: str = "main"
):
    """Register new user"""
    async with get_db() as db:
        # Check if user exists
        existing = await crud.get_user_by_username(db, username)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
            )
        
        # Create user
        hashed_password = auth_service.hash_password(password)
        user = await crud.create_user(
            db,
            username=username,
            hashed_password=hashed_password,
            email=email,
            full_name=full_name,
            roles=[role],
            campus_id=campus_id
        )
        
        return {
            "message": "User created successfully",
            "username": user.username
        }

@router.get("/me")
async def get_current_user_info(current_user: TokenData = Depends(get_current_user)):
    """Get current user information"""
    return current_user