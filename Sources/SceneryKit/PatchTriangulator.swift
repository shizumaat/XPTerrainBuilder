import Foundation

// Ear clipping with holes for the 3D preview's patch shapes
// (Ortho4XP/docs/specs/patch-editor-20261015.md §4, §5): one shape = one
// outer ring and its holes, triangulated in the document's metric plane,
// triangles returned as NODE IDS so a moved node updates its vertex in
// place without re-triangulating. The algorithm is the earcut method
// (holes bridged to the outer ring right-to-left, ears clipped with a
// z-order hash on large rings, then local-intersection cure and a split
// pass for degenerate input).

/// One triangle of a patch shape, counter-clockwise seen from above
/// (east = +x, north = +y).
public struct PatchTriangle: Equatable, Hashable, Sendable {
    public let a: Int64
    public let b: Int64
    public let c: Int64

    public init(_ a: Int64, _ b: Int64, _ c: Int64) {
        self.a = a; self.b = b; self.c = c
    }
}

public enum PatchTriangulator {
    /// Triangulate `outer` minus `holes`. Rings are node ids, closed or
    /// open (a repeated closing id is dropped); `position` gives a node's
    /// planar (x, y) metres — a node it does not know is skipped.
    public static func triangulate(outer: [Int64], holes: [[Int64]] = [],
                                   position: (Int64) -> (x: Double, y: Double)?) -> [PatchTriangle] {
        var ids: [Int64] = []
        var xy: [Double] = []
        var holeStarts: [Int] = []
        func append(_ ring: [Int64]) -> Bool {
            var r = ring
            if r.count > 1, r.first == r.last { r.removeLast() }
            let start = ids.count
            for id in r {
                guard let p = position(id) else { continue }
                ids.append(id); xy.append(p.x); xy.append(p.y)
            }
            if ids.count - start < 3 {          // a ring of < 3 points bounds nothing
                ids.removeSubrange(start...); xy.removeSubrange((start * 2)...)
                return false
            }
            return true
        }
        guard append(outer) else { return [] }
        for hole in holes {
            let start = ids.count
            if append(hole) { holeStarts.append(start) }
        }
        let indices = triangulate(coordinates: xy, holeStarts: holeStarts)
        var out: [PatchTriangle] = []
        out.reserveCapacity(indices.count / 3)
        for t in stride(from: 0, to: indices.count, by: 3) {
            let i = indices[t], j = indices[t + 1], k = indices[t + 2]
            out.append(PatchTriangle(ids[i], ids[j], ids[k]))
        }
        return out
    }

    /// The flat form: `coordinates` = x0, y0, x1, y1, …; the outer ring
    /// first, each hole starting at the POINT index in `holeStarts`.
    /// Returns point-index triples, counter-clockwise (y up).
    public static func triangulate(coordinates: [Double], holeStarts: [Int] = []) -> [Int] {
        var e = Earcut(coordinates)
        let tris = e.run(holeStarts: holeStarts)
        var out: [Int] = []
        out.reserveCapacity(tris.count)
        for t in stride(from: 0, to: tris.count, by: 3) {
            let a = tris[t], b = tris[t + 1], c = tris[t + 2]
            let ax = coordinates[2 * a], ay = coordinates[2 * a + 1]
            let cross = (coordinates[2 * b] - ax) * (coordinates[2 * c + 1] - ay)
                - (coordinates[2 * b + 1] - ay) * (coordinates[2 * c] - ax)
            if cross >= 0 { out += [a, b, c] } else { out += [a, c, b] }
        }
        return out
    }

    /// Signed area (positive counter-clockwise) of a flat ring.
    public static func signedArea(_ xy: [Double]) -> Double {
        let n = xy.count / 2
        guard n > 2 else { return 0 }
        var sum = 0.0
        var j = n - 1
        for i in 0..<n {
            sum += (xy[2 * j] - xy[2 * i]) * (xy[2 * i + 1] + xy[2 * j + 1])
            j = i
        }
        return -sum / 2
    }
}

// MARK: - earcut, on an index-linked node pool (no reference cycles)

private struct Earcut {
    private let data: [Double]
    // Node pool: parallel arrays; -1 is "none".
    private var vi: [Int] = []          // point index into `data` / 2
    private var nx: [Double] = []
    private var ny: [Double] = []
    private var prev: [Int] = []
    private var next: [Int] = []
    private var z: [Int32] = []
    private var prevZ: [Int] = []
    private var nextZ: [Int] = []
    private var steiner: [Bool] = []
    private var triangles: [Int] = []
    private var minX = 0.0, minY = 0.0, invSize = 0.0

    init(_ data: [Double]) { self.data = data }

    mutating func run(holeStarts: [Int]) -> [Int] {
        let outerEnd = holeStarts.first ?? data.count / 2
        guard var outer = linkedList(0, outerEnd, clockwise: true), next[outer] != prev[outer] else {
            return []
        }
        if !holeStarts.isEmpty { outer = eliminateHoles(holeStarts, outer) }
        if data.count > 80 * 2 {
            var x0 = data[0], y0 = data[1], x1 = x0, y1 = y0
            for i in stride(from: 2, to: outerEnd * 2, by: 2) {
                x0 = min(x0, data[i]); x1 = max(x1, data[i])
                y0 = min(y0, data[i + 1]); y1 = max(y1, data[i + 1])
            }
            minX = x0; minY = y0
            let size = max(x1 - x0, y1 - y0)
            invSize = size != 0 ? 32767 / size : 0
        }
        earcutLinked(outer, pass: 0)
        return triangles
    }

    // MARK: Pool

    private mutating func insertNode(_ i: Int, _ last: Int) -> Int {
        let p = vi.count
        vi.append(i); nx.append(data[2 * i]); ny.append(data[2 * i + 1])
        z.append(0); prevZ.append(-1); nextZ.append(-1); steiner.append(false)
        if last < 0 {
            prev.append(p); next.append(p)
        } else {
            prev.append(last); next.append(next[last])
            prev[next[last]] = p
            next[last] = p
        }
        return p
    }

    private mutating func removeNode(_ p: Int) {
        next[prev[p]] = next[p]
        prev[next[p]] = prev[p]
        if prevZ[p] >= 0 { nextZ[prevZ[p]] = nextZ[p] }
        if nextZ[p] >= 0 { prevZ[nextZ[p]] = prevZ[p] }
    }

    private func area(_ p: Int, _ q: Int, _ r: Int) -> Double {
        (ny[q] - ny[p]) * (nx[r] - nx[q]) - (nx[q] - nx[p]) * (ny[r] - ny[q])
    }

    private func equals(_ a: Int, _ b: Int) -> Bool { nx[a] == nx[b] && ny[a] == ny[b] }

    // MARK: Rings

    private mutating func linkedList(_ start: Int, _ end: Int, clockwise: Bool) -> Int? {
        var sum = 0.0
        var j = end - 1
        for i in start..<end {
            sum += (data[2 * j] - data[2 * i]) * (data[2 * i + 1] + data[2 * j + 1])
            j = i
        }
        var last = -1
        if clockwise == (sum > 0) {
            for i in start..<end { last = insertNode(i, last) }
        } else {
            for i in stride(from: end - 1, through: start, by: -1) { last = insertNode(i, last) }
        }
        guard last >= 0 else { return nil }
        if equals(last, next[last]) {
            removeNode(last)
            last = next[last]
        }
        return last
    }

    @discardableResult
    private mutating func filterPoints(_ start: Int, _ endIn: Int? = nil) -> Int {
        var end = endIn ?? start
        var p = start
        var again: Bool
        repeat {
            again = false
            if !steiner[p] && (equals(p, next[p]) || area(prev[p], p, next[p]) == 0) {
                removeNode(p)
                p = prev[p]; end = p
                if p == next[p] { break }
                again = true
            } else {
                p = next[p]
            }
        } while again || p != end
        return end
    }

    // MARK: Ear clipping

    private mutating func earcutLinked(_ start: Int, pass: Int) {
        var ear = start
        if pass == 0 && invSize != 0 { indexCurve(ear) }
        var stop = ear
        clipping: while prev[ear] != next[ear] {
            let p = prev[ear], n = next[ear]
            if invSize != 0 ? isEarHashed(ear) : isEar(ear) {
                triangles += [vi[p], vi[ear], vi[n]]
                removeNode(ear)
                ear = next[n]
                stop = next[n]
                continue
            }
            ear = n
            if ear == stop {
                switch pass {
                case 0: earcutLinked(filterPoints(ear), pass: 1)
                case 1: earcutLinked(cureLocalIntersections(filterPoints(ear)), pass: 2)
                default: splitEarcut(ear)
                }
                break clipping
            }
        }
    }

