from datetime import datetime

from pydantic import BaseModel


class FileAttachmentResponse(BaseModel):
    id: str
    project_id: str
    filename: str
    content_type: str
    file_size: int
    category: str
    created_at: datetime

    model_config = {"from_attributes": True}


class FileAttachmentListItem(BaseModel):
    id: str
    project_id: str
    filename: str
    content_type: str
    file_size: int
    category: str
    created_at: datetime

    model_config = {"from_attributes": True}
