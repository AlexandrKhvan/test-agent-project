from curriculum.material_index import build_course_digest, retrieve_relevant_chunks, split_material_into_chunks


def test_split_material_keeps_each_markdown_section() -> None:
    material = "# Intro\nA" * 1 + "\n# Graphs\nBreadth first search" + "\n# SQL\nSELECT rows"

    chunks = split_material_into_chunks(material, chunk_size=30, overlap=5)

    assert any("Intro" in chunk["title"] for chunk in chunks)
    assert any("Graphs" in chunk["content"] for chunk in chunks)
    assert any("SQL" in chunk["content"] for chunk in chunks)


def test_digest_represents_late_sections_within_budget() -> None:
    chunks = [
        {"id": "section-1", "title": "First", "content": "first material " * 30},
        {"id": "section-2", "title": "Last", "content": "last material " * 30},
    ]

    digest = build_course_digest(chunks, max_chars=180)

    assert len(digest) <= 180
    assert "First" in digest
    assert "Last" in digest


def test_retrieval_prioritizes_matching_section_title() -> None:
    chunks = [
        {"id": "section-1", "title": "Graphs", "content": "Breadth first search uses a queue."},
        {"id": "section-2", "title": "SQL", "content": "SELECT filters database rows."},
    ]

    selected = retrieve_relevant_chunks("How does SQL SELECT work?", chunks, limit=1)

    assert selected[0]["id"] == "section-2"
