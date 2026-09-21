/**
 * Grammar and ad-libs, in the languages the archive mostly sings in. The word
 * tables set these aside so what is left is vocabulary. The same lists drive
 * scripts/build_signatures.py; keep the two in step.
 */
// English words that are grammar: never vocabulary, in any table.
const EN_GRAMMAR =
  "the a an and or but if of to in on at by for with as is are was were be been being am i me my mine " +
  "you your yours he him his she her hers it its we us our ours they them their theirs this that " +
  "these those there here where when why how what which who whom whose will would can could shall " +
  "should may might must do does did done have has had having not no nor none don't doesn't didn't " +
  "won't can't couldn't wouldn't shouldn't isn't aren't wasn't weren't ain't i'm i've i'll i'd " +
  "you're you've you'll you'd he's she's it's we're we've we'll they're they've they'll that's " +
  "there's here's what's who's let's than then so too very just only also yeah yes oh ah uh well " +
  "okay ok hey gonna wanna gotta gimme lemme cause 'cause";
// English words that carry little on their own: set aside when choosing one word to stand for a catalogue.
const EN_GENERIC =
  "go goes going gone went come comes came coming get gets got getting gotten let make made making " +
  "take took taken keep kept give gave given put say said says saying tell told know knew known " +
  "think thought feel felt want wanted need needed see saw seen look looked even still yet again " +
  "away back down up out off over under into from about around through after before because while " +
  "till until once ever never always all any some every each much many more most little few like " +
  "way thing things something nothing everything anything someone everyone anyone one ones time " +
  "times own same other another really right";

const LISTS = [
  EN_GRAMMAR,
  EN_GENERIC,
  // Bosnian / Croatian / Serbian
  "i je da se ne ti mi na sam za što sve kad ja to si ali kao od samo sa u o me te još ću će nema " +
    "znam nije imam ona ovo sad bez ko jer ili dok sto nek nikad moj moja moje moju tvoj tvoja tvoje " +
    "tvoju svoj svoja svoje nas vas nam vam ih im njen njena njegov naš vaš ovaj ova ono onaj taj " +
    "ta tu tamo ovdje ovde gdje gde kako zašto zato ako pa ni niti čak već tek baš opet uvijek uvek " +
    "nikada niko neko nešto ništa svi bio bila bilo bili biti budem bude smo ste su sada onda prije " +
    "pre poslije posle mogu možeš može hoću hoćeš hoće neću nećeš neće nisam nisi nismo niste nisu " +
    "imaš ima imamo imate imaju znaš zna znamo znate znaju šta sta kada zar li bi bih bismo biste " +
    "neka eto evo ajde hajde daj ma ej hej joj jao jel jeli čega čemu kome koga koji koja koje kojoj " +
    "kojem mene tebe",
  // Spanish
  "que de la el y no en un mi te tu es me se por lo con para una los más si yo como pero del al las " +
    "todo mas nada ya sin eres soy está estoy",
  // Portuguese
  "que de não eu você um uma o a em do da é com para se me meu minha mais tudo vou tá pra sem ele " +
    "ela nao voce ta te já só isso",
  // French
  "je tu le la les et pas que de un une des dans ne me te pour qui mais mon ma sur est on moi toi " +
    "avec tout j'ai c'est t'as plus vous nous il elle ils elles se ce cette ces son sa ses leur au " +
    "aux du en y ou où si comme bien été être avoir",
  // German
  "ich du und die nicht das ist der wir es ein in zu sie mit auf mir dich was wie so dir mich den " +
    "sind aber für nur wenn mein kann noch doch schon mal denn dann weil oder auch immer nie hier " +
    "dort wo wer warum sich uns euch ihr ihn ihm ihnen sein seine meine dein deine kein keine alle " +
    "alles nichts etwas jeder jede hat haben war waren wird werden muss will soll bin bist seid eine " +
    "einen einem einer dem des vom zum zur ins ans bei nach vor über unter durch ohne gegen",
  // Italian
  "che non di la il mi un per ti è se e come ma sei con una io tu ho più sono del quando ci le mai " +
    "così sto già",
];

const FILLER = new Set(LISTS.join(" ").split(/\s+/).filter(Boolean));
const GENERIC = new Set(EN_GENERIC.split(/\s+/));

const AD_LIB = /^(?:[aeiouy]+h*|(?:la|na|da|dah|ooh|ohh|aah|ah|oh|uh|eh|ey|ay|yeah|yah|yo|mm|hmm|ba|bum|whoa|woah|wah|ha|hey|oi|ra|ta|ti|di|du|lo|le|li|nah|yea|ye|wo|wa|ho|oo|ai|ya|yu|yi|hi|hu|hah|heh|huh|hum|shh|ssh|tsk|brr|grr)+h?)$/;

/** True for a word that carries no meaning on its own: grammar or an ad-lib. */
export function isFiller(word: string): boolean {
  const w = word.toLowerCase().replace(/’/g, "'");
  if (w.length < 3) return true;
  if (FILLER.has(w)) return true;
  if (AD_LIB.test(w)) return true;
  if (w.length >= 4 && new Set(w).size <= 2) return true;
  return false;
}

/** True for grammar and ad-libs only; generic verbs and adverbs stay. */
export function isGrammar(word: string): boolean {
  return isFiller(word) && !GENERIC.has(word.toLowerCase().replace(/’/g, "'"));
}

/** The rows of a word table with the grammar set aside. */
export function vocabulary<T extends [string, ...unknown[]]>(rows: T[] | null | undefined): T[] {
  return (rows ?? []).filter(([w]) => !isGrammar(w));
}
