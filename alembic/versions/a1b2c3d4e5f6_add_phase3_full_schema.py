"""add phase3 full schema: appliance (F19-F20) + structural (F8-F9)

Creates all tables that were not covered by the init (4356fec95e3e) or
phase2.4 (8c945de89e0d) migrations.

New tables:
  Appliance module (F19-F20):
    - appliance_categories
    - appliances
    - appliance_points
    - appliance_load_calcs
  Structural module (F8-F9):
    - load_bearing_walls
    - beams
    - columns
    - floor_slabs
    - foundation_types
    - structure_load_estimates
    - bay_compliance
    - quantity_calculations
    - quantity_line_items

Revision ID: a1b2c3d4e5f6
Revises: 8c945de89e0d
Create Date: 2026-07-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '8c945de89e0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==================================================================
    # Appliance module (F19-F20): appliance_categories, appliances,
    #   appliance_points, appliance_load_calcs
    # ==================================================================

    # -- appliance_categories (standalone, no FK) ----------------------
    op.create_table('appliance_categories',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )

    # -- appliances (FK -> appliance_categories) ------------------------
    op.create_table('appliances',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('category_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('brand', sa.String(length=100), nullable=True),
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column('subcategory', sa.String(length=50), nullable=False),
        sa.Column('spec', sa.String(length=500), nullable=True),
        sa.Column('power_rating', sa.Float(), nullable=True),
        sa.Column('energy_label', sa.String(length=20), nullable=True),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('install_requirements', sa.JSON(), nullable=True),
        sa.Column('dimensions', sa.JSON(), nullable=True),
        sa.Column('weight_kg', sa.Float(), nullable=True),
        sa.Column('image_url', sa.String(length=500), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['appliance_categories.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # -- appliance_points (FK -> projects, rooms, appliances) -----------
    op.create_table('appliance_points',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('room_id', sa.String(length=36), nullable=True),
        sa.Column('appliance_id', sa.String(length=36), nullable=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('location', sa.Text(), nullable=True),
        sa.Column('outlet_type', sa.String(length=50), nullable=True),
        sa.Column('circuit', sa.String(length=100), nullable=True),
        sa.Column('water_supply', sa.Boolean(), nullable=False),
        sa.Column('drainage', sa.Boolean(), nullable=False),
        sa.Column('gas_supply', sa.Boolean(), nullable=False),
        sa.Column('wall_hole', sa.String(length=50), nullable=True),
        sa.Column('embedding_notes', sa.Text(), nullable=True),
        sa.Column('power_w', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['appliance_id'], ['appliances.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.ForeignKeyConstraint(['room_id'], ['rooms.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # -- appliance_load_calcs (FK -> projects) --------------------------
    op.create_table('appliance_load_calcs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('circuit_name', sa.String(length=100), nullable=False),
        sa.Column('total_power', sa.Float(), nullable=False),
        sa.Column('voltage', sa.Float(), nullable=False),
        sa.Column('max_current', sa.Float(), nullable=False),
        sa.Column('wire_gauge', sa.String(length=50), nullable=True),
        sa.Column('breaker_rating', sa.String(length=50), nullable=True),
        sa.Column('is_compliant', sa.Boolean(), nullable=False),
        sa.Column('warning_msg', sa.Text(), nullable=True),
        sa.Column('appliance_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # ==================================================================
    # Structural module (F8-F9): load_bearing_walls, beams, columns,
    #   floor_slabs, foundation_types, structure_load_estimates,
    #   bay_compliance, quantity_calculations, quantity_line_items
    # ==================================================================

    # -- load_bearing_walls (FK -> projects, rooms) --------------------
    op.create_table('load_bearing_walls',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('room_id', sa.String(length=36), nullable=True),
        sa.Column('wall_name', sa.String(length=100), nullable=False),
        sa.Column('is_load_bearing', sa.Boolean(), nullable=False),
        sa.Column('thickness_mm', sa.Integer(), nullable=False),
        sa.Column('length_m', sa.Float(), nullable=False),
        sa.Column('height_m', sa.Float(), nullable=False),
        sa.Column('material', sa.String(length=50), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.ForeignKeyConstraint(['room_id'], ['rooms.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # -- beams (FK -> projects) -----------------------------------------
    op.create_table('beams',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('beam_name', sa.String(length=100), nullable=False),
        sa.Column('beam_type', sa.String(length=30), nullable=False),
        sa.Column('width_mm', sa.Integer(), nullable=False),
        sa.Column('height_mm', sa.Integer(), nullable=False),
        sa.Column('length_m', sa.Float(), nullable=False),
        sa.Column('material', sa.String(length=30), nullable=False),
        sa.Column('concrete_grade', sa.String(length=10), nullable=True),
        sa.Column('position_desc', sa.String(length=200), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # -- columns (FK -> projects) --------------------------------------
    op.create_table('columns',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('column_name', sa.String(length=100), nullable=False),
        sa.Column('column_type', sa.String(length=30), nullable=False),
        sa.Column('width_mm', sa.Integer(), nullable=False),
        sa.Column('depth_mm', sa.Integer(), nullable=False),
        sa.Column('height_m', sa.Float(), nullable=False),
        sa.Column('material', sa.String(length=30), nullable=False),
        sa.Column('concrete_grade', sa.String(length=10), nullable=True),
        sa.Column('position_desc', sa.String(length=200), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # -- floor_slabs (FK -> projects) -----------------------------------
    op.create_table('floor_slabs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('slab_name', sa.String(length=100), nullable=False),
        sa.Column('slab_type', sa.String(length=30), nullable=False),
        sa.Column('thickness_mm', sa.Integer(), nullable=False),
        sa.Column('area_m2', sa.Float(), nullable=False),
        sa.Column('concrete_grade', sa.String(length=10), nullable=True),
        sa.Column('rebar_diameter_mm', sa.Integer(), nullable=True),
        sa.Column('rebar_spacing_mm', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # -- foundation_types (FK -> projects) ------------------------------
    op.create_table('foundation_types',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('found_type', sa.String(length=50), nullable=False),
        sa.Column('bearing_capacity_kpa', sa.Float(), nullable=False),
        sa.Column('embed_depth_m', sa.Float(), nullable=False),
        sa.Column('foundation_width_m', sa.Float(), nullable=True),
        sa.Column('soil_type', sa.String(length=50), nullable=True),
        sa.Column('is_selected', sa.Boolean(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # -- structure_load_estimates (FK -> projects) ----------------------
    op.create_table('structure_load_estimates',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('load_type', sa.String(length=30), nullable=False),
        sa.Column('load_value_kn_m2', sa.Float(), nullable=False),
        sa.Column('area_m2', sa.Float(), nullable=False),
        sa.Column('total_load_kn', sa.Float(), nullable=False),
        sa.Column('floor_level', sa.Integer(), nullable=True),
        sa.Column('usage', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # -- bay_compliance (FK -> projects) --------------------------------
    op.create_table('bay_compliance',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('room_name', sa.String(length=100), nullable=False),
        sa.Column('bay_width_m', sa.Float(), nullable=False),
        sa.Column('depth_m', sa.Float(), nullable=False),
        sa.Column('floor_height_m', sa.Float(), nullable=False),
        sa.Column('is_bay_compliant', sa.Boolean(), nullable=False),
        sa.Column('is_depth_compliant', sa.Boolean(), nullable=False),
        sa.Column('is_height_compliant', sa.Boolean(), nullable=False),
        sa.Column('checks', sa.JSON(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # -- quantity_calculations (FK -> projects) -------------------------
    op.create_table('quantity_calculations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('calc_name', sa.String(length=100), nullable=False),
        sa.Column('calc_type', sa.String(length=30), nullable=False),
        sa.Column('wall_volume_m3', sa.Float(), nullable=False),
        sa.Column('brick_count', sa.Integer(), nullable=False),
        sa.Column('mortar_m3', sa.Float(), nullable=False),
        sa.Column('concrete_m3', sa.Float(), nullable=False),
        sa.Column('rebar_kg', sa.Float(), nullable=False),
        sa.Column('formwork_m2', sa.Float(), nullable=False),
        sa.Column('total_cost', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # -- quantity_line_items (FK -> quantity_calculations) --------------
    op.create_table('quantity_line_items',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('calculation_id', sa.String(length=36), nullable=False),
        sa.Column('material_type', sa.String(length=50), nullable=False),
        sa.Column('material_name', sa.String(length=100), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=False),
        sa.Column('unit_price', sa.Float(), nullable=False),
        sa.Column('total_price', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['calculation_id'], ['quantity_calculations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    # Drop in reverse dependency order (children first, parents last)

    # Structural module (F8-F9)
    op.drop_table('quantity_line_items')
    op.drop_table('quantity_calculations')
    op.drop_table('bay_compliance')
    op.drop_table('structure_load_estimates')
    op.drop_table('foundation_types')
    op.drop_table('floor_slabs')
    op.drop_table('columns')
    op.drop_table('beams')
    op.drop_table('load_bearing_walls')

    # Appliance module (F19-F20)
    op.drop_table('appliance_load_calcs')
    op.drop_table('appliance_points')
    op.drop_table('appliances')
    op.drop_table('appliance_categories')
