from bot_faculdade.grades import (
    CourseGradeConfig,
    GradeComponent,
    GradeUnit,
    compute_course_average,
    missing_components,
)


def _config() -> CourseGradeConfig:
    return CourseGradeConfig(
        course="INTRODUÇÃO À PROGRAMAÇÃO",
        units=(
            GradeUnit(
                name="N1",
                components=(
                    GradeComponent(key="trabalho1", label="Trabalho 1", weight=0.3),
                    GradeComponent(key="aval1", label="Aval 1", weight=0.7),
                ),
            ),
            GradeUnit(
                name="N2",
                components=(
                    GradeComponent(key="trabalho2", label="Trabalho 2", weight=0.3),
                    GradeComponent(key="aval2", label="Aval 2", weight=0.7),
                ),
            ),
        ),
    )


def test_compute_course_average_matches_syllabus_formula():
    config = _config()
    values = {"trabalho1": 9, "aval1": 7, "trabalho2": 8, "aval2": 6}
    result = compute_course_average(config, values)
    assert result["units"]["N1"] == 7.6
    assert result["units"]["N2"] == 6.6
    assert round(result["final_average"], 2) == 7.1


def test_compute_course_average_partial_when_missing_values():
    config = _config()
    result = compute_course_average(config, {"trabalho1": 9, "aval1": 7})
    assert result["units"]["N1"] == 7.6
    assert result["units"]["N2"] is None
    assert result["final_average"] is None


def test_missing_components_skips_units_with_sigaa_override():
    config = _config()
    values = {"__unit__N1": 8.0}
    missing = missing_components(config, values)
    keys = {component.key for component in missing}
    assert keys == {"trabalho2", "aval2"}
