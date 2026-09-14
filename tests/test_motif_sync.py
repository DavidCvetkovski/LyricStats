from sync_pg import eligible_quote


def test_quote_requires_word_and_catalogue_evidence():
    stats = {'top_words_no_stop': [['mala', 240]], 'motif_quote': {'word': 'לידיה', 'quote': 'לידיה', 'song_title': 'Wrong'}}
    assert eligible_quote(stats, [['Real']]) is None
    stats['motif_quote'] = {'word': 'mala', 'quote': 'mala', 'song_title': 'Real'}
    assert eligible_quote(stats, [['Real']]) == stats['motif_quote']
    assert eligible_quote(stats, [['Other']]) is None
