from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Form, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import io

from app.database import get_db
from app.models.user import User
from app.models.file_attachment import FileAttachment
from app.schemas.file_attachment import FileAttachmentResponse, FileAttachmentListItem
from app.auth import get_current_user

router = APIRouter(prefix="/files", tags=["文件"])


@router.post("/upload", response_model=FileAttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    project_id: str = Form(...),
    category: str = Form(default="other"),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    contents = await file.read()
    attachment = FileAttachment(
        project_id=project_id,
        filename=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream",
        file_size=len(contents),
        category=category,
        file_data=contents,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return FileAttachmentResponse.model_validate(attachment)


@router.get("/project/{project_id}", response_model=list[FileAttachmentListItem])
async def list_files(
    project_id: str,
    category: str = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(FileAttachment).where(FileAttachment.project_id == project_id)
    if category:
        query = query.where(FileAttachment.category == category)
    result = await db.execute(query.order_by(FileAttachment.created_at.desc()))
    attachments = result.scalars().all()
    return [FileAttachmentListItem.model_validate(a) for a in attachments]


@router.get("/download/{attachment_id}")
async def download_file(
    attachment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(FileAttachment).where(FileAttachment.id == attachment_id))
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    return StreamingResponse(
        io.BytesIO(attachment.file_data),
        media_type=attachment.content_type,
        headers={"Content-Disposition": f'inline; filename="{attachment.filename}"'},
    )


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    attachment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(FileAttachment).where(FileAttachment.id == attachment_id))
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    await db.delete(attachment)
    await db.commit()
