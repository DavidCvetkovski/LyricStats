import { describe, expect, it } from "vitest";
import { joinerVariants, nameMatches } from "./utils";

describe("joinerVariants", () => {
  it("reads a joiner between words as 'and', then as nothing", () => {
    expect(joinerVariants("Emerson, Lake & Palmer")).toEqual(["emersonlakeandpalmer"]);
    expect(joinerVariants("Peter, Paul and Mary")).toEqual(["peterpaulmary"]);
    expect(joinerVariants("Florence + the Machine")).toEqual(["florenceandthemachine"]);
    expect(joinerVariants("Mumford & So")).toEqual(["mumfordandso"]);
  });

  it("leaves names without a joiner between two words alone", () => {
    expect(joinerVariants("Drake")).toEqual([]);
    expect(joinerVariants("And One")).toEqual([]);
    expect(joinerVariants("Prozac+")).toEqual([]);
    expect(joinerVariants("Band of Horses")).toEqual([]);
    expect(joinerVariants("&")).toEqual([]);
  });
});

describe("nameMatches", () => {
  it("matches a name filed under 'and' when an ampersand was typed", () => {
    expect(nameMatches("Mumford And Sons", "Mumford & Sons")).toBe(true);
    expect(nameMatches("Mumford And Sons", "mumford so")).toBe(false);
    expect(nameMatches("Simon & Garfunkel", "simon and garf")).toBe(true);
  });
});
