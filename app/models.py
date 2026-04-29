import uuid
from datetime import datetime
from secrets import token_hex

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Tenant(Base):
    __tablename__ = "tenant"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255))
    api_key: Mapped[str] = mapped_column(
        String(64), unique=True, default=lambda: token_hex(32)
    )
    signing_secret: Mapped[str] = mapped_column(
        String(64), unique=True, default=lambda: token_hex(32)
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
