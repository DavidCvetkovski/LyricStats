"use client";
import type { ArtistStats } from '@/lib/types';
import { Count, Reveal } from './EditorialMotion';
import { recurringWord } from '@/lib/artistEvidence';

type Props={artistName:string;stats:ArtistStats;topFreqNoun?:[string,number]|null};
export function ArtistStory({artistName,stats}:Props) {
 const word=recurringWord(stats);
 const cards=[
 {label:'The Output',value:stats.avg_words_per_song,suffix:'',unit:'words in the average song',copy:<>{artistName} fills an average song with <em className="text-accent">{Math.round(stats.avg_words_per_song).toLocaleString()} words.</em> A catalogue of {stats.song_count.toLocaleString()} songs, read one page at a time.</>,note:'The mean word count of the indexed songs. Longer does not necessarily mean faster.'},
 {label:'The Vocabulary',value:stats.avg_ttr*100,suffix:'%',unit:'mean word variety',copy:<>For every hundred words, about <em className="text-accent">{Math.round(stats.avg_ttr*100)} are distinct</em> in the average song.</>,note:'Distinct words divided by total words, calculated per song and then averaged. Shorter songs tend to score higher.'},
 {label:'The Echo',value:stats.avg_repetition_ratio*100,suffix:'%',unit:'mean repeated-line share',copy:<>About <em className="text-accent">{Math.round(stats.avg_repetition_ratio*100)} in every hundred lines</em> repeat an earlier line in the average song.</>,note:'Extra appearances of identical lines, averaged per song. This measures text repetition, not chorus length.'},
 ].filter(c=>Number.isFinite(c.value));
 return <div className="mt-16 mb-20 divide-y divide-rule">
 {cards.map((card,i)=><Reveal key={card.label} className={`py-14 sm:py-20 max-w-4xl mx-auto ${i===1?'md:text-right':''}`}>
  <div className={i===0&&word?'grid md:grid-cols-[1fr_280px] gap-10 items-center':''}>
   <div><h3 className="font-serif italic text-2xl sm:text-3xl lg:text-4xl leading-relaxed mb-10">{card.copy}</h3>
    <p className="smallcaps mb-5">{['I','II','III'][i]}. {card.label}</p>
    <div className="figure text-ink" style={{fontSize:'clamp(5rem,17vw,10rem)'}}><Count value={card.value} suffix={card.suffix}/></div>
    <p className="font-serif text-xl italic text-ink-soft mt-3">{card.unit}</p>
    <div className="h-px bg-rule-strong my-7"/>
    <p className={`text-sm text-ink-mute leading-relaxed max-w-lg ${i===1?'md:ml-auto':''}`}>{card.note}</p>
   </div>
   {i===0&&word&&<aside className="border border-rule-strong p-7 bg-paper-soft text-center relative shadow-sm">
    <div className="absolute inset-1 border border-dashed border-rule-strong pointer-events-none"/>
    <p className="smallcaps">A recurring word</p><p translate="no" className="notranslate font-serif italic text-5xl my-6 break-words">“{word[0]}”</p>
    <p className="font-serif text-lg"><strong>{word[1].toLocaleString()}</strong> recorded appearances</p><p className="text-xs text-ink-mute mt-3 leading-relaxed">In the indexed catalogue of {stats.song_count} songs. It may appear in only some of them.</p>
   </aside>}
  </div>
 </Reveal>)}
 </div>;
}
