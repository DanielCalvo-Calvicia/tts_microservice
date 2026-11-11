"""Fitness function: DTOs live in ``application/dtos/inbound`` or ``application/dtos/outbound``, never loose.

An inbound DTO is what an inbound adapter hands to the application (a request); an outbound DTO is what the
application hands back (a response). The folder, the file suffix and the class suffix say the same thing.

``outbound/audio_segment_outbound.py`` also holds the small event types a segment stream is made of
(``StreamFormat``, ``AudioChunk``, ``SegmentCompleted``, ``SegmentFailed``): they are parts of its DTO, so the
class suffix rule asks for at least one ``...OutboundDTO`` in each module, not for every class to have it.
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DTOS = ROOT / "application" / "dtos"


def _modules(folder: str) -> list[Path]:
    return sorted(p for p in (DTOS / folder).glob("*.py") if p.name != "__init__.py")


def test_no_dto_sits_outside_the_inbound_and_outbound_folders():
    loose = sorted(p.name for p in DTOS.glob("*.py") if p.name != "__init__.py")
    assert not loose, f"DTOs must be in dtos/inbound or dtos/outbound: {loose}"


@pytest.mark.parametrize("direction", ["inbound", "outbound"])
def test_each_dto_is_named_for_its_folder(direction):
    modules = _modules(direction)
    assert modules, f"no {direction} DTO found"
    suffix = f"{direction.capitalize()}DTO"
    problems = []
    for path in modules:
        if not path.stem.endswith(f"_{direction}"):
            problems.append(f"{path.name}: the file name must end with _{direction}")
        classes = [n.name for n in ast.parse(path.read_text(encoding="utf-8")).body if isinstance(n, ast.ClassDef)]
        if not any(name.endswith(suffix) for name in classes):
            problems.append(f"{path.name}: it must define a class ending with {suffix}, found {classes}")
    assert not problems, "\n".join(problems)
