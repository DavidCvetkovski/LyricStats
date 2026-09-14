"""Bounded motif sync. Defaults to a saved, read-only plan; never matches row IDs.

Example: uv run python sync_pg.py --artist 'Jala Brat' --output output/motif-plan.json
DATABASE_URL must be supplied explicitly in the environment. No .env auto-loading.
"""
import argparse
import json
import os
import re
import sqlite3
from pathlib import Path


def eligible_quote(stats, songs):
    quote = stats.get('motif_quote')
    if not isinstance(quote, dict):
        return None
    word = str(quote.get('word', '')).strip().casefold()
    counts = stats.get('top_words_no_stop', []) + stats.get('signature_words', [])
    if not any(str(entry[0]).casefold() == word and entry[1] > 0 for entry in counts):
        return None
    tokens = re.findall(r"[^\W\d_]+(?:['’][^\W\d_]+)*", str(quote.get('quote', '')).casefold())
    titles = [s.get('title', '') if isinstance(s, dict) else s[0] for s in songs]
    if word not in tokens or str(quote.get('song_title', '')).strip().casefold() not in {str(t).strip().casefold() for t in titles}:
        return None
    return quote


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artist', action='append', required=True, help='Exact artist name; at most 20')
    parser.add_argument('--database', default='data/lyricstats.db')
    parser.add_argument('--output', required=True, help='New plan file; existing files are preserved')
    parser.add_argument('--apply', action='store_true', help='Explicitly apply validated deltas; saves prior values in output first')
    args = parser.parse_args()
    names = list(dict.fromkeys(a.strip().lower() for a in args.artist))
    if len(names) > 20 or any(not n for n in names):
        parser.error('Supply 1–20 non-empty exact artist names.')
    # Reserve the checkpoint before contacting either database. Never overwrite one.
    with open(args.output, 'x', encoding='utf-8') as checkpoint:
        import psycopg
        url = os.environ.get('DATABASE_URL', '').replace('postgresql+psycopg://', 'postgresql://')
        if not url:
            parser.error('Set DATABASE_URL explicitly. No environment files are loaded.')
        local = sqlite3.connect(Path(args.database).resolve().as_uri() + '?mode=ro', uri=True, timeout=5)
        local.execute('PRAGMA query_only=ON')
        plans = []
        with local, psycopg.connect(url, connect_timeout=10) as remote:
            remote.execute("SET LOCAL statement_timeout = '5s'")
            if not args.apply:
                remote.execute('SET TRANSACTION READ ONLY')
            for name in names:
                source = local.execute('SELECT name, stats_json, songs_json FROM artistaggregate WHERE name = ? LIMIT 2', (name,)).fetchall()
                target = remote.execute('SELECT name, stats_json, songs_json FROM artistaggregate WHERE name = %s LIMIT 2', (name,)).fetchall()
                if len(source) != 1 or len(target) != 1:
                    plans.append({'artist': name, 'status': 'skipped: missing or ambiguous exact identity'})
                    continue
                quote = eligible_quote(json.loads(source[0][1]), json.loads(source[0][2] or '[]'))
                old = json.loads(target[0][1])
                candidate = dict(old, motif_quote=quote)
                if not quote or not eligible_quote(candidate, json.loads(target[0][2] or '[]')):
                    plans.append({'artist': name, 'status': 'skipped: quote lacks matching catalogue evidence'})
                    continue
                if old.get('motif_quote') == quote:
                    plans.append({'artist': name, 'status': 'unchanged'})
                    continue
                plans.append({'artist': name, 'status': 'planned', 'before': target[0][1], 'after': json.dumps(candidate, ensure_ascii=False)})
            json.dump({'mode': 'apply' if args.apply else 'dry-run', 'artists': plans}, checkpoint, ensure_ascii=False, indent=2)
            checkpoint.flush()
            os.fsync(checkpoint.fileno())
            if args.apply:
                for plan in plans:
                    if plan['status'] != 'planned':
                        continue
                    # Compare-and-swap preserves concurrent edits; all updates roll back on conflict.
                    result = remote.execute('UPDATE artistaggregate SET stats_json = %s WHERE name = %s AND stats_json = %s', (plan['after'], plan['artist'], plan['before']))
                    if result.rowcount != 1:
                        raise RuntimeError('Concurrent change detected; transaction rolled back. Plan preserved.')
        local.close()
    print(f"Saved {len(plans)} artist decisions to {args.output}; mode: {'apply' if args.apply else 'dry-run'}.")


if __name__ == '__main__':
    main()
