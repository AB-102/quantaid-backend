"""Quiz questions point at the lesson content they review by block label, so the links survive edits.

Questions used to store lessonContentIndices: positions among a lesson's non-image blocks. Inserting, removing or
moving a block silently re-pointed them. A labelled block keeps its `id` wherever it moves, and a question stores
the labels it reviews in lessonBlockIds.
"""

import re

# Labels are written as {#label} in the lesson source, so they stay plain and URL-safe
BLOCK_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9:_-]*$")


def _slugify(text: str, max_words: int) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return "-".join(words[:max_words])


def _new_block_id(block: dict, taken: set[str]) -> str:
    """A readable label: the heading's words, or a paragraph's first few words, made unique within the lesson."""
    max_words = 6 if block.get("type") in ("heading", "subheading") else 4
    base = _slugify(block.get("text", ""), max_words) or "block"
    block_id = base
    suffix = 2
    while block_id in taken:
        block_id = f"{base}-{suffix}"
        suffix += 1
    return block_id


def link_questions_by_block_id(blocks: list[dict], quiz: list[dict]) -> int:
    """Give each question that only has lessonContentIndices a lessonBlockIds list, labelling blocks as needed.

    Changes blocks and quiz in place and returns how many questions it linked. Questions that already have
    lessonBlockIds are left alone, so running it twice changes nothing. lessonContentIndices stays, so a
    frontend that still reads it keeps working until the lesson is next saved from the editor.
    """
    text_blocks = [block for block in blocks if block.get("type") != "image"]
    taken = {block["id"] for block in blocks if block.get("id")}
    linked = 0
    for question in quiz:
        if "lessonBlockIds" in question or not question.get("lessonContentIndices"):
            continue
        block_ids = []
        for index in question["lessonContentIndices"]:
            if not 0 <= index < len(text_blocks):
                continue  # the old link already pointed past the end of the lesson
            block = text_blocks[index]
            if not block.get("id"):
                block["id"] = _new_block_id(block, taken)
                taken.add(block["id"])
            block_ids.append(block["id"])
        question["lessonBlockIds"] = block_ids
        linked += 1
    return linked
