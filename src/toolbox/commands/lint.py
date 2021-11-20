"""Linting checks on source code."""

import os
from pathlib import Path
from typing import List

import click
from termcolor import cprint

from toolbox.constants import AppContext, pass_app_context
from toolbox.utils import ensure_reports_dir, format_messages, print_header, read_contents


@click.command()
@pass_app_context
def lint_pydocstyle(app_context: AppContext):
    """Run docstring linting on source code.

    Docstring linting is done via pydocstyle. The pydocstyle config can be found in the
    `pyproject.toml` file under `[tool.pydocstyle]`. This ensures compliance with PEP 257,
    with a few exceptions. Note that pylint also carries out additional documentation
    style checks.
    """
    project = app_context.py_project_toml.project
    print_header("documentation style", level=2)
    ensure_reports_dir(project)

    report_pydocstyle_fpath = project.reports_directory / "pydocstyle-report.log"

    try:
        app_context.ctx.run(f"pydocstyle {project.source_directory} > {report_pydocstyle_fpath}")
    finally:
        if os.path.exists(report_pydocstyle_fpath):
            format_messages(read_contents(report_pydocstyle_fpath))


@click.command()
@pass_app_context
def lint_pycodestyle(app_context: AppContext):
    """Run PEP8 checking on code.

    PEP8 checking is done via pycodestyle.

    Why pycodestyle and pylint? So far, pylint does not check against every convention in PEP8. As pylint's
    functionality grows, we should move all PEP8 checking to pylint and remove pycodestyle.
    """
    project = app_context.py_project_toml.project
    print_header("code style (PEP8)", level=2)
    ensure_reports_dir(project)

    dirs = f"{project.source_directory} {project.tests_directory}"
    report_pycodestyle_fpath = project.reports_directory / "pycodestyle-report.log"

    try:
        app_context.ctx.run(
            f"pycodestyle --ignore=E501,W503,E231,E203,E402 "
            "--exclude=.svn,CVS,.bzr,.hg,.git,__pycache__,.tox,*_config_parser.py "
            f"{dirs} > {report_pycodestyle_fpath}"
        )
        # Ignores explained:
        # - E501: Line length is checked by PyLint
        # - W503: Disable checking of "Line break before binary operator". PEP8 recently (~2019) switched to
        #         "line break before the operator" style, so we should permit this usage.
        # - E231: "missing whitespace after ','" is a false positive. Handled by black formatter.
    finally:
        if os.path.exists(report_pycodestyle_fpath):
            format_messages(read_contents(report_pycodestyle_fpath))


def run_pylint(app_context: AppContext, source_dirs: List[Path], report_path: Path, pylintrc_fpath: Path):
    print_header(", ".join(map(str, source_dirs)), level=3)
    ensure_reports_dir(app_context.py_project_toml.project)

    try:
        app_context.ctx.run(f"pylint --rcfile {pylintrc_fpath} {' '.join(map(str, source_dirs))} > {report_path}")
    except Exception as runtime_error:  # pylint: disable=broad-except
        if os.path.exists(report_path):
            print(read_contents(report_path))
        raise runtime_error
    else:
        cprint("✔ No issues found.", "green")


@click.command()
@pass_app_context
def lint_pylint(app_context: AppContext):
    """Run pylint on code.

    The bulk of our code conventions are enforced via pylint. The pylint config can be
    found in the `.pylintrc` file.
    """
    print_header("pylint", level=2)
    project = app_context.py_project_toml.project

    run_pylint(
        app_context,
        [project.source_directory],
        project.reports_directory / "pylint-report.log",
        project.root_directory / ".pylintrc",
    )
    run_pylint(
        app_context,
        [project.tests_directory],
        project.reports_directory / "pylint-report-tests.log",
        project.tests_directory / ".pylintrc",
    )


_COMMANDS = [lint_pylint, lint_pycodestyle, lint_pydocstyle]


@click.command(
    help=f"Run linting on the entire code base.\n\n"
    f"Alias for the {', '.join(command.name for command in _COMMANDS)} commands."
)
@click.pass_context
def lint(click_context: click.Context):
    print_header("Linting", icon="🔎")
    for command in _COMMANDS:
        click_context.forward(command)
