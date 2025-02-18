from typing import Optional

from pydantic import BaseModel


class FolderCreate(BaseModel):
    name: str
    parent_folder_id: Optional[int] = None