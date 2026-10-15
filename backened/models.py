from datetime import datetime, timezone
from decimal import Decimal

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint


db = SQLAlchemy()

PACKETS_PER_BALE = 100


def utc_now():
    return datetime.now(timezone.utc)


class MasterDataMixin:
    id = db.Column(db.Integer, primary_key=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class Material(MasterDataMixin, db.Model):
    __tablename__ = "materials"

    code = db.Column(db.String(30), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)

    # Raw-material colour is fixed by its code.
    material_type = db.Column(db.String(20), nullable=False)
    colour = db.Column(db.String(10), nullable=True)
    unit = db.Column(db.String(5), nullable=False, default="kg")

    __table_args__ = (
        CheckConstraint(
            """
            (
                code = 'MAT-A'
                AND material_type = 'roll'
                AND colour IS NOT NULL
                AND colour = 'Black'
            )
            OR
            (
                code = 'MAT-B'
                AND material_type = 'roll'
                AND colour IS NOT NULL
                AND colour = 'White'
            )
            OR
            (
                code = 'MIX'
                AND material_type = 'mixing_agent'
                AND colour IS NULL
            )
            """,
            name="ck_material_allowed_inputs",
        ),
        CheckConstraint("unit = 'kg'", name="ck_material_unit_kg"),
    )


class Machine(MasterDataMixin, db.Model):
    __tablename__ = "machines"

    code = db.Column(db.String(30), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    status = db.Column(
        db.String(20),
        nullable=False,
        default="Available",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('Available', 'Running', 'Maintenance')",
            name="ck_machine_status",
        ),
    )


class Operator(MasterDataMixin, db.Model):
    __tablename__ = "operators"

    employee_number = db.Column(
        db.String(30),
        unique=True,
        nullable=False,
    )
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(30), nullable=True)

    # Operators will be assigned to individual production batches,
    # allowing them to work on different machines.


class Product(MasterDataMixin, db.Model):
    __tablename__ = "products"

    sku = db.Column(db.String(40), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    size = db.Column(db.String(60), nullable=False)
    colour = db.Column(db.String(10), nullable=False)

    # Price per packet. Numeric avoids floating-point money errors.
    selling_price = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    __table_args__ = (
        CheckConstraint(
            "colour IN ('Black', 'White')",
            name="ck_product_colour",
        ),
        CheckConstraint(
            "selling_price >= 0",
            name="ck_product_price_nonnegative",
        ),
    )

    @property
    def bale_selling_price(self):
        return self.selling_price * PACKETS_PER_BALE


def packets_to_bales(packet_count):
    """Return complete bales and remaining packets."""
    if isinstance(packet_count, bool) or not isinstance(packet_count, int):
        raise ValueError("Packet count must be an integer.")
    if packet_count < 0:
        raise ValueError("Packet count cannot be negative.")

    return divmod(packet_count, PACKETS_PER_BALE)


class MaterialLot(db.Model):
    __tablename__ = "material_lots"

    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(
        db.Integer,
        db.ForeignKey("materials.id"),
        nullable=False,
        index=True,
    )

    # Unique internal identifier, even if suppliers reuse lot numbers.
    lot_number = db.Column(db.String(80), unique=True, nullable=False)
    supplier_name = db.Column(db.String(120), nullable=False)
    received_on = db.Column(db.Date, nullable=False)

    received_weight_kg = db.Column(db.Numeric(14, 3), nullable=False)
    purchase_cost = db.Column(db.Numeric(14, 2), nullable=False)

    notes = db.Column(db.Text)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    material = db.relationship("Material")
    moves = db.relationship("MaterialMove", back_populates="lot")

    __table_args__ = (
        CheckConstraint(
            "received_weight_kg > 0",
            name="ck_lot_positive_weight",
        ),
        CheckConstraint(
            "purchase_cost >= 0",
            name="ck_lot_nonnegative_cost",
        ),
    )


class MaterialMove(db.Model):
    __tablename__ = "material_moves"

    id = db.Column(db.Integer, primary_key=True)
    lot_id = db.Column(
        db.Integer,
        db.ForeignKey("material_lots.id"),
        nullable=False,
        index=True,
    )

    # Positive = incoming stock; negative = outgoing stock.
    quantity_kg = db.Column(db.Numeric(14, 3), nullable=False)
    move_type = db.Column(db.String(30), nullable=False)
    movement_date = db.Column(db.Date, nullable=False)
    reference = db.Column(db.String(100), nullable=False)
    reason = db.Column(db.Text, nullable=False)

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    lot = db.relationship("MaterialLot", back_populates="moves")

    __table_args__ = (
        CheckConstraint(
            "quantity_kg != 0",
            name="ck_material_move_nonzero",
        ),
        CheckConstraint(
            "move_type IN ('Receipt', 'Consumption', 'Adjustment')",
            name="ck_material_move_type",
        ),
        CheckConstraint(
            """
            (move_type = 'Receipt' AND quantity_kg > 0)
            OR (move_type = 'Consumption' AND quantity_kg < 0)
            OR move_type = 'Adjustment'
            """,
            name="ck_material_move_direction",
        ),
    )
