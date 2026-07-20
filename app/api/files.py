from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Form, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import io

from app.database import get_db
from app.models.user import User
from app.schemas.file_attachment import FileAttachmentResponse, FileAttachmentListItem
from app.auth import get_current_user
from app.rbac import verify_project_collaborator_access
from app.services.file_service import (
    upload_file as _svc_upload_file,
    list_project_files,
    get_file,
    delete_file as _svc_delete_file,
)

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
    # 项目协作权限检查（F40 三方协作：允许 designer/contractor/supplier 上传文件）
    await verify_project_collaborator_access(project_id=project_id, current_user=current_user, db=db)
    contents = await file.read()
    attachment = await _svc_upload_file(
        db,
        project_id=project_id,
        filename=file.filename or "unnamed",
        file_data=contents,
        content_type=file.content_type or "application/octet-stream",
        category=category,
    )
    return FileAttachmentResponse.model_validate(attachment)


@router.get("/project/{project_id}", response_model=list[FileAttachmentListItem])
async def list_files(
    project_id: str,
    category: str = Query(default=None),
    skip: int = Query(0, ge=0, description="分页偏移量"),
    limit: int = Query(100, ge=1, le=500, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出项目附件（v1.1.14: 支持 skip/limit 分页）"""
    await verify_project_collaborator_access(project_id=project_id, current_user=current_user, db=db)
    attachments = await list_project_files(db, project_id, category=category, skip=skip, limit=limit)
    return [FileAttachmentListItem.model_validate(a) for a in attachments]


@router.get("/download/{attachment_id}")
async def download_file(
    attachment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    attachment = await get_file(db, attachment_id)
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    await verify_project_collaborator_access(project_id=attachment.project_id, current_user=current_user, db=db)
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
    # 先获取文件以验证权限
    attachment = await get_file(db, attachment_id)
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    await verify_project_collaborator_access(project_id=attachment.project_id, current_user=current_user, db=db)
    await _svc_delete_file(db, attachment_id)
