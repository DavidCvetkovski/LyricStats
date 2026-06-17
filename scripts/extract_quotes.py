"""Extract Signature Motif Quotes from LRCLIB using Multiprocessing."""

import argparse
import json
import multiprocessing
import os
import random
import re
import sqlite3
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lyricstats.config import DB_PATH
from lyricstats.db import ArtistAggregate
from sqlmodel import Session, create_engine, select

LRCLIB_DB_PATH = os.path.join("data", "data_backup", "lrclib", "lrclib.sqlite3")
if not os.path.exists(LRCLIB_DB_PATH):
    LRCLIB_DB_PATH = os.path.join("data", "lrclib", "lrclib.sqlite3")

AD_LIBS = {"ooh", "ah", "oh", "uh", "la", "da", "na", "hey", "whoa", "yeh", "yeah", "imma", "yes", "no", "doo", "christmas", "bam"}

def get_target_motif_word(stats: dict, artist_name: str) -> str | None:
    signature_words = stats.get("signature_words", [])
    top_words = stats.get("top_words_no_stop", [])
    forbidden = set(artist_name.lower().split())
    
    # 1. Use Mathematical Scoring: Count * Log(Ratio)
    if signature_words:
        for w, count, score in signature_words:
            if len(w) <= 2: continue
            if "'" in w or "’" in w: continue
            if w in AD_LIBS or w in forbidden: continue
            return w
    
    # 2. Fallback to Frequency if no TF-IDF signatures
    if top_words:
        for w, count in top_words:
            if len(w) <= 2: continue
            if "'" in w or "’" in w: continue
            if w in AD_LIBS or w in forbidden: continue
            return w
            
    # 3. Absolute Desperate Fallback
    if top_words:
        for w, count in top_words:
            if len(w) <= 2: continue
            if "'" in w or "’" in w: continue
            if w in forbidden: continue
            return w
            
    if top_words:
        return top_words[0][0]
    return None

def score_lyric_line(line: str, word: str) -> float:
    """Score a candidate line. Returns higher score for better quotes."""
    if not line: return -100
    if line.startswith("[") or line.endswith("]"): return -100
    if line.startswith("(") and line.endswith(")"): return -100
    
    words = line.split()
    length = len(words)
    if length < 4 or length > 20:
        return -50 
        
    score = 0
    if 6 <= length <= 12:
        score += 20
        
    if line[0].isupper():
        score += 10
        
    if line.isupper():
        score -= 20
        
    unique_words = len(set(w.lower() for w in words))
    if length > 0 and (unique_words / length) < 0.6:
        score -= 50
        
    return score

def worker_process(artist_chunk):
    """Worker process that scans the LRCLIB SQLite DB for a chunk of artists."""
    try:
        conn = sqlite3.connect(LRCLIB_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        results = []
        
        for artist_id, artist_name, motif_word in artist_chunk:
            regex_pattern = r'\b' + re.escape(motif_word) + r'\b'
            compiled_re = re.compile(regex_pattern, re.IGNORECASE)
            
            cursor.execute(
                '''
                SELECT t.name, l.plain_lyrics 
                FROM tracks t 
                JOIN lyrics l ON t.last_lyrics_id = l.id 
                WHERE t.artist_name_lower = ? AND l.plain_lyrics IS NOT NULL
                ''', (artist_name,)
            )
            
            best_quote = None
            best_score = -9999
            best_title = None
            
            for row in cursor.fetchall():
                title = row["name"]
                lyrics = row["plain_lyrics"]
                
                for line in lyrics.split("\n"):
                    line = line.strip()
                    if compiled_re.search(line):
                        score = score_lyric_line(line, motif_word)
                        if score > best_score:
                            best_score = score
                            best_quote = line
                            best_title = title
                            
            if best_quote:
                results.append((artist_id, motif_word, best_quote, best_title))
                
        conn.close()
        return results
    except Exception as e:
        print(f"Worker process failed: {e}")
        return []

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="Limit number of artists to process for testing")
    args = parser.parse_args()
    
    if not os.path.exists(LRCLIB_DB_PATH):
        print(f"Error: LRCLIB database not found at {LRCLIB_DB_PATH}")
        return
        
    engine = create_engine(f"sqlite:///{DB_PATH}")
    
    with Session(engine) as session:
        statement = select(ArtistAggregate)
        if args.limit:
            statement = statement.limit(args.limit)
            
        aggregates = session.exec(statement).all()
        
    tasks = []
    for agg in aggregates:
        if not agg.stats_json: continue
        stats = json.loads(agg.stats_json)
        motif_word = get_target_motif_word(stats, agg.name)
        if motif_word:
            tasks.append((agg.id, agg.name, motif_word))
            
    if not tasks:
        print("No artists found with valid motifs.")
        return
        
    print(f"Loaded {len(tasks)} artists. Shuffling and chunking for multiprocessing...")
    random.shuffle(tasks)
    
    num_cores = multiprocessing.cpu_count()
    chunk_size = max(1, len(tasks) // (num_cores * 4))
    chunks = [tasks[i:i + chunk_size] for i in range(0, len(tasks), chunk_size)]
    
    results = []
    print(f"Starting {num_cores} workers...")
    
    with ProcessPoolExecutor(max_workers=num_cores) as executor:
        futures = {executor.submit(worker_process, chunk): chunk for chunk in chunks}
        
        for future in tqdm(as_completed(futures), total=len(chunks), desc="Processing chunks"):
            try:
                res = future.result()
                if res:
                    results.extend(res)
            except Exception as e:
                print(f"Future exception: {e}")
                
    print(f"Finished extracting quotes. Found quotes for {len(results)} artists.")
    
    print("Updating main database...")
    with Session(engine) as session:
        for artist_id, word, quote, title in tqdm(results, desc="Writing to DB"):
            agg = session.get(ArtistAggregate, artist_id)
            if not agg: continue
            
            stats = json.loads(agg.stats_json) if agg.stats_json else {}
            stats["motif_quote"] = {
                "word": word,
                "quote": quote,
                "song_title": title
            }
            agg.stats_json = json.dumps(stats, ensure_ascii=False)
            session.add(agg)
            
        session.commit()
        
    print("Done!")

if __name__ == "__main__":
    main()
