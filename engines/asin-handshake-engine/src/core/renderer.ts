import type { EngineConfig, GeometryOutput, RenderOutput } from "./types";

export function renderFrame(
  ctx: CanvasRenderingContext2D,
  geometry: GeometryOutput,
  cfg: EngineConfig
): RenderOutput {
  const { points, cx, cy, R } = geometry;
  const canvas = ctx.canvas;

  ctx.clearRect(0, 0, cfg.width, cfg.height);

  ctx.lineWidth = 0.9;
  ctx.strokeStyle = "#92c5ff55";
  ctx.beginPath();

  for (let i = 0; i < points.length; i++) {
    const p = points[i];
    const spokeAngle = (i % cfg.spokes) * (2 * Math.PI / cfg.spokes);
    const sx = cx + R * Math.cos(spokeAngle);
    const sy = cy + R * Math.sin(spokeAngle);

    ctx.moveTo(p.x, p.y);
    ctx.lineTo(sx, sy);
  }

  ctx.stroke();

  ctx.fillStyle = "#cfe8ff";
  ctx.beginPath();
  ctx.arc(cx, cy, 4, 0, Math.PI * 2);
  ctx.fill();

  const meta = `asin://v1 seed=${cfg.hz.toFixed(2)} phi=${cfg.phi} spokes=${cfg.spokes} step=${cfg.step} love=${cfg.love.toFixed(2)}`;

  return { canvas, meta };
}
