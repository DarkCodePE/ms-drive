from typing import Optional

from openai import BaseModel
from sqlalchemy import Column, String, DateTime, Integer
from app.config.base import Base  # Se asume que Base está definido en tu configuración de la BD


class DriveFileModel(Base):
    __tablename__ = "drive_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(500), nullable=False)
    mime_type = Column(String(255), nullable=False)
    modified_time = Column(DateTime, nullable=False)
    web_view_link = Column(String(1000), nullable=True)
    detected_at = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "file_id": self.file_id,
            "name": self.name,
            "mime_type": self.mime_type,
            "modified_time": self.modified_time.isoformat() if self.modified_time else None,
            "web_view_link": self.web_view_link,
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
        }


class DriveFile(BaseModel):
    id: str
    name: str
    mimeType: str
    modifiedTime: Optional[str] = None
    webViewLink: Optional[str] = None

    class Config:
        from_attributes = True
