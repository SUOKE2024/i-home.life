import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    total_area: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # draft / active / completed / cancelled

    # 项目类型：整装/硬装/软装/窗帘定制/厨卫改造/其他
    project_type: Mapped[str] = mapped_column(String(30), nullable=False, default="full_renovation")
    # full_renovation(整装) / hard_decoration(硬装) / soft_furnishing(软装) /
    # curtain(窗帘定制) / kitchen(厨房改造) / bathroom(卫浴改造) / custom

    # AR 测量来源
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    # manual / ar_measure
    scan_session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    owner = relationship("User", back_populates="projects")
    floors = relationship("Floor", back_populates="project", cascade="all, delete-orphan")
    bom_items = relationship("BOMItem", back_populates="project", cascade="all, delete-orphan")
    change_orders = relationship("ChangeOrder", back_populates="project", cascade="all, delete-orphan")


class Floor(Base):
    __tablename__ = "floors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    floor_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    area: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    project = relationship("Project", back_populates="floors")
    rooms = relationship("Room", back_populates="floor", cascade="all, delete-orphan")


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    floor_id: Mapped[str] = mapped_column(String(36), ForeignKey("floors.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    room_type: Mapped[str] = mapped_column(String(50), nullable=False, default="bedroom")
    area: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[float | None] = mapped_column(Float, nullable=True)
    height: Mapped[float | None] = mapped_column(Float, nullable=True)
    length: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    floor = relationship("Floor", back_populates="rooms")
