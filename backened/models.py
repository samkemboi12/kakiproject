from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
class RawMaterial(db.Model):
    id = db.Column(db.Integer, primary_key=True); code = db.Column(db.String(12), unique=True, nullable=False); name = db.Column(db.String(50), nullable=False); unit_cost = db.Column(db.Float, nullable=False)
class MaterialMovement(db.Model):
    id = db.Column(db.Integer, primary_key=True); material_id = db.Column(db.Integer, db.ForeignKey('raw_material.id'), nullable=False); movement_date = db.Column(db.Date, nullable=False); movement_type = db.Column(db.String(20), nullable=False); quantity_kg = db.Column(db.Float, nullable=False); reference = db.Column(db.String(40), nullable=False); material = db.relationship('RawMaterial')
class Shift(db.Model):
    id = db.Column(db.Integer, primary_key=True); shift_date = db.Column(db.Date, nullable=False); shift_type = db.Column(db.String(8), nullable=False); operator = db.Column(db.String(80), nullable=False); notes = db.Column(db.String(240), default='')
class ProductionRound(db.Model):
    id = db.Column(db.Integer, primary_key=True); shift_id = db.Column(db.Integer, db.ForeignKey('shift.id'), nullable=False); quality = db.Column(db.String(10), nullable=False); input_kg = db.Column(db.Float, nullable=False); waste_kg = db.Column(db.Float, nullable=False, default=0); leftover_kg = db.Column(db.Float, nullable=False, default=0); created_at = db.Column(db.DateTime, default=datetime.utcnow); shift = db.relationship('Shift'); rolls = db.relationship('Roll', backref='round', cascade='all, delete-orphan')
class Roll(db.Model):
    id = db.Column(db.Integer, primary_key=True); production_round_id = db.Column(db.Integer, db.ForeignKey('production_round.id'), nullable=False); machine = db.Column(db.String(1), nullable=False); gross_kg = db.Column(db.Float, nullable=False)
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True); sku = db.Column(db.String(20), unique=True, nullable=False); name = db.Column(db.String(80), nullable=False); quality = db.Column(db.String(10), nullable=False); price_per_packet = db.Column(db.Float, nullable=False)
class FinishedMovement(db.Model):
    id = db.Column(db.Integer, primary_key=True); product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False); movement_date = db.Column(db.Date, nullable=False); movement_type = db.Column(db.String(20), nullable=False); packets = db.Column(db.Integer, nullable=False); reference = db.Column(db.String(40), nullable=False); product = db.relationship('Product')
class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True); sale_date = db.Column(db.Date, nullable=False); customer = db.Column(db.String(100), nullable=False); product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False); packets = db.Column(db.Integer, nullable=False); amount = db.Column(db.Float, nullable=False); status = db.Column(db.String(15), nullable=False, default='Dispatched'); product = db.relationship('Product')
class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True); expense_date = db.Column(db.Date, nullable=False); category = db.Column(db.String(50), nullable=False); description = db.Column(db.String(120), nullable=False); amount = db.Column(db.Float, nullable=False)
