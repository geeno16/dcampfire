from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.common.database import Base


class Bonfire(Base):
    __tablename__ = "bonfires"
    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    owner_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    color: Mapped[str] = mapped_column(String(32), nullable=False)
    is_open: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    album_url: Mapped[str | None] = mapped_column(String(2048))
    album_title: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class BonfireTopic(Base):
    __tablename__ = "bonfire_topics"
    bonfire_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("bonfires.id", ondelete="CASCADE"),
        primary_key=True,
    )
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )
