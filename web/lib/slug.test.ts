import { describe, expect, it } from "vitest";
import { slugify, songPath } from "./slug";

describe("slugify", () => {
  it("folds accents, case and punctuation the way the API does", () => {
    expect(slugify("Beyoncé")).toBe("beyonce");
    expect(slugify("HUMBLE.")).toBe("humble");
    expect(slugify("Jala Brat")).toBe("jala-brat");
    expect(slugify("Wanna Be Startin' Somethin'")).toBe("wanna-be-startin-somethin");
    expect(slugify("  Mačje oči  ")).toBe("macje-oci");
    expect(slugify("Jay-Z")).toBe("jay-z");
    expect(slugify("$$$")).toBe("");
  });

  it("builds the song path", () => {
    expect(songPath("Michael Jackson", "Thriller")).toBe("/song/michael-jackson/thriller");
  });
});