    private func pointInTriangle(_ ax: Double, _ ay: Double, _ bx: Double, _ by: Double,
                                 _ cx: Double, _ cy: Double, _ px: Double, _ py: Double) -> Bool {
        (cx - px) * (ay - py) >= (ax - px) * (cy - py)
            && (ax - px) * (by - py) >= (bx - px) * (ay - py)
            && (bx - px) * (cy - py) >= (cx - px) * (by - py)
    }

    private func blocks(_ q: Int, _ a: Int, _ b: Int, _ c: Int,
                        _ x0: Double, _ y0: Double, _ x1: Double, _ y1: Double) -> Bool {
        nx[q] >= x0 && nx[q] <= x1 && ny[q] >= y0 && ny[q] <= y1 && q != a && q != c
            && pointInTriangle(nx[a], ny[a], nx[b], ny[b], nx[c], ny[c], nx[q], ny[q])
            && area(prev[q], q, next[q]) >= 0
    }

    private func isEar(_ ear: Int) -> Bool {
        let a = prev[ear], b = ear, c = next[ear]
        if area(a, b, c) >= 0 { return false }
        let x0 = min(nx[a], nx[b], nx[c]), x1 = max(nx[a], nx[b], nx[c])
        let y0 = min(ny[a], ny[b], ny[c]), y1 = max(ny[a], ny[b], ny[c])
        var p = next[c]
        while p != a {
            if blocks(p, a, b, c, x0, y0, x1, y1) { return false }
            p = next[p]
        }
        return true
    }

    private func isEarHashed(_ ear: Int) -> Bool {
        let a = prev[ear], b = ear, c = next[ear]
        if area(a, b, c) >= 0 { return false }
        let x0 = min(nx[a], nx[b], nx[c]), x1 = max(nx[a], nx[b], nx[c])
        let y0 = min(ny[a], ny[b], ny[c]), y1 = max(ny[a], ny[b], ny[c])
        let minZ = zOrder(x0, y0), maxZ = zOrder(x1, y1)
        var p = prevZ[ear], n = nextZ[ear]
        while p >= 0 && z[p] >= minZ && n >= 0 && z[n] <= maxZ {
            if blocks(p, a, b, c, x0, y0, x1, y1) { return false }
            p = prevZ[p]
            if blocks(n, a, b, c, x0, y0, x1, y1) { return false }
            n = nextZ[n]
        }
        while p >= 0 && z[p] >= minZ {
            if blocks(p, a, b, c, x0, y0, x1, y1) { return false }
            p = prevZ[p]
        }
        while n >= 0 && z[n] <= maxZ {
            if blocks(n, a, b, c, x0, y0, x1, y1) { return false }
            n = nextZ[n]
        }
        return true
    }

    private mutating func cureLocalIntersections(_ startIn: Int) -> Int {
        var start = startIn
        var p = start
        repeat {
            let a = prev[p], b = next[next[p]]
            if !equals(a, b) && intersects(a, p, next[p], b) && locallyInside(a, b) && locallyInside(b, a) {
                triangles += [vi[a], vi[p], vi[b]]
                let pn = next[p]
                removeNode(p); removeNode(pn)
                p = b; start = b
            }
            p = next[p]
        } while p != start
        return filterPoints(p)
    }

    private mutating func splitEarcut(_ start: Int) {
        var a = start
        repeat {
            var b = next[next[a]]
            while b != prev[a] {
                if vi[a] != vi[b] && isValidDiagonal(a, b) {
                    var c = splitPolygon(a, b)
                    a = filterPoints(a, next[a])
                    c = filterPoints(c, next[c])
                    earcutLinked(a, pass: 0)
                    earcutLinked(c, pass: 0)
                    return
                }
                b = next[b]
            }
            a = next[a]
        } while a != start
    }

    // MARK: Holes

