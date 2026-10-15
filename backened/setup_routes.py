import secrets
from decimal import Decimal, InvalidOperation

from flask import (
    Blueprint, abort, flash, redirect, render_template,
    request, session, url_for,
)
from sqlalchemy.exc import IntegrityError

from models import db, Material, Machine, Operator, Product


setup_bp = Blueprint("setup", __name__, url_prefix="/setup")

# Field: (database attribute, display label, input type, choices)
SECTIONS = {
    "materials": {
        "title": "Materials",
        "model": Material,
        "allow_create": False,
        "fields": [
            ("code", "Code", "readonly", None),
            ("name", "Material name", "text", None),
            ("material_type", "Type", "readonly", None),
            ("colour", "Colour", "readonly", None),
            ("unit", "Unit", "readonly", None),
        ],
    },
    "machines": {
        "title": "Machines",
        "model": Machine,
        "allow_create": False,
        "fields": [
            ("code", "Code", "readonly", None),
            ("name", "Machine name", "text", None),
            (
                "status", "Status", "select",
                ["Available", "Running", "Maintenance"],
            ),
        ],
    },
    "operators": {
        "title": "Operators",
        "model": Operator,
        "allow_create": True,
        "fields": [
            ("employee_number", "Employee number", "text", None),
            ("full_name", "Full name", "text", None),
            ("phone", "Phone", "optional", None),
        ],
    },
    "products": {
        "title": "Products",
        "model": Product,
        "allow_create": True,
        "fields": [
            ("sku", "SKU", "text", None),
            ("name", "Product name", "text", None),
            ("size", "Size", "text", None),
            ("colour", "Colour", "select", ["Black", "White"]),
            ("selling_price", "Selling price per packet", "money", None),
        ],
    },
}


def get_section(section):
    config = SECTIONS.get(section)
    if config is None:
        abort(404)
    return config


def csrf_token():
    session.setdefault("csrf_token", secrets.token_urlsafe(32))
    return session["csrf_token"]


@setup_bp.app_context_processor
def template_helpers():
    return {"csrf_token": csrf_token}


def validate_form(config):
    values = {}

    for name, label, kind, choices in config["fields"]:
        if kind == "readonly":
            continue

        value = request.form.get(name, "").strip()

        if kind != "optional" and not value:
            raise ValueError(f"{label} is required.")

        if choices and value not in choices:
            raise ValueError(f"Choose a valid {label.lower()}.")

        column = config["model"].__table__.columns[name]
        max_length = getattr(column.type, "length", None)
        if max_length and len(value) > max_length:
            raise ValueError(
                f"{label} must be {max_length} characters or fewer."
            )

        if kind == "money":
            try:
                amount = Decimal(value)
            except InvalidOperation:
                raise ValueError("Enter a valid selling price.")

            if not amount.is_finite() or amount < 0:
                raise ValueError("Selling price must be zero or greater.")

            if amount > Decimal("9999999999.99"):
                raise ValueError("Selling price is too large.")

            if amount != amount.quantize(Decimal("0.01")):
                raise ValueError("Use at most two decimal places.")

            value = amount.quantize(Decimal("0.01"))

        elif name in ("sku", "employee_number"):
            value = value.upper()

        values[name] = value or None

    return values


@setup_bp.get("/")
def index():
    return redirect(url_for("setup.manage", section="materials"))


@setup_bp.route("/<section>", methods=["GET", "POST"])
def manage(section):
    config = get_section(section)
    model = config["model"]

    record_id = request.args.get("edit", type=int)
    record = db.session.get(model, record_id) if record_id else None

    if record_id and record is None:
        abort(404)

    submitted = None
    status_code = 200

    if request.method == "POST":
        supplied_token = request.form.get("csrf_token", "")
        expected_token = session.get("csrf_token", "")

        if not expected_token or not secrets.compare_digest(
            supplied_token, expected_token
        ):
            abort(400, description="Invalid form token. Refresh and retry.")

        if record is None and not config["allow_create"]:
            abort(400, description="Select an existing record to edit.")

        submitted = request.form.to_dict()

        try:
            values = validate_form(config)

            if record is None:
                record = model()
                db.session.add(record)

            for name, value in values.items():
                setattr(record, name, value)

            record.active = request.form.get("active") == "on"

            db.session.commit()
            flash("Record saved successfully.", "success")
            return redirect(url_for("setup.manage", section=section))

        except ValueError as error:
            db.session.rollback()
            flash(str(error), "error")
            status_code = 400

        except IntegrityError:
            db.session.rollback()
            flash(
                "Could not save. Check for a duplicate SKU or "
                "employee number and valid field values.",
                "error",
            )
            status_code = 400

        # Restore the original edit record after rollback.
        record = db.session.get(model, record_id) if record_id else None

    rows = db.session.execute(
        db.select(model).order_by(model.id)
    ).scalars().all()

    if submitted is not None:
        form_values = submitted
    elif record is not None:
        form_values = {
            name: getattr(record, name)
            for name, *_ in config["fields"]
        }
    else:
        form_values = {}

    active_checked = (
        submitted.get("active") == "on"
        if submitted is not None
        else record.active if record is not None else True
    )

    return render_template(
        "setup.html",
        section=section,
        config=config,
        sections=SECTIONS,
        rows=rows,
        record=record,
        editing=record_id is not None,
        form_values=form_values,
        active_checked=active_checked,
    ), status_code