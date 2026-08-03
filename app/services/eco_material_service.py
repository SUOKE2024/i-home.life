"""F44 环保材料库标签服务层 — 材料环保等级 ENF/E0/E1 + 绿色认证 + 合规校验

对标 PRD v3.1 F44（2026-08-03 行业调研新增）：
近九成消费者首选环保建材，环保为硬性刚需；
材料 SKU 增加 ENF/E0 环保等级与绿色建材认证字段与筛选（强化 HC-003 环保等级硬约束）。
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.eco_material import MaterialEcoCert
from app.models.material import Material

# 环保等级（ENF > E0 > E1），国标 GB/T 39600-2021 人造板甲醛释放分级
ECO_GRADES = ["ENF", "E0", "E1"]
GRADE_RANK = {"ENF": 3, "E0": 2, "E1": 1}

# 对标 HC-003 环保等级硬约束
COMPLIANCE_REQUIREMENT = "HC-003 环保等级硬约束"


def valid_compliance(eco_grade: str, certification: str) -> bool:
    """环保合规判定：ENF/E0 且具备认证（非"无认证"）为合规（对标 HC-003）"""
    return eco_grade in {"ENF", "E0"} and certification != "无认证"


async def assign_cert(
    db: AsyncSession,
    material_id: str,
    eco_grade: str,
    certification: str,
    source: str,
) -> tuple[MaterialEcoCert, bool]:
    """为材料分配/更新环保认证标签；返回 (认证记录, 是否新建)"""
    material = await db.get(Material, material_id)
    if not material:
        raise ValueError("材料不存在")
    if eco_grade not in ECO_GRADES:
        raise ValueError("环保等级不合法，可选: ENF/E0/E1")
    existing = await get_cert(db, material_id)
    if existing:
        existing.eco_grade = eco_grade
        existing.certification = certification
        existing.source = source
        await db.commit()
        await db.refresh(existing)
        return existing, False
    cert = MaterialEcoCert(
        material_id=material_id,
        eco_grade=eco_grade,
        certification=certification,
        source=source,
    )
    db.add(cert)
    await db.commit()
    await db.refresh(cert)
    return cert, True


async def get_cert(db: AsyncSession, material_id: str) -> MaterialEcoCert | None:
    """查询材料环保认证（无则 None）"""
    result = await db.execute(
        select(MaterialEcoCert).where(MaterialEcoCert.material_id == material_id)
    )
    return result.scalar_one_or_none()


def _cert_item(cert: MaterialEcoCert, material: Material) -> dict:
    """认证标签 + 材料信息（用于筛选/列表）"""
    return {
        "material_id": material.id,
        "material_name": material.name,
        "sku": material.sku,
        "brand": material.brand,
        "unit_price": material.unit_price,
        "eco_grade": cert.eco_grade,
        "certification": cert.certification,
    }


async def list_by_grade(db: AsyncSession, eco_grade: str) -> list[dict]:
    """按环保等级筛选材料"""
    result = await db.execute(
        select(MaterialEcoCert, Material)
        .join(Material, Material.id == MaterialEcoCert.material_id)
        .where(
            MaterialEcoCert.eco_grade == eco_grade,
            Material.deleted_at.is_(None),
        )
        .order_by(MaterialEcoCert.created_at.desc())
    )
    return [_cert_item(cert, mat) for cert, mat in result.all()]


async def list_all(db: AsyncSession) -> list[dict]:
    """列出全部带环保标签的材料"""
    result = await db.execute(
        select(MaterialEcoCert, Material)
        .join(Material, Material.id == MaterialEcoCert.material_id)
        .where(Material.deleted_at.is_(None))
        .order_by(MaterialEcoCert.created_at.desc())
    )
    return [_cert_item(cert, mat) for cert, mat in result.all()]


async def list_grades(db: AsyncSession) -> dict:
    """各环保等级数量统计（含 0）"""
    result = await db.execute(
        select(MaterialEcoCert.eco_grade, func.count(MaterialEcoCert.id))
        .group_by(MaterialEcoCert.eco_grade)
    )
    counts: dict[str, int] = {grade: 0 for grade in ECO_GRADES}
    for grade, count in result.all():
        counts[grade] = int(count)
    return counts


async def validate_compliance(db: AsyncSession, material_ids: list[str]) -> dict:
    """逐材料环保合规校验报告（对标 HC-003 环保等级硬约束）"""
    items: list[dict] = []
    for material_id in material_ids:
        material = await db.get(Material, material_id)
        if not material:
            raise ValueError(f"材料不存在: {material_id}")
        cert = await get_cert(db, material_id)
        eco_grade = cert.eco_grade if cert else "E1"
        certification = cert.certification if cert else "无认证"
        compliant = valid_compliance(eco_grade, certification)
        items.append({
            "material_id": material_id,
            "material_name": material.name,
            "eco_grade": eco_grade,
            "certification": certification,
            "compliant": compliant,
            "requirement": COMPLIANCE_REQUIREMENT,
            "note": "符合 HC-003 环保等级硬约束" if compliant else "环保等级或认证不满足 HC-003 要求",
        })
    compliant_count = sum(1 for item in items if item["compliant"])
    return {
        "total": len(items),
        "compliant_count": compliant_count,
        "non_compliant_count": len(items) - compliant_count,
        "items": items,
    }


async def recommend_alternatives(db: AsyncSession, material_id: str) -> list[dict]:
    """推荐同分类且环保等级 >= 当前等级（ENF > E0 > E1）的替代材料"""
    material = await db.get(Material, material_id)
    if not material:
        raise ValueError("材料不存在")
    cert = await get_cert(db, material_id)
    current_grade = cert.eco_grade if cert else "E1"
    current_rank = GRADE_RANK.get(current_grade, 0)
    result = await db.execute(
        select(Material).where(
            Material.category_id == material.category_id,
            Material.id != material_id,
            Material.deleted_at.is_(None),
        )
    )
    alternatives: list[dict] = []
    for candidate in result.scalars().all():
        candidate_cert = await get_cert(db, candidate.id)
        grade = candidate_cert.eco_grade if candidate_cert else "E1"
        if GRADE_RANK.get(grade, 0) >= current_rank:
            alternatives.append({
                "material_id": candidate.id,
                "material_name": candidate.name,
                "sku": candidate.sku,
                "eco_grade": grade,
                "unit_price": candidate.unit_price,
            })
    return alternatives
