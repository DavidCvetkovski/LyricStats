import { describe, expect, it } from "vitest";
import { isFiller, isGrammar, vocabulary } from "./filler";

describe("filler", () => {
  it("sets aside sung vocables, interjections and words without a vowel", () => {
    for (const w of ["hoo", "hee", "woo", "whoo", "doo", "wow", "ugh", "skrrt"]) expect(isFiller(w)).toBe(true);
    for (const w of ["hoodoo", "home", "moon", "river"]) expect(isFiller(w)).toBe(false);
  });

  it("sets aside grammar spelled without its apostrophe, section labels and credits", () => {
    for (const w of ["dont", "nothin", "though", "within", "chorus", "repeat", "copyright"]) {
      expect(isGrammar(w)).toBe(true);
    }
    expect(isGrammar("cos")).toBe(false); // a word in Romanian and Italian
  });

  it("keeps vocabulary in a word table", () => {
    const rows: [string, number][] = [["hoo", 9], ["river", 4], ["chorus", 3], ["girl", 2]];
    expect(vocabulary(rows).map(([w]) => w)).toEqual(["river", "girl"]);
  });
});
