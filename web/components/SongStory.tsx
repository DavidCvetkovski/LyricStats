"use client";
import { useMemo, useState } from 'react';
import type { SongPayload } from '@/lib/types';
import { readLyrics, wordsIn } from '@/lib/reading';
import { Count, Reveal } from './EditorialMotion';
import { MusicLinks } from './MusicLinks';

export function SongStory({song,onExpand,expanding}:{song:SongPayload;onExpand:()=>void;expanding:boolean}) {
 const reading=useMemo(()=>readLyrics(song.lyrics),[song.lyrics]);
 const full=song.analysis_complete!==false&&reading.lines.length>0;
 const [active,setActive]=useState(0);
 const [mapMode,setMapMode]=useState<'length'|'return'>('length');
 const [word,setWord]=useState('');
 const s=song.stats;
 const repeat=full?reading.repeated/reading.lines.length:s.repetition_ratio;
 const unique=full?reading.unique:s.unique_words;
 const total=full?reading.total:s.word_count;
 const selected=reading.lines[active]??reading.lines[0];
 const maxWords=Math.max(1,...reading.lines.map(l=>l.words));
 const term=word.trim().toLowerCase()||reading.topWords[0]?.[0]||'';
 const matches=reading.lines.filter(l=>wordsIn(l.text).includes(term));
 const curve=reading.lines.map((l,i)=>`${i? 'L':'M'} ${reading.lines.length>1?i/(reading.lines.length-1)*600:0} ${150-l.vocabulary/Math.max(1,unique)*130}`).join(' ');
 return <article className="mt-16 sm:mt-24" key={`${song.artist}:${song.title}`}>
  <header className="text-center border-b border-rule-strong pb-10 sm:pb-14">
   <p className="smallcaps text-accent mb-5">{song.source==='local'?'Your words, examined':'A close reading'}</p>
   <h1 translate="no" className="display notranslate mx-auto break-words" style={{fontSize:'clamp(3.5rem,10vw,8rem)',maxWidth:'18ch'}}>{song.title}</h1>
   <p translate="no" className="font-serif text-xl sm:text-2xl italic text-ink-soft mt-6">{song.artist}{song.album?` · ${song.album}`:''}{song.year?` · ${song.year}`:''}</p>
   {song.source!=='local'&&<MusicLinks artist={song.artist} title={song.title} showArtist/>}
   <p className="smallcaps mt-6">{total.toLocaleString()} words · {unique.toLocaleString()} distinct{full?` · ${reading.lines.length} lines`:''}</p>
   <nav aria-label="In this reading" className="flex flex-wrap justify-center gap-x-6 gap-y-3 mt-7 text-xs text-ink-soft">
    <a className="reading-link" href="#song-echo">The echo</a>{full&&<><a className="reading-link" href="#song-shape">The shape</a><a className="reading-link" href="#song-vocabulary">The unfolding</a><a className="reading-link" href="#song-words">The words</a></>}
   </nav>
  </header>
  {!full&&<div className="mt-8 flex flex-wrap items-center justify-between gap-5 border border-rule p-5 bg-paper-soft">
   <p className="font-serif text-lg italic max-w-xl text-ink-soft">The catalogue gives us the outline. Open the text to trace how the song moves, where lines return, and which words arrive last.</p>
   <button className="pill" disabled={expanding} onClick={onExpand}>{expanding?'Opening the text…':'Explore the full song →'}</button>
  </div>}
  <section id="song-echo" className="scroll-mt-8"><Reveal className="py-14 sm:py-24 grid md:grid-cols-[1.3fr_1fr] gap-10 md:gap-20 items-center">
   <div><p className="smallcaps mb-6">I. The echo</p><h2 className="font-serif text-3xl sm:text-4xl italic leading-snug max-w-xl">
    {repeat===0?<>Every line arrives <em className="text-accent">for the first time.</em></>:repeat>=0.45?<>This song keeps <em className="text-accent">coming back to itself.</em></>:<>Some lines move on.<br/>Others <em className="text-accent">come back.</em></>}
   </h2><div className="figure mt-8" style={{fontSize:'clamp(5rem,18vw,11rem)'}}><Count value={repeat*100} suffix="%"/></div>
   <p className="font-serif text-xl italic text-ink-soft mt-3">of line appearances repeat something already said</p>
   <p className="text-sm leading-relaxed text-ink-mute mt-5 max-w-md">{full?`${reading.repeated} repeated appearances among ${reading.lines.length} lines. `:'From the stored song analysis. '}Identical text counts as a return; a repeated melody with different words does not.</p></div>
   <aside className="border-y border-rule-strong py-7">
    {full&&reading.repeatGroups[0]?<><p className="smallcaps mb-5">The line that returns most</p><blockquote translate="no" className="font-serif italic text-2xl sm:text-3xl leading-relaxed break-words">“{reading.lines[reading.repeatGroups[0][0]].text}”</blockquote><p className="smallcaps mt-6 text-accent">{reading.repeatGroups[0].length} appearances · first at line {reading.repeatGroups[0][0]+1}</p><div className="flex flex-wrap gap-2 mt-6">{reading.repeatGroups[0].map((index,i)=><a key={index} href="#song-shape" className="echo-return" aria-label={`Explore appearance ${i+1}, line ${index+1}`} onClick={()=>{setActive(index);setMapMode('return');}}>{index+1}</a>)}</div></>:
     <><p className="smallcaps mb-5">A hundred-line illustration</p><div className="grid grid-cols-10 gap-2" aria-hidden>{Array.from({length:100},(_,i)=><span key={i} className={`aspect-square ${i<Math.round(repeat*100)?'bg-accent':'bg-paper-deep'}`}/>)}</div><p className="text-xs text-ink-mute mt-4">Red represents the repeated share. This illustration is not the song’s structure.</p></>}
   </aside>
  </Reveal></section>
  {full&&<>
   <section id="song-shape" className="scroll-mt-8 border-y border-rule-strong py-10 sm:py-14"><Reveal>
    <div className="flex flex-wrap justify-between gap-5 items-end"><div><p className="smallcaps mb-4">II. The shape of a song</p><h2 className="display text-4xl sm:text-5xl">Follow the lines.</h2></div>
     <div className="reading-switch" aria-label="Song map mode"><button aria-pressed={mapMode==='length'} onClick={()=>setMapMode('length')}>Line length</button><button aria-pressed={mapMode==='return'} onClick={()=>setMapMode('return')}>Returning lines</button></div>
    </div><p className="font-serif italic text-lg text-ink-soft mt-5 max-w-2xl">{mapMode==='length'?'Short breaths, long passages. Each mark is a line; its height is its word count.':'A song remembers. Red marks repeat earlier text; select one to see its other appearances.'} Tap a mark or use the line selector.</p>
    <div className="line-score mt-10" aria-label="Lines in song order">{reading.lines.map((line,i)=><button key={i} title={`Line ${i+1}: ${line.words} words${line.repeats>1?`, ${line.repeats} appearances`:''}`} aria-label={`Line ${i+1}`} aria-pressed={active===i} onClick={()=>setActive(i)} style={{height:mapMode==='length'?`${Math.max(9,line.words/maxWords*100)}%`:'65%',background:active===i?'var(--ink)':mapMode==='return'&&line.first===i?'var(--rule-strong)':selected?.key===line.key||mapMode==='return'?'var(--accent)':'var(--accent-soft)',opacity:active===i||selected?.key===line.key?1:0.55}}/>)}</div>
    <div className="flex justify-between smallcaps mt-3"><span>Opening line</span><span>Final line</span></div>
    <div className="grid sm:grid-cols-[150px_1fr] gap-6 mt-8 bg-paper-soft p-6 sm:p-8 min-h-36">
     <label className="smallcaps">Read line <select className="block bg-transparent text-ink text-2xl font-serif mt-3 border-b border-rule-strong max-w-full" value={active} onChange={e=>setActive(Number(e.target.value))}>{reading.lines.map((_,i)=><option key={i} value={i}>{i+1} / {reading.lines.length}</option>)}</select></label>
     <div><blockquote translate="no" className="font-serif text-2xl sm:text-3xl italic leading-snug break-words">{selected?.text}</blockquote><p className="smallcaps mt-4">{selected?.section?`${selected.section} · `:''}{selected?.words} words · {selected?.repeats===1?'Appears once':`${selected?.repeats} appearances`}</p></div>
    </div><p className="text-xs text-ink-mute mt-5">This is the written shape, not audio timing or a measure of rapping speed.</p>
   </Reveal></section>
   <section id="song-vocabulary" className="scroll-mt-8"><Reveal className="py-14 sm:py-24 grid md:grid-cols-2 gap-10 md:gap-20 items-center">
    <div><p className="smallcaps mb-5">III. The unfolding</p><h2 className="font-serif italic text-3xl sm:text-4xl leading-snug">{reading.newInSecond===0?<>By halfway, the song has <em className="text-accent">shown its whole vocabulary.</em></>:<>Even after halfway,<br/><em className="text-accent">new words arrive.</em></>}</h2><div className="figure text-accent mt-8" style={{fontSize:'clamp(5rem,15vw,9rem)'}}><Count value={reading.newInSecond}/></div><p className="font-serif italic text-xl text-ink-soft mt-3">words introduced for the first time in the second half</p><p className="text-sm leading-relaxed text-ink-mute mt-5">Halfway means halfway through the lines, not the recording. A flat curve means familiar words; a rise means new vocabulary.</p></div>
    <figure><svg viewBox="0 0 600 170" role="img" aria-label={`Vocabulary grows to ${unique} distinct words over ${reading.lines.length} lines`} className="w-full overflow-visible"><path d="M 0 150 H 600" fill="none" stroke="var(--rule-strong)"/><path d="M 300 5 V 150" stroke="var(--rule-strong)" strokeDasharray="4 5"/><path d={curve} fill="none" stroke="var(--accent)" strokeWidth="3" pathLength="1" className="vocabulary-stroke"/></svg><figcaption className="flex justify-between smallcaps mt-4"><span>First word</span><span>Halfway</span><span>{unique} distinct</span></figcaption><div className="border-t border-rule mt-8 pt-6 flex justify-between gap-4"><span className="font-serif italic text-lg">Words used just once</span><span className="figure text-3xl">{reading.oneOff}</span></div></figure>
   </Reveal></section>
   <section id="song-words" className="scroll-mt-8 border-t border-rule-strong py-10 sm:py-14"><Reveal>
    <p className="smallcaps mb-4">IV. Words in their world</p><h2 className="display text-4xl sm:text-5xl">A word is only the beginning.</h2><p className="font-serif text-lg italic text-ink-soft mt-5">Choose a word to find the lines around it.</p>
    <div className="flex flex-wrap gap-2 mt-7">{reading.topWords.map(([w,n])=><button key={w} translate="no" className={`word-chip ${term===w?'is-active':''}`} aria-pressed={term===w} onClick={()=>setWord(w)}>{w}<small>{n}</small></button>)}</div>
    <label className="block mt-7 max-w-sm"><span className="smallcaps">Or find your own word</span><input className="field mt-2" value={word} onChange={e=>setWord(e.target.value)} placeholder="Search within the song" maxLength={80}/></label>
    <div className="mt-8 grid md:grid-cols-[180px_1fr] gap-6"><p className="smallcaps pt-2">{reading.counts.get(term)??0} appearances<br/><span className="block mt-2">{matches.length} matching lines</span></p><div className="space-y-5">{matches.slice(0,5).map((line,i)=><p key={i} translate="no" className="font-serif text-xl italic border-l-2 border-accent pl-5 leading-relaxed">{line.text}</p>)}{!matches.length&&<p className="font-serif italic text-ink-soft">No exact word match. Try another word above.</p>}{matches.length>5&&<p className="text-sm text-ink-mute">Showing five of {matches.length} matching lines.</p>}</div></div>
   </Reveal></section>
   <details className="border-y border-rule-strong mt-10 py-5"><summary className="cursor-pointer smallcaps text-ink">Read the complete text</summary><div translate="no" className="font-serif whitespace-pre-wrap break-words text-lg leading-relaxed mt-8 max-w-3xl mx-auto">{song.lyrics}</div></details>
  </>}
  {!full&&<Reveal className="py-14 sm:py-20"><p className="smallcaps mb-6">II. The vocabulary</p><div className="grid sm:grid-cols-[1fr_1.1fr] gap-8 items-center"><div className="figure text-accent" style={{fontSize:'clamp(5rem,16vw,10rem)'}}><Count value={unique}/></div><div><h2 className="font-serif italic text-3xl sm:text-4xl leading-snug">Different words.<br/>One song.</h2><p className="font-serif text-xl text-ink-soft mt-5">{total.toLocaleString()} word appearances, drawn from {unique.toLocaleString()} distinct words. About {Math.round(s.type_token_ratio*100)} different words per hundred.</p><p className="text-sm text-ink-mute mt-5">Variety describes this text. It is not a score for songwriting quality.</p></div></div></Reveal>}
  <p className="text-xs leading-relaxed text-ink-mute mt-8 max-w-3xl">{song.source==='local'?'Calculated in your browser from the text you supplied. The text is not uploaded or saved.':full?'This reading follows the available transcription. Versions and line breaks can change the results.':'This outline uses saved catalogue statistics. The full text may use a different transcription.'} Word matching ignores case. Line matching also normalises whitespace; punctuation remains significant.</p>
 </article>;
}
