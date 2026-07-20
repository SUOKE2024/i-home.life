"""文件附件 Service — 文件上传/下载/删除操作"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.file_attachment import FileAttachment


async def upload_file(
    db: AsyncSession,
    project_id: str,
    filename: str,
    file_data: bytes,
    content_type: str = "application/octet-stream",
    category: str = "other",
    message_id: str | None = None,
) -> FileAttachment:
    attachment = FileAttachment(
        project_id=project_id,
        message_id=message_id,
        filename=filename,
        content_type=content_type,
        file_size=len(file_data),
        category=category,
        file_data=file_data,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return attachment


async def get_file(db: AsyncSession, file_id: str) -> FileAttachment | None:
    """获取文件完整信息（含二进制数据）"""
    result = await db.execute(
        select(FileAttachment).where(FileAttachment.id == file_id)
    )
    return result.scalar_one_or_none()


async def get_file_metadata(
    db: AsyncSession, file_id: str,
) -> FileAttachment | None:
    """获取文件元数据（不含二进制数据）"""
    result = await db.execute(
        select(FileAttachment).where(FileAttachment.id == file_id)
    )
    return result.scalar_one_or_none()


async def list_project_files(
    db: AsyncSession,
    project_id: str,
    category: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[FileAttachment]:
    stmt = (
        select(FileAttachment)
        .where(FileAttachment.project_id == project_id)
        .order_by(FileAttachment.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    if category:
        stmt = stmt.where(FileAttachment.category == category)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def delete_file(db: AsyncSession, file_id: str) -> bool:
    attachment = await get_file(db, file_id)
    if not attachment:
        return False
    await db.delete(attachment)
    await db.commit()
    return True
