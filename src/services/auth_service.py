import os
import uuid
from datetime import datetime, timedelta
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
from models.user import User, UserCreate, UserLogin, Token, TokenData
from services.dynamodb_service import DynamoDBService


class AuthService:
    def __init__(self):
        self.db = DynamoDBService()
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.secret_key = os.environ.get('JWT_SECRET', 'your-secret-key-change-in-production')
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 60 * 24 * 7  # 7 days

    def _hash_password(self, password: str) -> str:
        """Hash a password"""
        # Ensure password is properly encoded (bcrypt has 72 byte limit)
        # Truncate if necessary to avoid bcrypt errors
        if len(password.encode('utf-8')) > 72:
            password = password[:72]
        return self.pwd_context.hash(password)

    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return self.pwd_context.verify(plain_password, hashed_password)

    def _create_access_token(self, data: dict) -> str:
        """Create a JWT access token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def register_user(self, user_create: UserCreate) -> Token:
        """Register a new user"""
        # Check if user already exists
        existing = self.db.query_gsi('GSI1', f"EMAIL#{user_create.email}")
        if existing:
            raise ValueError("Email already registered")

        user_id = str(uuid.uuid4())
        now = datetime.utcnow()

        user_data = {
            'PK': f'USER#{user_id}',
            'SK': f'PROFILE',
            'GSI1PK': f'EMAIL#{user_create.email}',
            'GSI1SK': f'USER#{user_id}',
            'user_id': user_id,
            'email': user_create.email,
            'full_name': user_create.full_name,
            'hashed_password': self._hash_password(user_create.password),
            'is_active': True,
            'created_at': now.isoformat(),
            'updated_at': now.isoformat(),
        }

        self.db.put_item(user_data)

        user = User(
            user_id=user_id,
            email=user_create.email,
            full_name=user_create.full_name,
            created_at=now,
            updated_at=now,
            is_active=True
        )

        access_token = self._create_access_token(
            data={"user_id": user_id, "email": user_create.email}
        )

        return Token(access_token=access_token, user=user)

    def login_user(self, user_login: UserLogin) -> Token:
        """Authenticate and login a user"""
        users = self.db.query_gsi('GSI1', f"EMAIL#{user_login.email}")

        if not users:
            raise ValueError("Invalid email or password")

        user_data = users[0]

        if not self._verify_password(user_login.password, user_data['hashed_password']):
            raise ValueError("Invalid email or password")

        if not user_data.get('is_active', False):
            raise ValueError("User account is inactive")

        user = User(
            user_id=user_data['user_id'],
            email=user_data['email'],
            full_name=user_data.get('full_name'),
            created_at=datetime.fromisoformat(user_data['created_at']),
            updated_at=datetime.fromisoformat(user_data['updated_at']),
            is_active=user_data['is_active']
        )

        access_token = self._create_access_token(
            data={"user_id": user.user_id, "email": user.email}
        )

        return Token(access_token=access_token, user=user)

    def verify_token(self, token: str) -> TokenData:
        """Verify and decode a JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            user_id: str = payload.get("user_id")
            email: str = payload.get("email")

            if user_id is None or email is None:
                raise ValueError("Invalid token")

            return TokenData(user_id=user_id, email=email)
        except JWTError:
            raise ValueError("Invalid token")

    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        user_data = self.db.get_item(f'USER#{user_id}', 'PROFILE')

        if not user_data:
            return None

        return User(
            user_id=user_data['user_id'],
            email=user_data['email'],
            full_name=user_data.get('full_name'),
            created_at=datetime.fromisoformat(user_data['created_at']),
            updated_at=datetime.fromisoformat(user_data['updated_at']),
            is_active=user_data['is_active']
        )
