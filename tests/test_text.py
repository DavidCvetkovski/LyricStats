from lyricstats.text import all_lines, parse_sections, tokenize


def test_tokenize_handles_bhs_diacritics():
    text = "Šta ćeš ti tu, đe si bio, čovječe?"
    tokens = tokenize(text)
    assert "šta" in tokens
    assert "ćeš" in tokens
    assert "đe" in tokens
    assert "čovječe" in tokens


def test_tokenize_lowercases():
    assert tokenize("HELLO World") == ["hello", "world"]


def test_parse_sections_splits_on_brackets():
    lyrics = """[Verse 1]
line one
line two

[Chorus]
hook line
"""
    secs = parse_sections(lyrics)
    assert [s.name for s in secs] == ["Verse 1", "Chorus"]
    assert secs[0].kind == "verse"
    assert secs[1].kind == "chorus"
    assert len(secs[0].lines) == 2


def test_all_lines_strips_headers():
    lyrics = "[Intro]\nyo\n[Verse 1]\nline\nanother"
    assert all_lines(lyrics) == ["yo", "line", "another"]


def test_clean_strips_genius_preamble():
    lyrics = "5 ContributorsBombaclat Lyrics\n[Verse 1]\nfoo\n12Embed"
    secs = parse_sections(lyrics)
    assert secs[0].name == "Verse 1"
    assert "foo" in secs[0].lines
