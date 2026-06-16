import { useEffect, useRef, useState } from "react";

export function useIntersectionObserver(options = {}) {
  const [isIntersecting, setIsIntersecting] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      // Once it intersects, keep it visible (don't animate out when scrolling past)
      if (entry.isIntersecting) {
        setIsIntersecting(true);
      }
    }, {
      root: null,
      rootMargin: "0px",
      threshold: 0.2, // Trigger when 20% visible
      ...options
    });

    const currentRef = ref.current;
    if (currentRef) {
      observer.observe(currentRef);
    }

    return () => {
      if (currentRef) {
        observer.unobserve(currentRef);
      }
    };
  }, [options]);

  return { ref, isIntersecting };
}
