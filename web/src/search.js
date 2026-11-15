// 英雄搜索：首页网格和顶栏快速搜索共用的一套打分逻辑
export function norm(s) {
  return (s || '').toLowerCase().replace(/[\s·,，/._'’\-—()（）[\]【】]+/g, '')
}

export function editDistance(a, b) {
  if (a === b) return 0
  if (!a.length) return b.length
  if (!b.length) return a.length
  let prev = Array.from({ length: b.length + 1 }, (_, i) => i)
  for (let i = 1; i <= a.length; i++) {
    const cur = [i]
    for (let j = 1; j <= b.length; j++) {
      cur[j] = Math.min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1))
    }
    prev = cur
  }
  return prev[b.length]
}

export function score(c, q) {
  const fields = (c.search || '').split('|').map(norm).filter(Boolean)
  if (fields.some(f => f === q)) return 100
  if (fields.some(f => f.startsWith(q))) return 80
  if ((c.search || '').includes(q)) return 60
  if (q.length >= 3) {
    if (fields.some(f => f.length <= q.length + 2 && editDistance(q, f) <= 1)) return 35
  }
  return 0
}

export function compareKey(a, b) {
  const A = a.sort_key.split(' '), B = b.sort_key.split(' ')
  for (let i = 0; i < Math.min(A.length, B.length); i++) {
    const c = A[i].localeCompare(B[i])
    if (c) return c
  }
  return A.length - B.length
}

export function searchChampions(champions, query, favoriteSet = new Set()) {
  const q = norm(query)
  if (!q) return []
  return champions
    .map(c => ({ c, s: score(c, q) }))
    .filter(x => x.s > 0)
    .sort((a, b) => b.s - a.s
      || (favoriteSet.has(b.c.id) ? 1 : 0) - (favoriteSet.has(a.c.id) ? 1 : 0)
      || compareKey(a.c, b.c))
    .map(x => x.c)
}
