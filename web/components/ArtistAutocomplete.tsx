"use client";

import { useEffect, useId, useRef, useState } from "react";
import { suggestArtists, type ArtistSuggestion } from "@/lib/api";
import { artistKey } from "@/lib/utils";

type Props = {
  value: string;
  onChange: (value: string) => void;
  /** Called when a suggestion is chosen (click / Enter on a highlighted row). */
  onPick?: (name: string) => void;
  placeholder?: string;
  className?: string;
  autoFocus?: boolean;
};

// Sit on the latest keystroke this long before asking the API, so a fast
// typist fires one request instead of one per letter.
const DEBOUNCE_MS = 180;
// Fetch a generous candidate set but only show the top few. The extra rows let
// us narrow locally as the reader types more (no extra round-trips).
const FETCH_LIMIT = 20;
const SHOW = 8;

// One cache for the whole session, shared across both search boxes. Keyed by
// the aggressive match key; holds the *full* fetched list plus whether it was
// the complete set (fewer than FETCH_LIMIT rows) — only complete sets are safe
// to narrow from, since a capped list might hide a deeper match.
type Entry = { items: ArtistSuggestion[]; complete: boolean };
const cache = new Map<string, Entry>();

/**
 * Resolve a query from cache alone, or null if a network fetch is needed.
 * Exact hit wins; otherwise narrow from the longest complete prefix we've
 * already fetched. Because "names containing `key`" ⊆ "names containing
 * `prefix`", filtering a complete prefix set yields the exact, complete answer.
 */
function resolveFromCache(key: string): Entry | null {
  const exact = cache.get(key);
  if (exact) return exact;
  for (let i = key.length - 1; i >= 2; i--) {
    const anchor = cache.get(key.slice(0, i));
    if (anchor?.complete) {
      const items = anchor.items.filter((it) =>
        artistKey(it.name).includes(key),
      );
      const entry: Entry = { items, complete: true };
      cache.set(key, entry);
      return entry;
    }
  }
  return null;
}

/**
 * Artist search field with a dataset-backed dropdown. Wraps a plain `.field`
 * input; as the reader types we fetch matching artists and list them below,
 * each with its catalogue size. Selecting one fills the field and fires
 * `onPick` (the artist page uses that to run the search immediately).
 */
export function ArtistAutocomplete({
  value,
  onChange,
  onPick,
  placeholder,
  className = "field",
  autoFocus,
}: Props) {
  const [items, setItems] = useState<ArtistSuggestion[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);

  const rootRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  // Track whether the last input change came from user typing/editing, so we
  // don't show the suggestions list on initial mount or parameter restoration.
  const isUserTyping = useRef(false);
  // The text in the field at the moment a suggestion was picked. While the
  // typed value still equals this, we keep the menu shut so it doesn't reopen
  // onto the very name we just chose.
  const justPicked = useRef<string | null>(null);
  const listId = useId();

  useEffect(() => {
    const q = value.trim();
    if (justPicked.current !== null && q === justPicked.current) return;
    justPicked.current = null;

    const key = artistKey(q);
    if (key.length < 2) {
      abortRef.current?.abort();
      setItems([]);
      setActive(-1);
      setOpen(false);
      return;
    }

    const show = (full: ArtistSuggestion[]) => {
      setItems(full.slice(0, SHOW));
      setActive(full.length > 0 ? 0 : -1);
      if (isUserTyping.current) {
        setOpen(full.length > 0);
      }
    };

    // 1. Served entirely from cache (exact or narrowed) → instant, no network.
    const cached = resolveFromCache(key);
    if (cached) {
      abortRef.current?.abort();
      show(cached.items);
      return;
    }

    // 2. Debounced fetch. We deliberately keep the current rows on screen while
    //    it's in flight, so the list never blanks mid-type.
    const t = setTimeout(async () => {
      abortRef.current?.abort();
      const ac = new AbortController();
      abortRef.current = ac;
      try {
        const found = await suggestArtists(q, FETCH_LIMIT, ac.signal);
        if (ac.signal.aborted) return;
        cache.set(key, { items: found, complete: found.length < FETCH_LIMIT });
        show(found);
      } catch {
        // Network/abort error: leave whatever's showing in place rather than
        // blanking the menu, so a hiccup doesn't make it "stop working".
      }
    }, DEBOUNCE_MS);

    return () => clearTimeout(t);
  }, [value]);

  // Close when focus or a click lands outside the widget.
  useEffect(() => {
    function onDocPointer(e: PointerEvent) {
      if (!rootRef.current?.contains(e.target as Node)) {
        setOpen(false);
        isUserTyping.current = false;
      }
    }
    document.addEventListener("pointerdown", onDocPointer);
    return () => document.removeEventListener("pointerdown", onDocPointer);
  }, []);

  function pick(name: string) {
    justPicked.current = name;
    isUserTyping.current = false;
    onChange(name);
    setItems([]);
    setOpen(false);
    setActive(-1);
    onPick?.(name);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!open || items.length === 0) return;
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setActive((i) => (i + 1) % items.length);
        break;
      case "ArrowUp":
        e.preventDefault();
        setActive((i) => (i <= 0 ? items.length - 1 : i - 1));
        break;
      case "Enter":
        // Only intercept the submit when a row is highlighted; otherwise let
        // the form submit the typed name as before.
        if (active >= 0 && active < items.length) {
          e.preventDefault();
          pick(items[active].name);
        }
        break;
      case "Escape":
        e.preventDefault();
        setOpen(false);
        isUserTyping.current = false;
        break;
    }
  }

  return (
    <div ref={rootRef} className="relative">
      <input
        className={className}
        type="text"
        placeholder={placeholder}
        value={value}
        onChange={(e) => {
          isUserTyping.current = true;
          onChange(e.target.value);
        }}
        onKeyDown={onKeyDown}
        autoFocus={autoFocus}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}
        autoComplete="off"
      />

      {open && items.length > 0 && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-30 left-0 right-0 mt-1 max-h-72 overflow-auto border border-rule-strong bg-paper shadow-[0_8px_24px_rgba(26,22,20,0.12)]"
        >
          {items.map((it, i) => (
            <li
              key={`${it.name}-${i}`}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              // pointerdown (not click) so the pick lands before the input's
              // blur can close the menu out from under it.
              onPointerDown={(e) => {
                e.preventDefault();
                pick(it.name);
              }}
              onMouseEnter={() => setActive(i)}
              className={`flex items-baseline justify-between gap-4 px-3 py-2 cursor-pointer border-b border-rule last:border-b-0 ${
                i === active ? "bg-paper-soft" : ""
              }`}
            >
              <span
                className={`font-serif text-lg leading-tight truncate ${
                  i === active ? "text-accent" : "text-ink"
                }`}
              >
                {it.name}
              </span>
              <span className="figure text-[0.7rem] tabular-nums text-ink-mute whitespace-nowrap shrink-0">
                {it.song_count.toLocaleString()}{" "}
                {it.song_count === 1 ? "song" : "songs"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
