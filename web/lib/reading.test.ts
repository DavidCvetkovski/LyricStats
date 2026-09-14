import { describe, it, expect } from 'vitest';
import { readLyrics, localSong, wordsIn } from './reading';
import { verifiedMotif } from './artistEvidence';
import type { ArtistPayload } from './types';
describe('reading actual text',()=>{
 it('tracks returns and where new words arrive, excluding section labels',()=>{
  const r=readLyrics('[Verse]\nRed moon\nBlue sky\n[Chorus]\nRed moon\nNew dawn');
  expect(r.total).toBe(8);expect(r.unique).toBe(6);expect(r.repeated).toBe(1);
  expect(r.repeatGroups).toEqual([[0,2]]);expect(r.newInSecond).toBe(2);
  expect(r.lines.map(l=>l.vocabulary)).toEqual([2,4,4,6]);expect(r.lines[2].section).toBe('Chorus');
 });
 it('does not invent words or divide by zero for empty input',()=>{
  expect(readLyrics('[Intro]\n...').lines).toEqual([]);
  expect(localSong('','','').stats.repetition_ratio).toBe(0);
 });
 it('retains multilingual words, including Hebrew and apostrophes',()=>{
  expect(wordsIn("Noćas לידיה don't")).toEqual(['noćas','לידיה',"don't"]);
 });
 it('marks pasted text local and keeps it out of remote sources',()=>{
  expect(localSong('Me','New song','Blue moon\nBlue moon').source).toBe('local');
 });
});
describe('artist quotation evidence',()=>{
 const base={stats:{top_words_no_stop:[['mala',240]],motif_quote:{word:'לידיה',quote:'לידיה',song_title:'Wrong song'}},songs:[{title:'Real song'}]} as ArtistPayload;
 it('rejects a foreign catalogue quote without borrowing another word’s count',()=>expect(verifiedMotif(base)).toBeNull());
 it('accepts a evidenced non-Latin quote, rather than banning a language',()=>{
  const data={...base,stats:{...base.stats,top_words_no_stop:[['לידיה',7]],motif_quote:{word:'לידיה',quote:'לידיה',song_title:'Real song'}}} as ArtistPayload;
  expect(verifiedMotif(data)?.count).toBe(7);
 });
 it('requires the quoted track to belong to this catalogue',()=>{
  expect(verifiedMotif({...base,stats:{...base.stats,motif_quote:{word:'mala',quote:'mala',song_title:'Wrong song'}}})).toBeNull();
 });
});
