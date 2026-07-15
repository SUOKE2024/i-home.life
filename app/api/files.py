from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Form, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import io

from app.database import get_db
from app.models.user import User
from app.models.file_attachment import FileAttachment
from app.models.project import Project
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
    # 文件大小限制 20MB
    ALLOWED_CONTENT_TYPES = {
        "image/jpeg", "image/png", "image/webp", "image/gif",
        "application/pdf", "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/plain", "application/zip",
        "application/octet-stream",
        "model/vnd.usdz+zip", "model/gltf-binary", "model/gltf+json",
    }
    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"不支持的文件类型: {file.content_type}")
    # 项目归属权检查
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if current_user.role != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
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
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if current_user.role != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
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
    # 项目归属权检查
    result = await db.execute(select(Project).where(Project.id == attachment.project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if current_user.role != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
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
    # 项目归属权检查
    result = await db.execute(select(Project).where(Project.id == attachment.project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if current_user.role != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    await db.delete(attachment)
    await db.commit()
