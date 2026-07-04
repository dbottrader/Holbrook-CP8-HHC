# Mathematical Model

## Angular Position

For point index `i`:

```text
theta_i = (i * phi + lambda) * pi / 180
lambda = love * 0.8
```

## Radial Function

```text
r_i = R * sqrt(i / points)
R = width * 0.42
```

## Cartesian Mapping

```text
x_i = cx + r_i * cos(theta_i)
y_i = cy + r_i * sin(theta_i)
```

## Radial Spoke Projection

```text
alpha_i = (i mod spokes) * (2*pi / spokes)
x_s = cx + R * cos(alpha_i)
y_s = cy + R * sin(alpha_i)
```

The renderer draws a line segment from `(x_i, y_i)` to `(x_s, y_s)` for each point.

## Complexity

Let `n = points`.

- Time complexity: `O(n)`
- Space complexity: `O(n)` for generated point storage, excluding the render buffer
