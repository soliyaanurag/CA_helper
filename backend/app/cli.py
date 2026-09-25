"""Custom `flask` CLI commands.

flask --app app seed    run every module's seed() (make seed)
"""

import click
from flask import Flask

from app.modules import run_all_seeds


def register_commands(app: Flask) -> None:
    @app.cli.command("seed")
    def seed_command() -> None:
        """Insert development seed data from every module. Safe to re-run."""
        seeded = run_all_seeds()
        click.echo(f"Seeded {len(seeded)} module(s): {', '.join(seeded) or '(none)'}")
