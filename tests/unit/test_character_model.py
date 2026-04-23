"""
Tests for Character relationship model and related functionality
"""
import pytest
from pydantic import ValidationError

from src.model import Character, CharacterRelationship, NovelOutline, ChapterOutline


class TestCharacterRelationshipModel:
    """Tests for CharacterRelationship model validation"""

    def test_valid_relationship_creation(self):
        """Test creating a valid CharacterRelationship"""
        relationship = CharacterRelationship(
            source="张三",
            target="李四",
            relationship_type="兄弟",
            description="同父异母的兄弟",
            events=["童年一起玩耍", "成年后分道扬镳"]
        )

        assert relationship.source == "张三"
        assert relationship.target == "李四"
        assert relationship.relationship_type == "兄弟"
        assert relationship.description == "同父异母的兄弟"
        assert len(relationship.events) == 2

    def test_relationship_with_empty_events(self):
        """Test relationship with empty events list"""
        relationship = CharacterRelationship(
            source="张三",
            target="李四",
            relationship_type="父子",
            description="亲生父子"
        )

        assert relationship.events == []

    def test_relationship_missing_required_field_source(self):
        """Test that source is required"""
        with pytest.raises(ValidationError) as exc_info:
            CharacterRelationship(
                target="李四",
                relationship_type="兄弟",
                description="测试"
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("source",) for e in errors)

    def test_relationship_missing_required_field_target(self):
        """Test that target is required"""
        with pytest.raises(ValidationError) as exc_info:
            CharacterRelationship(
                source="张三",
                relationship_type="兄弟",
                description="测试"
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("target",) for e in errors)

    def test_relationship_missing_required_field_type(self):
        """Test that relationship_type is required"""
        with pytest.raises(ValidationError) as exc_info:
            CharacterRelationship(
                source="张三",
                target="李四",
                description="测试"
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("relationship_type",) for e in errors)

    def test_relationship_missing_required_field_description(self):
        """Test that description is required"""
        with pytest.raises(ValidationError) as exc_info:
            CharacterRelationship(
                source="张三",
                target="李四",
                relationship_type="朋友"
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("description",) for e in errors)


class TestCharacterModel:
    """Tests for Character model with relationships field"""

    def test_character_without_relationships(self):
        """Test creating a Character without relationships"""
        character = Character(
            name="张三",
            background="出身于农村",
            personality="正直勇敢",
            goals=["成为武林高手", "保护家人"],
            conflicts=["与反派的对抗", "内心的挣扎"],
            arc="从软弱到坚强的成长"
        )

        assert character.name == "张三"
        assert character.relationships == []
        assert len(character.goals) == 2
        assert len(character.conflicts) == 2

    def test_character_with_single_relationship(self):
        """Test creating a Character with a single relationship"""
        relationship = CharacterRelationship(
            source="张三",
            target="李四",
            relationship_type="兄弟",
            description="同父异母"
        )

        character = Character(
            name="张三",
            background="测试背景",
            personality="开朗",
            goals=["目标1"],
            conflicts=["冲突1"],
            arc="成长弧线",
            relationships=[relationship]
        )

        assert len(character.relationships) == 1
        assert character.relationships[0].relationship_type == "兄弟"

    def test_character_with_multiple_relationships(self):
        """Test creating a Character with multiple relationships"""
        relationships = [
            CharacterRelationship(
                source="张三",
                target="李四",
                relationship_type="兄弟",
                description="兄弟关系"
            ),
            CharacterRelationship(
                source="张三",
                target="王五",
                relationship_type="师徒",
                description="师徒关系",
                events=["传授武功"]
            ),
            CharacterRelationship(
                source="张三",
                target="赵六",
                relationship_type="恋人",
                description="青梅竹马",
                events=["小时候定下婚约", "成年后重逢"]
            )
        ]

        character = Character(
            name="张三",
            background="测试背景",
            personality="开朗",
            goals=["目标1"],
            conflicts=["冲突1"],
            arc="成长弧线",
            relationships=relationships
        )

        assert len(character.relationships) == 3

        # Verify relationship types
        types = [r.relationship_type for r in character.relationships]
        assert "兄弟" in types
        assert "师徒" in types
        assert "恋人" in types

    def test_character_missing_required_field_name(self):
        """Test that name is required"""
        with pytest.raises(ValidationError) as exc_info:
            Character(
                background="测试",
                personality="开朗",
                goals=[],
                conflicts=[],
                arc="成长"
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("name",) for e in errors)

    def test_character_missing_required_field_goals(self):
        """Test that goals is required"""
        with pytest.raises(ValidationError) as exc_info:
            Character(
                name="张三",
                background="测试",
                personality="开朗",
                conflicts=[],
                arc="成长"
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("goals",) for e in errors)

    def test_character_with_empty_goals_list(self):
        """Test that goals can be empty list"""
        character = Character(
            name="张三",
            background="测试",
            personality="开朗",
            goals=[],
            conflicts=[],
            arc="成长"
        )

        assert character.goals == []

    def test_character_relationships_is_list(self):
        """Test that relationships field is a list"""
        character = Character(
            name="测试",
            background="背景",
            personality="性格",
            goals=["目标"],
            conflicts=["冲突"],
            arc="弧线",
            relationships=[]  # Should accept empty list
        )

        assert isinstance(character.relationships, list)


