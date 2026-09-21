import type { ArtistPayload, ArtistStats } from './types';
import { wordsIn } from './utils';

/** A quote may only decorate the word and catalogue it actually belongs to. */
export function verifiedMotif(data: ArtistPayload) {
 const quote=data.stats.motif_quote;if(!quote)return null;
 const word=quote.word.trim().toLowerCase();
 const entries=[...data.stats.top_words_no_stop,...(data.stats.signature_words??[]).map(([w,n])=>[w,n] as [string,number])];
 const match=entries.find(([w,n])=>w.toLowerCase()===word&&Number.isFinite(n)&&n>0);
 if(!match||!wordsIn(quote.quote).includes(word)||!data.songs.some(s=>s.title.trim().toLowerCase()===quote.song_title.trim().toLowerCase()))return null;
 return {...quote,count:match[1]};
}
export function recurringWord(stats:ArtistStats):[string,number]|null {
 // This is a frequency label, not an inferred noun, language or vocal trait.
 const filler=new Set(['yeah','ooh','oh','uh','hey','the','and','that','with','this','kako','kada','znam','mene','tebe','nisam','samo']);
 return stats.top_words_no_stop.find(([word,count])=>wordsIn(word).length===1&&word.length>2&&!filler.has(word.toLowerCase())&&Number.isFinite(count)&&count>0)??null;
}