    private mutating func eliminateHoles(_ holeStarts: [Int], _ outerIn: Int) -> Int {
        var queue: [Int] = []
        for (k, start) in holeStarts.enumerated() {
            let end = k + 1 < holeStarts.count ? holeStarts[k + 1] : data.count / 2
            guard let list = linkedList(start, end, clockwise: false) else { continue }
            if list == next[list] { steiner[list] = true }
            queue.append(leftmost(list))
        }
        queue.sort { nx[$0] != nx[$1] ? nx[$0] < nx[$1] : ny[$0] < ny[$1] }
        var outer = outerIn
        for hole in queue { outer = eliminateHole(hole, outer) }
        return outer
    }

    private mutating func eliminateHole(_ hole: Int, _ outer: Int) -> Int {
        guard let bridge = findHoleBridge(hole, outer) else { return outer }
        let bridgeReverse = splitPolygon(bridge, hole)
        filterPoints(bridgeReverse, next[bridgeReverse])
        return filterPoints(bridge, next[bridge])
    }

    private func findHoleBridge(_ hole: Int, _ outer: Int) -> Int? {
        var p = outer
        let hx = nx[hole], hy = ny[hole]
        var qx = -Double.infinity
        var m = -1
        repeat {
            let q = next[p]
            if hy <= ny[p] && hy >= ny[q] && ny[q] != ny[p] {
                let x = nx[p] + (hy - ny[p]) * (nx[q] - nx[p]) / (ny[q] - ny[p])
                if x <= hx && x > qx {
                    qx = x
                    m = nx[p] < nx[q] ? p : q
                    if x == hx { return m }
                }
            }
            p = q
        } while p != outer
        guard m >= 0 else { return nil }
        let stop = m, mx = nx[m], my = ny[m]
        var tanMin = Double.infinity
        p = m
        repeat {
            if hx >= nx[p] && nx[p] >= mx && hx != nx[p]
                && pointInTriangle(hy < my ? hx : qx, hy, mx, my, hy < my ? qx : hx, hy, nx[p], ny[p]) {
                let tan = abs(hy - ny[p]) / (hx - nx[p])
                if locallyInside(p, hole)
                    && (tan < tanMin || (tan == tanMin
                        && (nx[p] > nx[m] || (nx[p] == nx[m] && sectorContainsSector(m, p))))) {
                    m = p
                    tanMin = tan
                }
            }
            p = next[p]
        } while p != stop
        return m
    }

    private func sectorContainsSector(_ m: Int, _ p: Int) -> Bool {
        area(prev[m], m, prev[p]) < 0 && area(next[p], m, next[m]) < 0
    }

    private func leftmost(_ start: Int) -> Int {
        var p = start, best = start
        repeat {
            if nx[p] < nx[best] || (nx[p] == nx[best] && ny[p] < ny[best]) { best = p }
            p = next[p]
        } while p != start
        return best
    }

    // MARK: Diagonals

    private func isValidDiagonal(_ a: Int, _ b: Int) -> Bool {
        guard vi[next[a]] != vi[b], vi[prev[a]] != vi[b], !intersectsPolygon(a, b) else { return false }
        if locallyInside(a, b) && locallyInside(b, a) && middleInside(a, b)
            && (area(prev[a], a, prev[b]) != 0 || area(a, prev[b], b) != 0) {
            return true
        }
        return equals(a, b) && area(prev[a], a, next[a]) > 0 && area(prev[b], b, next[b]) > 0
    }

    private func intersects(_ p1: Int, _ q1: Int, _ p2: Int, _ q2: Int) -> Bool {
        func sign(_ v: Double) -> Int { v > 0 ? 1 : (v < 0 ? -1 : 0) }
        func onSegment(_ p: Int, _ q: Int, _ r: Int) -> Bool {
            nx[q] <= max(nx[p], nx[r]) && nx[q] >= min(nx[p], nx[r])
                && ny[q] <= max(ny[p], ny[r]) && ny[q] >= min(ny[p], ny[r])
        }
        let o1 = sign(area(p1, q1, p2)), o2 = sign(area(p1, q1, q2))
        let o3 = sign(area(p2, q2, p1)), o4 = sign(area(p2, q2, q1))
        if o1 != o2 && o3 != o4 { return true }
        if o1 == 0 && onSegment(p1, p2, q1) { return true }
        if o2 == 0 && onSegment(p1, q2, q1) { return true }
        if o3 == 0 && onSegment(p2, p1, q2) { return true }
        if o4 == 0 && onSegment(p2, q1, q2) { return true }
        return false
    }

