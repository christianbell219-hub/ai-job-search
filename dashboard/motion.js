(function motion() {
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce) return;

  const stills = document.querySelectorAll(".reveal-still");
  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        const t = Math.min(1, Math.max(0, entry.intersectionRatio));
        const node = entry.target;
        node.style.opacity = String(0.35 + t * 0.65);
        node.style.transform = `scale(${0.92 + t * 0.08})`;
      });
    },
    { threshold: [0, 0.2, 0.4, 0.6, 0.8, 1] }
  );
  stills.forEach((el) => io.observe(el));
})();
