"""Linking quiz questions to lesson content by block label (core/quiz_links.py)."""

from core.quiz_links import BLOCK_ID_PATTERN, link_questions_by_block_id
from data.default_lessons import get_lesson_documents


def _text_blocks(blocks: list[dict]) -> list[dict]:
    return [block for block in blocks if block.get("type") != "image"]


class TestLinkQuestionsByBlockId:
    def test_positions_become_labels_on_the_same_blocks(self):
        blocks = [
            {"type": "heading", "text": "Core Principles"},
            {"type": "image", "fileId": "abc"},  # positions skip images
            {"type": "paragraph", "text": "Qubits: unlike classical bits, qubits can be both."},
        ]
        quiz = [{"question": "Q?", "lessonContentIndices": [0, 1]}]
        assert link_questions_by_block_id(blocks, quiz) == 1
        assert quiz[0]["lessonBlockIds"] == ["core-principles", "qubits-unlike-classical-bits"]
        assert blocks[0]["id"] == "core-principles"
        assert blocks[2]["id"] == "qubits-unlike-classical-bits"
        assert quiz[0]["lessonContentIndices"] == [0, 1]  # kept for an older frontend

    def test_running_twice_changes_nothing(self):
        blocks = [{"type": "paragraph", "text": "Hello world"}]
        quiz = [{"question": "Q?", "lessonContentIndices": [0]}]
        link_questions_by_block_id(blocks, quiz)
        before = ([dict(b) for b in blocks], [dict(q) for q in quiz])
        assert link_questions_by_block_id(blocks, quiz) == 0
        assert (blocks, quiz) == before

    def test_labels_are_unique_and_valid(self):
        blocks = [
            {"type": "paragraph", "text": "Same start here, then one way"},
            {"type": "paragraph", "text": "Same start here, then another"},
            {"type": "paragraph", "text": "|ψ⟩ ⟨φ|"},  # no ASCII words to slug
        ]
        quiz: list[dict] = [{"question": "Q?", "lessonContentIndices": [0, 1, 2]}]
        link_questions_by_block_id(blocks, quiz)
        labels = quiz[0]["lessonBlockIds"]
        assert labels == ["same-start-here-then", "same-start-here-then-2", "block"]
        assert all(BLOCK_ID_PATTERN.match(label) for label in labels)

    def test_positions_past_the_end_are_dropped(self):
        blocks = [{"type": "paragraph", "text": "Only block"}]
        quiz = [{"question": "Q?", "lessonContentIndices": [0, 5]}]
        link_questions_by_block_id(blocks, quiz)
        assert quiz[0]["lessonBlockIds"] == ["only-block"]

    def test_existing_labels_are_reused(self):
        blocks = [{"type": "paragraph", "text": "Hello", "id": "greeting"}]
        quiz = [{"question": "Q?", "lessonContentIndices": [0]}, {"question": "Q2?", "lessonContentIndices": [0]}]
        link_questions_by_block_id(blocks, quiz)
        assert [q["lessonBlockIds"] for q in quiz] == [["greeting"], ["greeting"]]


class TestSeededLessons:
    def test_every_seeded_link_reviews_the_same_content_as_before(self):
        for lesson in get_lesson_documents():
            text_blocks = _text_blocks(lesson["blocks"])
            by_label = {block["id"]: block for block in lesson["blocks"] if block.get("id")}
            for question in lesson["quiz"]:
                old = [text_blocks[i] for i in question["lessonContentIndices"] if i < len(text_blocks)]
                new = [by_label[label] for label in question["lessonBlockIds"]]
                assert new == old, (lesson["courseId"], question["question"])

    def test_seeding_twice_gives_the_same_labels(self):
        assert get_lesson_documents()[0]["blocks"] == get_lesson_documents()[0]["blocks"]
