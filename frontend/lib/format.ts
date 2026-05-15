export function fmt(n: number): string {
  return n.toLocaleString("ko-KR");
}

export function fmtThousand(n: number): string {
  return Math.round(n / 1000).toLocaleString("ko-KR");
}
