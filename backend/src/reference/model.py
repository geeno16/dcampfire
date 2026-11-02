from sqlalchemy import SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from src.common.database import Base


class Topic(Base):
    __tablename__ = "topics"
    id: Mapped[int] = mapped_column(
        SmallInteger, primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
