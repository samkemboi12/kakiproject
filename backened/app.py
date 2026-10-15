import os
import sqlite3
from pathlib import Path

import click
from flask import Flask, jsonify
from sqlalchemy import event
from sqlalchemy.engine import Engine

from models import db, Material, Machine


@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(connection, connection_record):
    if isinstance(connection, sqlite3.Connection):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get(
    "KHAKI_SECRET_KEY",
    "local-development-change-before-deployment",
),
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            "KHAKI_DATABASE_URL",
            "sqlite:///khaki_plant.sqlite3",
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    from setup_routes import setup_bp
    app.register_blueprint(setup_bp)

    @app.get("/")
    def home():
        return jsonify(
            application="Khaki Packet Manufacturing",
            stage="Master data setup",
            packets_per_bale=100,
        )

    @app.cli.command("init-db")
    def init_db():
        """Create tables and seed the three inputs and machines."""
        db.create_all()

        materials = [
            {
                "code": "MAT-A",
                "name": "Material A — Black rolls",
                "material_type": "roll",
                "colour": "Black",
            },
            {
                "code": "MAT-B",
                "name": "Material B — White rolls",
                "material_type": "roll",
                "colour": "White",
            },
            {
                "code": "MIX",
                "name": "Mixing Agent",
                "material_type": "mixing_agent",
                "colour": None,
            },
        ]

        # Seed everything together; roll back if an insert fails.
        with db.session.begin():
            for values in materials:
                existing = db.session.execute(
                    db.select(Material).where(
                        Material.code == values["code"]
                    )
                ).scalar_one_or_none()

                if existing is None:
                    db.session.add(Material(**values))

            for number in range(1, 4):
                code = f"MACHINE-{number}"

                existing = db.session.execute(
                    db.select(Machine).where(Machine.code == code)
                ).scalar_one_or_none()

                if existing is None:
                    db.session.add(
                        Machine(
                            code=code,
                            name=f"Machine {number}",
                            status="Available",
                        )
                    )

        click.echo(
            "Database initialized: three inputs and three "
            "independent machines."
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)