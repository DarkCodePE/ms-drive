from datetime import datetime
from typing import Optional

from openai import BaseModel
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from app.config.base import Base  # Se asume que Base está definido en tu configuración de la BD


class DriveFolderModel(Base):
    """Modelo para representar las carpetas en la base de datos"""
    __tablename__ = "drive_folders"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    google_drive_folder_id = Column(String, nullable=True, index=True)  # ID de la carpeta en Google Drive (si aplica)
    parent_id = Column(Integer, ForeignKey("drive_folders.id"), nullable=True)  # Referencia a la carpeta padre
    created_at = Column(DateTime, default=datetime.utcnow)

    children = relationship("DriveFolderModel", backref="parent",
                            remote_side=[id])  # Relación recursiva para subcarpetas
    documents = relationship("DriveFileModel", backref="folder")  # Relación con documentos dentro de la carpeta

    def __repr__(self):
        return f"<DriveFolderModel(id={self.id}, name='{self.name}')>"


class DriveFileModel(Base):
    __tablename__ = "drive_files"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    file_id = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String, index=True)
    mime_type = Column(String(255), nullable=False)
    modified_time = Column(DateTime, nullable=False)
    web_view_link = Column(String(1000), nullable=True)
    detected_at = Column(DateTime, nullable=True)
    processed = Column(Boolean, default=False)
    folder_id = Column(Integer, ForeignKey("drive_folders.id"))  # Clave foránea a la carpeta contenedora
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<DriveDocumentModel(id={self.id}, name='{self.name}')>"

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
