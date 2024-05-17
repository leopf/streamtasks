export type Point = { x: number, y: number };

export function addPoints(a: Point, b: Point): Point {
    return { x: a.x + b.x, y: a.y + b.y };
}
export function subPoints(a: Point, b: Point): Point {
    return { x: a.x - b.x, y: a.y - b.y };
}
export function mulPoints(a: Point, b: Point): Point {
    return { x: a.x * b.x, y: a.y * b.y };
}
export function divPoints(a: Point, b: Point): Point {
    return { x: a.x / b.x, y: a.y / b.y };
}
export function scalarToPoint(a: number): Point {
    return { x: a, y: a };
}
export function pointDistance(a: Point, b: Point) {
    return Math.sqrt(Math.pow(a.x - b.x, 2) + Math.pow(a.y - b.y, 2))
}