class TestCharacterRelationshipEdgeCases:
    """Edge case tests for character relationships"""

    def test_relationship_with_unicode_characters(self):
        """Test relationship with Chinese characters"""
        relationship = CharacterRelationship(
            source="张三",
            target="李四",
            relationship_type="父子",
            description="他们是父子关系",
            events=["一起吃饭", "讨论未来"]
        )

        assert relationship.source == "张三"
        assert relationship.description == "他们是父子关系"

    def test_relationship_type_varieties(self):
        """Test various relationship types"""
        types = ["父子", "母子", "兄弟", "姐妹", "恋人", "夫妻", "师徒", "朋友", "敌对", "主仆"]

        for rel_type in types:
            relationship = CharacterRelationship(
                source="A",
                target="B",
                relationship_type=rel_type,
                description=f"{rel_type}关系"
            )
            assert relationship.relationship_type == rel_type

    def test_relationship_with_many_events(self):
        """Test relationship with many events"""
        events = [f"事件{i}" for i in range(100)]

        relationship = CharacterRelationship(
            source="张三",
            target="李四",
            relationship_type="兄弟",
            description="有很多事件的关系",
            events=events
        )

        assert len(relationship.events) == 100

    def test_character_can_have_relationships_to_self(self):
        """Test if relationship can reference same character (self-reference)"""
        # Note: This might be valid in some scenarios (self-reflection, internal conflict)
        relationship = CharacterRelationship(
            source="张三",
            target="张三",
            relationship_type="内心",
            description="与自己内心的对话"
        )

        assert relationship.source == relationship.target

    def test_multiple_characters_with_same_relationship(self):
        """Test multiple characters having relationships to each other"""
        char1 = Character(
            name="张三",
            background="背景1",
            personality="性格1",
            goals=["目标1"],
            conflicts=["冲突1"],
            arc="弧线1",
            relationships=[
                CharacterRelationship(
                    source="张三",
                    target="李四",
                    relationship_type="兄弟",
                    description="兄弟"
                )
            ]
        )

        char2 = Character(
            name="李四",
            background="背景2",
            personality="性格2",
            goals=["目标2"],
            conflicts=["冲突2"],
            arc="弧线2",
            relationships=[
                CharacterRelationship(
                    source="李四",
                    target="张三",
                    relationship_type="兄弟",
                    description="兄弟"
                )
            ]
        )

        assert len(char1.relationships) == 1
        assert len(char2.relationships) == 1
        assert char1.relationships[0].target == "李四"
        assert char2.relationships[0].target == "张三"