from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class DriveFile(BaseModel):
    """Schema for Google Drive file metadata"""
    id: str
    name: str
    mimeType: str
    modifiedTime: str
    webViewLink: Optional[str] = None
    detected_at: Optional[str] = None


class MonitoringStatus(BaseModel):
    """Schema for monitoring status response"""
    is_running: bool
    folder_id: str
    last_check: Optional[datetime] = None
    files_processed: int


class ServiceStatus(BaseModel):
    """Schema for service status response"""
    status: str
    version: str
    google_drive_connected: bool
    monitoring_active: bool
    folder_id: Optional[str] = None
