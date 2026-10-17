"""The agent skill bundled with swpc-kit, and the commands that install it.

The package ships a skill (``SKILL.md`` plus ``references/``) that teaches
AI coding assistants how to use the library without reading its source. It
follows the Agent Skills format and is versioned with the package. Agents do
not look inside installed Python packages, so copy it where they look::

    python -m swpc_kit.skill install            # into .claude/skills/swpc-kit/
    python -m swpc_kit.skill install --target DIR
    python -m swpc_kit.skill check              # is the installed copy current?
    python -m swpc_kit.skill show               # print SKILL.md
    python -m swpc_kit.skill path               # where the bundled copy lives
"""

import argparse
import re
import shutil
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path

from swpc_kit import __version__

__all__ = [
    "DEFAULT_TARGET",
    "SKILL_NAME",
    "SkillInfo",
    "Status",
    "bundled",
    "check",
    "install",
    "main",
    "read_skill",
    "skill_info",
]

SKILL_NAME = "swpc-kit"
"""Name of the skill, also the name of its directory."""

DEFAULT_TARGET = Path(".claude") / "skills" / SKILL_NAME
"""Where :func:`install` copies the skill by default (relative to the cwd)."""

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_NAME = re.compile(r"^name:\s*(\S+)\s*$", re.MULTILINE)
_VERSION = re.compile(r"^\s+version:\s*[\"']?([^\"'\s]+)[\"']?\s*$", re.MULTILINE)


def bundled() -> Traversable:
    """Return the directory of the skill shipped with the package."""
    return resources.files(__package__).joinpath(SKILL_NAME)


def read_skill() -> str:
    """Return the text of the bundled ``SKILL.md``."""
    return bundled().joinpath("SKILL.md").read_text(encoding="utf-8")


@dataclass(frozen=True, slots=True)
class SkillInfo:
    """Name and version read from the frontmatter of a ``SKILL.md``.

    Attributes:
        name: The ``name`` field, or ``None``.
        version: The ``metadata.version`` field, or ``None``.
    """

    name: str | None
    version: str | None


def skill_info(text: str) -> SkillInfo:
    """Read name and version from the frontmatter of a ``SKILL.md``."""
    match = _FRONTMATTER.match(text)
    if match is None:
        return SkillInfo(None, None)
    head = match[1]
    name = _NAME.search(head)
    version = _VERSION.search(head)
    return SkillInfo(name[1] if name else None, version[1] if version else None)


def _copy(source: Traversable, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        if item.is_dir():
            _copy(item, target / item.name)
        elif not item.name.endswith((".pyc", ".pyo")):
            (target / item.name).write_bytes(item.read_bytes())


def install(target: Path = DEFAULT_TARGET, *, force: bool = False) -> Path:
    """Copy the bundled skill into ``target``.

    A previous copy of this skill in ``target`` is replaced. Any other
    non-empty directory is left alone unless ``force`` is true.

    Args:
        target: Directory to create or replace.
        force: Replace ``target`` even if it is not a copy of this skill.

    Returns:
        The directory written.

    Raises:
        FileExistsError: If ``target`` holds something else and ``force`` is
            false.
    """
    if target.exists():
        current = target / "SKILL.md"
        ours = current.is_file() and skill_info(current.read_text("utf-8")).name == (
            SKILL_NAME
        )
        if not ours and any(target.iterdir()) and not force:
            raise FileExistsError(
                f"{target} exists and is not a copy of the {SKILL_NAME} skill;"
                " use --force to replace it"
            )
        shutil.rmtree(target)
    _copy(bundled(), target)
    return target


@dataclass(frozen=True, slots=True)
class Status:
    """State of an installed copy compared with the bundled skill.

    Attributes:
        current: Whether the installed copy matches the package version.
        installed: Version of the installed copy, or ``None`` if missing.
        bundled: Version of the skill shipped with the package.
        message: One line for humans.
    """

    current: bool
    installed: str | None
    bundled: str | None
    message: str


def check(target: Path = DEFAULT_TARGET) -> Status:
    """Compare the copy in ``target`` with the bundled skill."""
    shipped = skill_info(read_skill()).version
    path = target / "SKILL.md"
    if not path.is_file():
        return Status(False, None, shipped, f"not installed in {target}")
    installed = skill_info(path.read_text("utf-8")).version
    if installed != shipped:
        return Status(
            False,
            installed,
            shipped,
            f"{target} has version {installed}, the package has {shipped}:"
            " run `python -m swpc_kit.skill install`",
        )
    return Status(True, installed, shipped, f"{target} is current ({installed})")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the ``python -m swpc_kit.skill`` command line."""
    parser = argparse.ArgumentParser(
        prog="python -m swpc_kit.skill",
        description=f"Manage the agent skill of swpc-kit {__version__}.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name, text in (
        ("install", "copy the skill into a skills directory"),
        ("check", "say whether the installed copy matches this version"),
    ):
        command = commands.add_parser(name, help=text)
        command.add_argument(
            "--target",
            type=Path,
            default=DEFAULT_TARGET,
            help=f"skill directory (default: {DEFAULT_TARGET})",
        )
        if name == "install":
            command.add_argument(
                "--force", action="store_true", help="replace any existing directory"
            )
    commands.add_parser("show", help="print SKILL.md")
    commands.add_parser("path", help="print where the bundled skill lives")
    args = parser.parse_args(argv)

    if args.command == "show":
        sys.stdout.write(read_skill())
        return 0
    if args.command == "path":
        print(bundled())
        return 0
    if args.command == "install":
        try:
            written = install(args.target, force=args.force)
        except FileExistsError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"installed the {SKILL_NAME} skill {__version__} in {written}")
        return 0
    status = check(args.target)
    print(status.message)
    return 0 if status.current else 1
