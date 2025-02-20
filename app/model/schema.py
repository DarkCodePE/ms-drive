from pydantic import BaseModel

from typing import Optional, List, Dict, Any


class DocumentStructure(BaseModel):
    id: int
    file_id: str
    name: str
    mime_type: str


class FolderStructure(BaseModel):
    id: int
    name: str
    google_drive_folder_id: Optional[str]
    parent_id: Optional[str]  # Now parent_id is String
    children: List["FolderStructure"] = []  # Forward reference for recursive type
    documents: List[DocumentStructure] = []

    class Config:
        orm_mode = True  # To allow creation from ORM objects


FolderStructure.update_forward_refs()  # Resolve forward reference after class definition


class RootStructureResponse(BaseModel):
    root_folders: List[FolderStructure]


class FolderStructureResponse(BaseModel):
    folder: FolderStructure
