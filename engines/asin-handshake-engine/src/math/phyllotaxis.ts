import type { EngineConfig, GeometryOutput, Point } from "../core/types";

export function generateGeometry(cfg: EngineConfig): GeometryOutput {
  const points: Point[] = [];
  const R = cfg.width * 0.42;
  const cx = cfg.width / 2;
  const cy = cfg.height / 2;
  const lambda = cfg.love * 0.8;

  for (let i = 0; i < cfg.points; i++) {
    const theta = ((i * cfg.phi) + lambda) * Math.PI / 180;
    const r = Math.sqrt(i / cfg.points) * R;

    points.push({
      x: cx + r * Math.cos(theta),
      y: cy + r * Math.sin(theta),
      angle: theta,
      radius: r
    });
  }

  return { points, cx, cy, R };
}
