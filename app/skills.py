from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import PROJECT_ROOT, Settings


SKILL_FILENAME = "SKILL.md"


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    path: Path
    body: str
    stage: str = ""
    version: str = ""
    metadata: dict[str, str] | None = None


def resolve_skills_dir(settings: Settings) -> Path:
    path = Path(settings.skills_dir)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def list_skills(settings: Settings) -> list[Skill]:
    skills_dir = resolve_skills_dir(settings)
    if not skills_dir.exists():
        return []
    return sorted(
        (load_skill_file(path) for path in skills_dir.glob(f"*/{SKILL_FILENAME}")),
        key=lambda skill: skill.name,
    )


def load_skill(settings: Settings, name: str) -> Skill:
    for skill in list_skills(settings):
        if skill.name == name:
            return skill
    raise FileNotFoundError(f"Skill not found: {name}")


def load_skill_file(path: Path) -> Skill:
    raw = path.read_text(encoding="utf-8")
    metadata, body = parse_skill_markdown(raw)
    name = metadata.get("name") or path.parent.name
    return Skill(
        name=name,
        description=metadata.get("description", ""),
        stage=metadata.get("stage", ""),
        version=metadata.get("version", ""),
        metadata=metadata,
        path=path,
        body=body.strip(),
    )


def parse_skill_markdown(raw: str) -> tuple[dict[str, str], str]:
    lines = raw.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, raw

    metadata: dict[str, str] = {}
    end_index: int | None = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"').strip("'")

    if end_index is None:
        return {}, raw
    return metadata, "\n".join(lines[end_index + 1 :])


def render_skill_context(skills: list[Skill]) -> str:
    sections: list[str] = []
    for skill in skills:
        sections.append(f"# Skill: {skill.name}\n\n{skill.body}")
    return "\n\n".join(sections)
