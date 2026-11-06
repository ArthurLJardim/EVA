from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class GradeComponent:
    key: str
    label: str
    weight: float
    due_date: str | None = None
    item_title_contains: str | None = None


@dataclass(frozen=True)
class GradeUnit:
    name: str
    components: tuple[GradeComponent, ...]


@dataclass(frozen=True)
class CourseGradeConfig:
    course: str
    units: tuple[GradeUnit, ...]
    use_sigaa_unit_override: bool = True

    def all_components(self) -> list[GradeComponent]:
        return [component for unit in self.units for component in unit.components]

    def component(self, key: str) -> GradeComponent | None:
        for component in self.all_components():
            if component.key == key:
                return component
        return None


def load_grade_configs(path: Path) -> dict[str, CourseGradeConfig]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    configs: dict[str, CourseGradeConfig] = {}
    for course, spec in data.items():
        units = tuple(
            GradeUnit(
                name=unit["name"],
                components=tuple(
                    GradeComponent(
                        key=component["key"],
                        label=component["label"],
                        weight=component["weight"],
                        due_date=component.get("due_date"),
                        item_title_contains=component.get("item_title_contains"),
                    )
                    for component in unit["components"]
                ),
            )
            for unit in spec["units"]
        )
        configs[course] = CourseGradeConfig(
            course=course,
            units=units,
            use_sigaa_unit_override=spec.get("use_sigaa_unit_override", True),
        )
    return configs


def _unit_override_key(unit_name: str) -> str:
    return f"__unit__{unit_name}"


def compute_unit_value(unit: GradeUnit, values: dict[str, float]) -> float | None:
    override = values.get(_unit_override_key(unit.name))
    if override is not None:
        return override
    total = 0.0
    for component in unit.components:
        if component.key not in values or values[component.key] is None:
            return None
        total += values[component.key] * component.weight
    return total


def compute_course_average(config: CourseGradeConfig, values: dict[str, float]) -> dict:
    unit_values = {unit.name: compute_unit_value(unit, values) for unit in config.units}
    known = [value for value in unit_values.values() if value is not None]
    final_average = sum(known) / len(config.units) if len(known) == len(config.units) and config.units else None
    return {"units": unit_values, "final_average": final_average}


def missing_components(config: CourseGradeConfig, values: dict[str, float]) -> list[GradeComponent]:
    missing: list[GradeComponent] = []
    for unit in config.units:
        if values.get(_unit_override_key(unit.name)) is not None:
            continue
        missing.extend(
            component
            for component in unit.components
            if component.key not in values or values[component.key] is None
        )
    return missing


def apply_boletim_results(storage, configs: dict[str, CourseGradeConfig], results: list[dict]) -> None:
    for result in results:
        course = result["course"]
        storage.set_course_attendance(
            course,
            result.get("faltas") or 0,
            result.get("situacao") or "",
            result.get("max_faltas"),
        )
        config = configs.get(course)
        if not config or not config.use_sigaa_unit_override:
            continue
        unit_values = list((result.get("unidades") or {}).values())
        for unit, value in zip(config.units, unit_values):
            if value is None:
                continue
            storage.set_grade_component(course, _unit_override_key(unit.name), value, "sigaa")
