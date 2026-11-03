// The faint falling-characters backdrop. Low frame rate and low opacity so it never gets in the way.

const GLYPHS = "01アイウエオカキクケコサシスセソタチツテトナニヌネノ0123456789ABCDEF<>/{}[]$#";

export function startRain(canvas) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const ctx = canvas.getContext("2d");
  const size = 16;
  let cols = [];

  function resize() {
    canvas.width = innerWidth;
    canvas.height = innerHeight;
    const n = Math.ceil(canvas.width / size);
    cols = Array.from({ length: n }, (_, i) => cols[i] ?? Math.random() * -60);
  }
  resize();
  addEventListener("resize", resize);

  setInterval(() => {
    if (document.hidden) return;
    ctx.fillStyle = "rgba(0, 0, 0, 0.12)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.font = `${size - 2}px Consolas, monospace`;
    for (let i = 0; i < cols.length; i++) {
      const y = cols[i] * size;
      if (y > 0) {
        ctx.fillStyle = Math.random() < 0.04 ? "#d6ffe0" : "#00ff41";
        ctx.fillText(GLYPHS[(Math.random() * GLYPHS.length) | 0], i * size, y);
      }
      cols[i] = y > canvas.height && Math.random() > 0.975 ? 0 : cols[i] + 1;
    }
  }, 70);
}
