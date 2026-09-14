import type { SongPayload, SongStats } from './types';

export const wordsIn = (text: string): string[] => text.normalize("NFC").toLowerCase().match(/\p{L}+(?:['’]\p{L}+)*/gu) ?? [];
const STOP = new Set(('the a an and or but i you he she it we they me my your his her our their to of in on at for from with is are was were be been am do does did have has had that this these those as if so not no yes oh ooh yeah uh hey na la da de se je su sam si za na u sa i a al ali me te mi ti od do što sta šta kako kada dok').split(' '));
export function readLyrics(text: string) {
  let section = '';
  const seen = new Set<string>();
  const counts = new Map<string, number>();
  const groups = new Map<string, number[]>();
  const lines: {text:string; key:string; section:string; words:number; added:number; vocabulary:number; repeats:number; first:number}[] = [];
  for (const raw of text.replace(/\r\n?/g,'\n').split('\n')) {
    const line = raw.trim();
    if (!line || /^(?:\d+ Contributors?.*|.*Translations?.*|You might also like.*|\d*Embed)$/i.test(line)) continue;
    const heading = line.match(/^\[([^\]]+)\]$/);
    if (heading) { section = heading[1]; continue; }
    const tokens = wordsIn(line);
    if (!tokens.length) continue;
    let added = 0;
    for (const word of tokens) { if (!seen.has(word)) {seen.add(word);added++;} counts.set(word,(counts.get(word)??0)+1); }
    const key = line.normalize("NFC").toLowerCase().replace(/\s+/g, " ");
    const indices = groups.get(key) ?? [];indices.push(lines.length);groups.set(key,indices);
    lines.push({text:line,key,section,words:tokens.length,added,vocabulary:seen.size,repeats:1,first:indices[0]});
  }
  lines.forEach(line => {line.repeats=groups.get(line.key)!.length;});
  const total=lines.reduce((n,l)=>n+l.words,0);
  const repeated=lines.length-groups.size;
  const repeatGroups=[...groups.values()].filter(g=>g.length>1).sort((a,b)=>b.length-a.length);
  const halfway=Math.ceil(lines.length/2);
  const early=lines.slice(0,halfway).reduce((n,l)=>n+l.words,0);
  const late=total-early;
  const topWords=[...counts].filter(([w])=>!STOP.has(w)&&w.length>2).sort((a,b)=>b[1]-a[1]).slice(0,12);
  const peak=lines.reduce((best,l,i)=>l.words>(lines[best]?.words??0)?i:best,0);
  return {lines,total,unique:seen.size,counts,topWords,repeatGroups,repeated,halfway,early,late,peak,
    firstReturn:lines.findIndex((l,i)=>l.first!==i),
    oneOff:[...counts.values()].filter(n=>n===1).length,
    newInSecond:lines.slice(halfway).reduce((n,l)=>n+l.added,0)};
}
export type Reading = ReturnType<typeof readLyrics>;
export function localSong(artist:string,title:string,lyrics:string):SongPayload {
  const r=readLyrics(lyrics);const histogram:Record<string,number>={};
  for(const [w,n] of r.counts) histogram[[...w].length]=(histogram[[...w].length]??0)+n;
  const stats:SongStats={word_count:r.total,unique_words:r.unique,type_token_ratio:r.total?r.unique/r.total:0,
    char_count_no_spaces:lyrics.replace(/\s/g,'').length,line_count:r.lines.length,section_count:new Set(r.lines.map(l=>l.section)).size,
    hapax_count:r.oneOff,hapax_ratio:r.unique?r.oneOff/r.unique:0,avg_word_length:r.total?[...r.counts].reduce((n,[w,c])=>n+[...w].length*c,0)/r.total:0,
    longest_words:[...r.counts.keys()].sort((a,b)=>b.length-a.length).slice(0,8),word_length_hist:histogram,
    avg_words_per_line:r.lines.length?r.total/r.lines.length:0,longest_line_words:r.lines[r.peak]?.words??0,
    shortest_line_words:r.lines.length?Math.min(...r.lines.map(l=>l.words)):0,
    top_words:[...r.counts].sort((a,b)=>b[1]-a[1]).slice(0,20),top_words_no_stop:r.topWords,
    section_kinds:{},section_sequence:[],chorus_ratio:0,repetition_ratio:r.lines.length?r.repeated/r.lines.length:0,language_mix:{},profanity_count:0};
  return {artist:artist.trim()||'Your text',title:title.trim()||'An untitled song',album:null,year:null,source:'local',analysis_complete:true,has_sections:false,lyrics,stats};
}
