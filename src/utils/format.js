export function fmtNum(value, decimals = 2) {
  if (value === null || value === undefined || value === '') return '0';
  const n = typeof value === 'string' ? parseFloat(value.replace(',', '.')) : Number(value);
  if (isNaN(n)) return '0';
  return n.toFixed(decimals).replace('.', ',');
}

export function parseNum(val) {
  if (val === null || val === undefined || val === '') return 0;
  const n = parseFloat(String(val).replace(',', '.'));
  return isNaN(n) ? 0 : n;
}
