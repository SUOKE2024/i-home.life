"""批量产品 Schema — 文件上传 + 批量创建 + AI 文案进度"""

from datetime import datetime
from pydantic import BaseModel, Field


class BatchProductRow(BaseModel):
    """Excel/CSV 中的一行产品数据"""
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(default="other")
    description: str | None = None
    price_min: float | None = None
    price_max: float | None = None
    unit: str = Field(default="个")
    tags: str | None = None  # 逗号分隔的标签字符串，如 "防滑,灰色,客厅"
    stock_status: str = Field(default="in_stock")
    cover_image: str | None = None  # 图片 URL


class BatchProductCreate(BaseModel):
    """批量创建产品请求"""
    products: list[BatchProductRow] = Field(min_length=1, max_length=500)
    ai_assisted: bool = Field(default=True)  # 是否批量生成 AI 文案


class BatchProductResult(BaseModel):
    """单条批量创建结果"""
    row: int  # 行号（从 1 开始）
    name: str
    success: bool
    product_id: str | None = None
    error: str | None = None


class BatchUploadResponse(BaseModel):
    """批量上传/创建响应"""
    total: int
    success_count: int
    failed_count: int
    results: list[BatchProductResult]
    batch_id: str | None = None  # 用于追踪 AI 文案生成进度
    ai_jobs_pending: int = 0     # 待生成的 AI 文案数量


class AIJobStatus(BaseModel):
    """AI 文案生成任务状态"""
    job_id: str
    batch_id: str
    total: int
    completed: int
    failed: int
    in_progress: bool
    created_at: datetime
    updated_at: datetime | None = None
