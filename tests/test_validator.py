# tests/test_validator.py
import pytest
from aptitude.models import SkillDraft
from aptitude.validate.validator import validate_draft, validate_skill_dir
from aptitude.errors import ValidationError

def test_valid_draft_no_error():
    assert validate_draft(SkillDraft("good-name", "Use when X.", "This is a valid body that is long enough to avoid triggering the warning.")) == []

def test_bad_name_raises():
    with pytest.raises(ValidationError):
        validate_draft(SkillDraft("Bad Name!", "d", "b"))

def test_empty_description_raises():
    with pytest.raises(ValidationError):
        validate_draft(SkillDraft("n", "", "b"))

def test_validate_skill_dir(tmp_path):
    d = tmp_path / "n"; d.mkdir()
    (d / "SKILL.md").write_text("---\nname: n\ndescription: Use when X.\n---\nThis is a valid body that is long enough to avoid triggering the warning.")
    assert validate_skill_dir(d) == []
    (d / "SKILL.md").write_text("no frontmatter")
    with pytest.raises(ValidationError):
        validate_skill_dir(d)
