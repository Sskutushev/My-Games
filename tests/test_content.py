from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from dl_toolkit.content import (
    CURRENT_SCHEMA_VERSION,
    Attribute,
    CharacterClass,
    ClassTier,
    ItemGrade,
    LevelStep,
    MagicSchool,
    ProgressionCurve,
    Race,
    Ruleset,
    Skill,
    SkillAccess,
    SkillGroup,
    ValidationError,
    load_ruleset,
    parse_ruleset,
)
from dl_toolkit.content.models import CLASS_SLOTS, RACE_SLOTS, SKILL_SLOTS


def make_race(**overrides: Any) -> Race:
    base = {
        "slot": 0,
        "key": "virn",
        "name_ru": "Вирн",
        "name_en": "Virn",
        "base_attributes": dict.fromkeys(Attribute, 12),
        "life": 46,
        "speed_bonus": 0,
        "parry_bonus": 1,
        "playable": True,
        "summary": "",
    }
    return Race(**{**base, **overrides})


def make_class(**overrides: Any) -> CharacterClass:
    base = {
        "slot": 1,
        "key": "blade",
        "name_ru": "Клинок",
        "name_en": "Blade",
        "tier": ClassTier.BASE,
        "guild": "steel",
        "parent": None,
        "requirements": {},
        "required_level": 1,
        "quest_register": None,
        "skills": (),
        "summary": "",
    }
    return CharacterClass(**{**base, **overrides})


# ------------------------------------------------------------------ модели


def test_engine_slot_constants_are_fixed():
    assert (RACE_SLOTS, CLASS_SLOTS, SKILL_SLOTS) == (16, 35, 45)
    assert len(MagicSchool) == 4
    assert len(Attribute) == 6
    assert ItemGrade.OBSIDIAN.value == "obsidian"


def test_string_ids_follow_engine_ranges():
    assert make_race(slot=3).string_id == 1303
    assert make_class(slot=5).string_id == 1405
    assert Skill(4, "heavy", "Тяжёлое", SkillGroup.MELEE, "").string_id == 1804


def test_race_validation():
    make_race().validate()
    with pytest.raises(ValidationError, match="вне 0"):
        make_race(slot=99).validate()
    with pytest.raises(ValidationError, match="не заданы атрибуты"):
        make_race(base_attributes={Attribute.STRENGTH: 10}).validate()
    with pytest.raises(ValidationError, match="вне разумного диапазона"):
        make_race(base_attributes=dict.fromkeys(Attribute, 99)).validate()


def test_skill_validation():
    Skill(0, "brawl", "Рукопашный", SkillGroup.MELEE, "").validate()
    with pytest.raises(ValidationError, match="вне 0"):
        Skill(99, "x", "X", SkillGroup.MELEE, "").validate()


def test_class_validation():
    make_class().validate()
    with pytest.raises(ValidationError, match="вне 0"):
        make_class(slot=99).validate()
    with pytest.raises(ValidationError, match="пустое имя"):
        make_class(name_ru="").validate()
    with pytest.raises(ValidationError, match="должен быть родитель"):
        make_class(tier=ClassTier.ELITE, parent=None).validate()
    with pytest.raises(ValidationError, match="не заданы требования"):
        make_class(tier=ClassTier.ELITE, parent="blade", requirements={}).validate()


def test_skill_access_cap_bounds():
    make_class(skills=(SkillAccess("brawl", 5, ClassTier.BASE),)).validate()
    with pytest.raises(ValidationError, match="предел"):
        make_class(skills=(SkillAccess("brawl", 99, ClassTier.BASE),)).validate()


def test_progression_curve():
    curve = ProgressionCurve([LevelStep(1, 0, 0, 10), LevelStep(2, 100, 2, 4)])
    curve.validate()
    assert curve.max_level == 2
    assert curve.xp_for(2) == 100
    assert curve.level_at(0) == 1
    assert curve.level_at(99) == 1
    assert curve.level_at(100) == 2
    with pytest.raises(KeyError):
        curve.xp_for(9)


def test_progression_validation_errors():
    with pytest.raises(ValidationError, match="пуста"):
        ProgressionCurve().validate()
    with pytest.raises(ValidationError, match="подряд начиная с 1"):
        ProgressionCurve([LevelStep(2, 0, 0, 0)]).validate()
    with pytest.raises(ValidationError, match="опыт не растёт"):
        ProgressionCurve([LevelStep(1, 10, 0, 0), LevelStep(2, 5, 0, 0)]).validate()
    with pytest.raises(ValidationError, match=">= 1"):
        LevelStep(0, 0, 0, 0).validate()
    with pytest.raises(ValidationError, match="отрицательный опыт"):
        LevelStep(1, -1, 0, 0).validate()


def test_ruleset_cross_checks():
    ruleset = Ruleset(
        title_ru="Т",
        title_en="T",
        races=[make_race()],
        skills=[Skill(0, "brawl", "Рукопашный", SkillGroup.MELEE, "")],
        classes=[make_class(skills=(SkillAccess("brawl", 5, ClassTier.BASE),))],
        progression=ProgressionCurve([LevelStep(1, 0, 0, 10)]),
    )
    ruleset.validate()
    assert ruleset.playable_races() == ruleset.races
    assert ruleset.classes_by_tier(ClassTier.BASE)[0].key == "blade"
    assert ruleset.skill_matrix() == {"blade": {"brawl": 5}}

    ruleset.classes[0] = make_class(skills=(SkillAccess("нет_такого", 5, ClassTier.BASE),))
    with pytest.raises(ValidationError, match="неизвестный навык"):
        ruleset.validate()


