"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { artistKey } from "@/lib/utils";
import { Highlight } from "./Highlight";

const SHOW = 8;

type Props = {
  value: string;
  onChange: (value: string) => void;
  /** Chosen from the menu (click, or Enter on a highlighted row). */
  onPick?: (title: string) => void;
  /** The artist's catalogue, once known; the menu filters it locally. */
  titles: string[];
  placeholder?: string;
  onFocus?: () => void;
};

/**
 * Song-title field with the artist's catalogue as a dropdown. Everything
 * happens in the browser: the titles arrive once (when the artist is known)
 * and each keystroke narrows them, titles that start with the typed text
 * first. Picking one fires `onPick`, which the search page uses to open the
 * song straight away.
 */
export function TitleAutocomplete({ value, onChange, onPick, titles, placeholder, onFocus }: Props) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const typing = useRef(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const listId = useId();

  const items = useMemo(() => {
    const key = artistKey(value);
    if (!titles.length) return [];
    if (!key) return titles.slice(0, SHOW);
    const starts: string[] = [];
    const contains: string[] = [];
    for (const t of titles) {
      const k = artistKey(t);
      if (k === key) starts.unshift(t);
      else if (k.startsWith(key)) starts.push(t);
      else if (k.includes(key)) contains.push(t);
    }
    // Among titles that start with the typed text, the shortest is the
    // likeliest ("Thriller" before "Threatened" and the 25th-anniversary take).
    const exact = starts.length && artistKey(starts[0]) === key ? starts.shift()! : null;
    starts.sort((a, b) => a.length - b.length || a.localeCompare(b));
    contains.sort((a, b) => a.length - b.length || a.localeCompare(b));
    return [...(exact ? [exact] : []), ...starts, ...contains].slice(0, SHOW);
  }, [titles, value]);

  useEffect(() => {
    if (!typing.current) return;
    setOpen(items.length > 0 && artistKey(value) !== (items.length === 1 ? artistKey(items[0]) : ""));
    setActive(items.length ? 0 : -1);
  }, [items, value]);

  useEffect(() => {
    function onDocPointer(e: PointerEvent) {
      if (!rootRef.current?.contains(e.target as Node)) {
        setOpen(false);
        typing.current = false;
      }
    }
    document.addEventListener("pointerdown", onDocPointer);
    return () => document.removeEventListener("pointerdown", onDocPointer);
  }, []);

  function pick(title: string) {
    typing.current = false;
    onChange(title);
    setOpen(false);
    setActive(-1);
    onPick?.(title);
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
        if (active >= 0 && active < items.length) {
          e.preventDefault();
          pick(items[active]);
        }
        break;
      case "Escape":
        e.preventDefault();
        setOpen(false);
        typing.current = false;
        break;
    }
  }

  return (
    <div ref={rootRef} className="relative">
      <input
        className="field"
        type="text"
        placeholder={placeholder}
        value={value}
        maxLength={300}
        autoComplete="off"
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={open && active >= 0 ? `${listId}-${active}` : undefined}
        onFocus={() => {
          onFocus?.();
          // A focused, empty field offers the catalogue's first titles.
          if (!value.trim() && titles.length) {
            typing.current = true;
            setOpen(true);
            setActive(0);
          }
        }}
        onChange={(e) => {
          typing.current = true;
          onChange(e.target.value);
        }}
        onKeyDown={onKeyDown}
      />
      {open && items.length > 0 && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-30 left-0 right-0 mt-1 max-h-72 overflow-auto border border-rule-strong bg-paper shadow-[0_8px_24px_rgba(26,22,20,0.12)]"
        >
          {items.map((t, i) => (
            <li
              key={`${t}#${i}`}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              onPointerDown={(e) => {
                e.preventDefault();
                pick(t);
              }}
              onMouseEnter={() => setActive(i)}
              className={`flex items-baseline justify-between gap-4 px-3 py-2 cursor-pointer border-b border-rule last:border-b-0 ${
                i === active ? "bg-paper-soft" : ""
              }`}
            >
              <span translate="no" className={`font-serif text-lg leading-tight truncate ${i === active ? "text-accent" : "text-ink"}`}>
                <Highlight text={t} query={value} />
              </span>
              {i === active && (
                <span className="smallcaps text-[0.6rem] whitespace-nowrap shrink-0">read it ↵</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
