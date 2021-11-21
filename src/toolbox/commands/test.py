"""Tests on source code."""

import re
import shutil
import webbrowser
from pathlib import Path

import click
import invoke

from toolbox.contexts import AppContext, pass_app_context
from toolbox.utils import ensure_reports_dir, handle_invoke_exceptions, print_header


@handle_invoke_exceptions
def _run_tests(app_context: AppContext, name: str, maxfail: int, debug: bool) -> None:
    """Execute the tests for a given test type."""
    toolbox = app_context.py_project_toml.tool.toolbox

    if name not in toolbox.test_types or not toolbox.tests_directory:
        return

    print_header(f"️Running {name} tests️", icon="🔎🐛")
    ensure_reports_dir(toolbox)
    app_context.ctx.run(
        f"""
        pytest \
            --cov={toolbox.sources_directory} \
            --cov-report="xml:{toolbox.reports_directory / f"coverage-{name}.xml"}" \
            --cov-branch -vv --maxfail={maxfail} {"-s" if debug else ""}\
            {toolbox.tests_directory / name}
        """,
        env={"COVERAGE_FILE": toolbox.reports_directory / f"coverage-{name}.dat"},
        pty=True,
    )


@click.command(help="Run unit tests.")
@click.option("--maxfail", type=int, default=0)
@click.option("--debug", is_flag=True, help="Disables capture, allowing debuggers like `pdb` to be used.")
@pass_app_context
def test_unit(app_context: AppContext, maxfail: int, debug: bool):
    _run_tests(app_context, "unit", maxfail=maxfail, debug=debug)


@click.command(help="Run integration tests.")
@click.option("--maxfail", type=int, default=0)
@click.option("--debug", is_flag=True, help="Disables capture, allowing debuggers like `pdb` to be used.")
@pass_app_context
def test_integration(app_context: AppContext, maxfail: int, debug: bool):
    # TODO(Radek): Replace with alias?
    _run_tests(app_context, "integration", maxfail=maxfail, debug=debug)


def _get_total_coverage(ctx: invoke.Context, coverage_dat: Path) -> str:
    """Return coverage percentage, as captured in coverage dat file; e.g., returns "100%"."""
    output = ctx.run(
        f"""
        export COVERAGE_FILE="{coverage_dat}"
        coverage report""",
        hide=True,
    ).stdout
    match = re.search(r"TOTAL.*?([\d.]+%)", output)
    if match is None:
        raise RuntimeError(f"Regex failed on output: {output}")
    return match.group(1)


@click.command()
@pass_app_context
@handle_invoke_exceptions
def coverage_report(app_context: AppContext):
    """Analyse coverage and generate a term/HTML report.

    Combines all test types.
    """
    print_header("Generating coverage report", icon="📃")
    toolbox = app_context.py_project_toml.tool.toolbox
    ensure_reports_dir(toolbox)

    coverage_dat_combined = toolbox.reports_directory / "coverage.dat"
    coverage_html = toolbox.reports_directory / "coverage-report/"

    coverage_files = []  # we'll make a copy because `combine` will erase them
    for test_type in toolbox.test_types:
        coverage_dat = toolbox.reports_directory / f"coverage-{test_type}.dat"

        if not coverage_dat.exists():
            click.secho(
                f"Could not find coverage dat file for {test_type} tests: {coverage_dat}",
                fg="yellow",
            )
        else:
            print(f"{test_type.title()} test coverage: {_get_total_coverage(app_context.ctx, coverage_dat)}")

            temp_copy = coverage_dat.with_name(coverage_dat.name.replace(".dat", "-copy.dat"))
            shutil.copy(coverage_dat, temp_copy)
            coverage_files.append(str(temp_copy))

    app_context.ctx.run(
        f"""
            export COVERAGE_FILE="{coverage_dat_combined}"
            coverage combine {" ".join(coverage_files)}
            coverage html -d {coverage_html}
        """
    )
    print(f"Total coverage: {_get_total_coverage(app_context.ctx, coverage_dat_combined)}\n")
    print(
        f"Refer to coverage report for full analysis in '{coverage_html}/index.html'\n"
        f"Or open the report in your default browser with:\n"
        f"  pipenv run inv coverage-open"
    )


@click.command(help="Run all tests, and generate coverage report.")
@click.pass_context
def test_all(click_context: click.Context):
    print_header("Linting", icon="🔎")
    click_context.forward(test_unit)
    click_context.forward(test_integration)
    click_context.forward(coverage_report)


@click.command(help="Open coverage results in default browser.")
@pass_app_context
def coverage_open(app_context: AppContext):
    report_index = app_context.py_project_toml.tool.toolbox.reports_directory / "coverage-report" / "index.html"
    if not report_index.exists():
        click.secho(
            f"Could not find coverage report '{report_index}'. Ensure that the report has been built.\n"
            "Try one of the following:\n"
            f"  pipenv run inv {coverage_report.name}\n"
            f"or\n"
            f"  pipenv run inv {test_all.name}",
            fg="red",
        )

        raise click.exceptions.Exit(code=1)
    webbrowser.open(f"file:///{report_index.absolute()}")