def test_ruleset_rejects_duplicate_slots_and_bad_parent():
    ruleset = Ruleset(
        title_ru="Т",
        title_en="T",
        races=[make_race(slot=0, key="a"), make_race(slot=0, key="b")],
        progression=ProgressionCurve([LevelStep(1, 0, 0, 0)]),
    )
    with pytest.raises(ValidationError, match="слоты заняты дважды"):
        ruleset.validate()

    ruleset = Ruleset(
        title_ru="Т",
        title_en="T",
        classes=[
            make_class(tier=ClassTier.ELITE, parent="ghost", requirements={Attribute.STRENGTH: 10})
        ],
        progression=ProgressionCurve([LevelStep(1, 0, 0, 0)]),
    )
    with pytest.raises(ValidationError, match="неизвестный родитель"):
        ruleset.validate()


# ------------------------------------------------------------------ загрузка


MINIMAL: dict[str, Any] = {
    "schema_version": CURRENT_SCHEMA_VERSION,
    "title_ru": "Тест",
    "title_en": "Test",
    "races": [
        {
            "slot": 0,
            "key": "virn",
            "name_ru": "Вирн",
            "attributes": {a.value: 12 for a in Attribute},
        }
    ],
    "skills": [{"slot": 0, "key": "brawl", "name_ru": "Рукопашный", "group": "melee"}],
    "classes": [
        {
            "slot": 1,
            "key": "blade",
            "name_ru": "Клинок",
            "tier": "base",
            "skills": [{"skill": "brawl", "cap": 5}],
        }
    ],
    "progression": [{"level": 1, "total_xp": 0, "skill_points": 10}],
}


def test_parse_minimal_document():
    ruleset = parse_ruleset(MINIMAL)
    ruleset.validate()
    assert ruleset.title_ru == "Тест"
    assert ruleset.races[0].string_id == 1300


def test_parse_rejects_wrong_schema_version():
    with pytest.raises(ValidationError, match="версия схемы"):
        parse_ruleset({**MINIMAL, "schema_version": 1})


def test_parse_reports_missing_fields():
    broken = {**MINIMAL, "races": [{"key": "virn"}]}
    with pytest.raises(ValidationError, match="отсутствует обязательное поле 'slot'"):
        parse_ruleset(broken)
    with pytest.raises(ValidationError, match="отсутствует обязательное поле 'title_ru'"):
        parse_ruleset({"schema_version": CURRENT_SCHEMA_VERSION, "title_en": "T"})


def test_parse_rejects_unknown_attribute():
    broken = {**MINIMAL, "races": [{**MINIMAL["races"][0], "attributes": {"luck": 5}}]}
    with pytest.raises(ValidationError, match="неизвестный атрибут"):
        parse_ruleset(broken)


def test_load_ruleset_from_disk(tmp_path: Path):
    path = tmp_path / "rules.yaml"
    path.write_text(yaml.safe_dump(MINIMAL, allow_unicode=True), "utf-8")
    assert load_ruleset(path).title_en == "Test"


def test_load_ruleset_rejects_non_mapping(tmp_path: Path):
    path = tmp_path / "rules.yaml"
    path.write_text("- 1\n- 2\n", "utf-8")
    with pytest.raises(ValidationError, match="ожидался словарь"):
        load_ruleset(path)


# ------------------------------------------------------------------ реальный свод


def test_shipped_ruleset_matches_engine_layout(ruleset_path: Path):
    """Свод обязан ровно укладываться в слоты движка, иначе патч сломает игру."""
    ruleset = load_ruleset(ruleset_path)
    assert ruleset.title_ru == "Обсидиановые Врата"
    assert len(ruleset.races) == RACE_SLOTS
    assert len(ruleset.classes) == CLASS_SLOTS
    assert len(ruleset.skills) == SKILL_SLOTS
    assert len(ruleset.playable_races()) == 5
    assert len(ruleset.classes_by_tier(ClassTier.BASE)) == 4
    assert len(ruleset.classes_by_tier(ClassTier.SPECIALIST)) == 15
    assert len(ruleset.classes_by_tier(ClassTier.ELITE)) == 15
    assert ruleset.progression.max_level == 40


def test_shipped_ruleset_progression_is_monotonic(ruleset_path: Path):
    curve = load_ruleset(ruleset_path).progression
    totals = [curve.xp_for(level) for level in range(1, curve.max_level + 1)]
    assert totals == sorted(totals)
    assert totals[0] == 0
    assert curve.level_at(totals[-1]) == curve.max_level


def test_shipped_ruleset_elites_are_gated(ruleset_path: Path):
    for entry in load_ruleset(ruleset_path).classes_by_tier(ClassTier.ELITE):
        assert entry.required_level >= 16
        assert entry.quest_register
        assert entry.requirements
        assert max(a.cap for a in entry.skills) >= 9
