# src/core/security.py
from datetime import datetime, timedelta
from typing import Optional, List
from enum import Enum
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
import redis.asyncio as redis
from src.core.config import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

# Redis for token blacklist
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int

class TokenData(BaseModel):
    username: Optional[str] = None
    roles: List[str] = []
    campus_id: Optional[str] = None

class UserInDB(BaseModel):
    username: str
    email: str
    full_name: str
    roles: List[str]
    campus_id: str
    disabled: bool = False
    hashed_password: str

class Role(str, Enum):
    STUDENT = "student"
    FACULTY = "faculty"
    STAFF = "staff"
    ADMIN = "admin"
    SUPPORT = "support"

# Permission definitions
PERMISSIONS = {
    Role.STUDENT: [
        "course:view",
        "equipment:book",
        "support:ticket:create",
        "support:ticket:view_own"
    ],
    Role.FACULTY: [
        "course:create",
        "course:edit",
        "schedule:view",
        "equipment:book",
        "support:ticket:create",
        "support:ticket:view_department"
    ],
    Role.STAFF: [
        "equipment:manage",
        "facilities:manage",
        "energy:view",
        "support:ticket:manage",
        "support:ticket:assign"
    ],
    Role.ADMIN: ["*"],  # All permissions
    Role.SUPPORT: [
        "support:ticket:view_all",
        "support:ticket:update",
        "support:ticket:escalate",
        "support:faq:manage"
    ]
}

class AuthService:
    def __init__(self):
        self.secret_key = settings.SECRET_KEY
        self.algorithm = settings.ALGORITHM
        self.access_token_expire = 30  # minutes
        self.refresh_token_expire = 7  # days
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def create_refresh_token(self, data: dict):
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire)
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    async def verify_token(self, token: str, token_type: str = "access") -> Optional[TokenData]:
        """Verify token and return token data"""
        try:
            # Check if token is blacklisted
            if await redis_client.get(f"blacklist:{token}"):
                return None
            
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            if payload.get("type") != token_type:
                return None
            
            username: str = payload.get("sub")
            roles: List[str] = payload.get("roles", [])
            campus_id: str = payload.get("campus_id")
            
            if username is None:
                return None
            
            return TokenData(username=username, roles=roles, campus_id=campus_id)
            
        except JWTError:
            return None
    
    async def blacklist_token(self, token: str):
        """Add token to blacklist"""
        await redis_client.setex(f"blacklist:{token}", 86400, "1")  # 24 hours
    
    def hash_password(self, password: str) -> str:
        return pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)
    
    def check_permission(self, user_roles: List[str], required_permission: str) -> bool:
        """Check if user has required permission"""
        for role in user_roles:
            if role not in PERMISSIONS:
                continue
            perms = PERMISSIONS[role]
            if "*" in perms or required_permission in perms:
                return True
        return False

# Dependency to get current user
async def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    auth_service = AuthService()
    token_data = await auth_service.verify_token(token)
    
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return token_data

# Permission dependency
def require_permission(permission: str):
    async def permission_dependency(current_user: TokenData = Depends(get_current_user)):
        auth_service = AuthService()
        if not auth_service.check_permission(current_user.roles, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return permission_dependency