    private func intersectsPolygon(_ a: Int, _ b: Int) -> Bool {
        var p = a
        repeat {
            let q = next[p]
            if vi[p] != vi[a] && vi[q] != vi[a] && vi[p] != vi[b] && vi[q] != vi[b]
                && intersects(p, q, a, b) {
                return true
            }
            p = q
        } while p != a
        return false
    }

    private func locallyInside(_ a: Int, _ b: Int) -> Bool {
        area(prev[a], a, next[a]) < 0
            ? area(a, b, next[a]) >= 0 && area(a, prev[a], b) >= 0
            : area(a, b, prev[a]) < 0 || area(a, next[a], b) < 0
    }

    private func middleInside(_ a: Int, _ b: Int) -> Bool {
        var p = a
        var inside = false
        let px = (nx[a] + nx[b]) / 2, py = (ny[a] + ny[b]) / 2
        repeat {
            let q = next[p]
            if (ny[p] > py) != (ny[q] > py) && ny[q] != ny[p]
                && px < (nx[q] - nx[p]) * (py - ny[p]) / (ny[q] - ny[p]) + nx[p] {
                inside.toggle()
            }
            p = q
        } while p != a
        return inside
    }

    /// Link `a` to `b` with a two-way bridge; returns the copy of `b`.
    private mutating func splitPolygon(_ a: Int, _ b: Int) -> Int {
        let a2 = insertNode(vi[a], -1), b2 = insertNode(vi[b], -1)
        let an = next[a], bp = prev[b]
        next[a] = b; prev[b] = a
        next[a2] = an; prev[an] = a2
        next[b2] = a2; prev[a2] = b2
        next[bp] = b2; prev[b2] = bp
        return b2
    }

    // MARK: z-order hash

    private func zOrder(_ x: Double, _ y: Double) -> Int32 {
        var xi = Int32(truncatingIfNeeded: Int((x - minX) * invSize))
        var yi = Int32(truncatingIfNeeded: Int((y - minY) * invSize))
        xi = (xi | (xi << 8)) & 0x00FF00FF; xi = (xi | (xi << 4)) & 0x0F0F0F0F
        xi = (xi | (xi << 2)) & 0x33333333; xi = (xi | (xi << 1)) & 0x55555555
        yi = (yi | (yi << 8)) & 0x00FF00FF; yi = (yi | (yi << 4)) & 0x0F0F0F0F
        yi = (yi | (yi << 2)) & 0x33333333; yi = (yi | (yi << 1)) & 0x55555555
        return xi | (yi << 1)
    }

    private mutating func indexCurve(_ start: Int) {
        var p = start
        repeat {
            if z[p] == 0 { z[p] = zOrder(nx[p], ny[p]) }
            prevZ[p] = prev[p]; nextZ[p] = next[p]
            p = next[p]
        } while p != start
        nextZ[prevZ[p]] = -1
        prevZ[p] = -1
        sortLinked(p)
    }

    /// Simon Tatham's linked-list merge sort on `z`.
    private mutating func sortLinked(_ listIn: Int) {
        var list = listIn
        var inSize = 1
        var merges: Int
        repeat {
            var p = list
            list = -1
            var tail = -1
            merges = 0
            while p >= 0 {
                merges += 1
                var q = p
                var pSize = 0
                for _ in 0..<inSize {
                    pSize += 1
                    q = nextZ[q]
                    if q < 0 { break }
                }
                var qSize = inSize
                while pSize > 0 || (qSize > 0 && q >= 0) {
                    let e: Int
                    if pSize != 0 && (qSize == 0 || q < 0 || z[p] <= z[q]) {
                        e = p; p = nextZ[p]; pSize -= 1
                    } else {
                        e = q; q = nextZ[q]; qSize -= 1
                    }
                    if tail >= 0 { nextZ[tail] = e } else { list = e }
                    prevZ[e] = tail
                    tail = e
                }
                p = q
            }
            nextZ[tail] = -1
            inSize *= 2
        } while merges > 1
    }
}
