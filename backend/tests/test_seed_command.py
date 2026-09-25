"""`flask seed` runs every module's seed() without errors."""


def test_seed_command_runs_all_modules(app, database):
    result = app.test_cli_runner().invoke(args=["seed"])

    assert result.exit_code == 0, result.output
    assert "Seeded 9 module(s)" in result.output
