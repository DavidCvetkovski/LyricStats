"use client";

import { useEffect, useState } from "react";

/**
 * Today's date, rendered on the client. The masthead is statically
 * prerendered, so a server-side `new Date()` would freeze at build time;
 * filling it in after mount keeps the folio date current (and avoids a
 * hydration mismatch).
 */
export function DateLine() {
  const [today, setToday] = useState("");

  useEffect(() => {
    setToday(
      new Date().toLocaleDateString("en-GB", {
        weekday: "long",
        day: "numeric",
        month: "long",
        year: "numeric",
      }),
    );
  }, []);

  return <>{today}</>;
}
