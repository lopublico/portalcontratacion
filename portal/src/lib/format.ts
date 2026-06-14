export function formatEuro(n: number | null | undefined): string {
  if (n == null || isNaN(n)) return '—';
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return `${(n / 1_000_000).toLocaleString('es-ES', { maximumFractionDigits: 1 })} M €`;
  if (abs >= 1_000) return `${(n / 1_000).toLocaleString('es-ES', { maximumFractionDigits: 0 })} mil €`;
  return `${n.toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

export function formatNum(n: number | null | undefined): string {
  if (n == null || isNaN(n)) return '—';
  return n.toLocaleString('es-ES');
}

export function formatFecha(s: string | null | undefined): string {
  if (!s) return '—';
  const d = s.slice(0, 10);
  if (!d.includes('-')) return s;
  const [y, m, day] = d.split('-');
  const meses = ['ene.', 'feb.', 'mar.', 'abr.', 'may.', 'jun.',
                 'jul.', 'ago.', 'sep.', 'oct.', 'nov.', 'dic.'];
  return `${parseInt(day)} ${meses[parseInt(m) - 1]} ${y}`;
}

export function iniciales(nombre: string | null | undefined): string {
  if (!nombre) return '?';
  const palabras = nombre.trim().split(/\s+/);
  if (palabras.length === 1) return palabras[0].slice(0, 2).toUpperCase();
  return (palabras[0][0] + palabras[palabras.length - 1][0]).toUpperCase();
}

export function truncar(s: string | null | undefined, n: number): string {
  if (!s) return '—';
  return s.length > n ? s.slice(0, n) + '…' : s;
}

const TIPOS_CONTRATO: Record<string, string> = {
  '1': 'Obras', '2': 'Servicios', '3': 'Suministros',
  '4': 'Concesión obras', '5': 'Concesión servicios', '7': 'Otros',
};

export function labelTipoContrato(codigo: string | null | undefined): string {
  if (!codigo) return '—';
  return TIPOS_CONTRATO[codigo] ?? codigo;
}

const ESTADOS: Record<string, { etiqueta: string; clase: string }> = {
  ADJ:  { etiqueta: 'Adjudicada',     clase: 'estado-adj' },
  PUB:  { etiqueta: 'Publicada',      clase: 'estado-pub' },
  EV:   { etiqueta: 'En evaluación',  clase: 'estado-ev' },
  RES:  { etiqueta: 'Resuelta',       clase: 'estado-res' },
  ANUL: { etiqueta: 'Anulada',        clase: 'estado-anul' },
  DES:  { etiqueta: 'Desierta',       clase: 'estado-des' },
};

export function configEstado(estado: string | null | undefined) {
  return ESTADOS[estado ?? ''] ?? { etiqueta: estado ?? '—', clase: 'estado-des' };
}
