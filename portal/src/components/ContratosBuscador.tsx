import { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { api, atomNum, type PaginaContratos, type SectorCpv } from '../lib/api';
import cpvData from '../data/cpv.json';

const NOMBRES_DIVISION: Record<string, string> = Object.fromEntries(
  Object.entries(cpvData as Record<string, string>)
    .filter(([k]) => k !== '_fuente' && k.endsWith('000000'))
    .map(([k, v]) => [k.slice(0, 2), v])
);

const TIPO_CONTRATO: Record<string, string> = {
  '1': 'Obras', '2': 'Servicios', '3': 'Suministros',
  '4': 'Concesión obras', '5': 'Concesión servicios', '7': 'Otros',
};

const ESTADOS: Record<string, { etiqueta: string; color: string; desc: string }> = {
  ADJ: { etiqueta: 'Adjudicada',    color: '#5E9040', desc: 'El contrato ha sido adjudicado a un proveedor.' },
  PUB: { etiqueta: 'Publicada',     color: '#5A7EC0', desc: 'Publicado y en plazo de presentación de ofertas.' },
  EV:  { etiqueta: 'En evaluación', color: '#C8922A', desc: 'Plazo cerrado; mesa de contratación evaluando.' },
  RES: { etiqueta: 'Resuelta',      color: '#7E7A6C', desc: 'Contrato formalizado y en ejecución.' },
  ANUL:{ etiqueta: 'Anulada',       color: '#C03838', desc: 'El procedimiento ha sido anulado.' },
  DES: { etiqueta: 'Desierta',      color: '#8E6AAC', desc: 'La Administración desistió de contratar.' },
};

const TIPOS_EXPEDIENTE = [
  { valor: 'licitaciones', etiqueta: 'Licitaciones',            punto: '#0A8FA8', desc: 'Contratos con licitación pública (obras, servicios, suministros).' },
  { valor: 'menores',      etiqueta: 'Contratos menores',       punto: '#C08800', desc: 'Adjudicación directa sin licitación (< 15.000 € servicios / < 40.000 € obras).' },
  { valor: 'encargos',     etiqueta: 'Encargos a medio propio', punto: '#B03888', desc: 'Encargos entre entidades públicas, sin concurrencia de mercado.' },
  { valor: 'consultas',    etiqueta: 'Consultas preliminares',  punto: '#508030', desc: 'Sondeos al mercado previos a la licitación, sin adjudicatario.' },
];

const PROCEDIMIENTOS = [
  { valor: '1',  etiqueta: 'Abierto',                      desc: 'Cualquier empresa puede presentar oferta.' },
  { valor: '9',  etiqueta: 'Abierto simplificado',         desc: 'Procedimiento abierto con trámites reducidos (LCSP 2017).' },
  { valor: '2',  etiqueta: 'Restringido',                  desc: 'Solo pueden licitar empresas previamente seleccionadas.' },
  { valor: '3',  etiqueta: 'Negociado con publicidad',     desc: 'Negociación directa con anuncio público previo.' },
  { valor: '7',  etiqueta: 'Negociado sin publicidad',     desc: 'Adjudicación directa por causas tasadas en la ley.' },
  { valor: '4',  etiqueta: 'Diálogo competitivo',          desc: 'Para contratos complejos cuyas especificaciones no pueden fijarse de antemano.' },
  { valor: '13', etiqueta: 'Asociación innovación',        desc: 'I+D con solución aún no disponible en el mercado.' },
];

const TIPO_EXPEDIENTE_BADGE: Record<string, { label: string; bg: string; color: string; border: string }> = {
  licitaciones: { label: 'Licitación', bg: 'rgba(10,143,168,0.04)',  color: '#065A68', border: 'rgba(10,143,168,0.25)' },
  menores:      { label: 'Menor',      bg: 'rgba(192,136,0,0.04)',   color: '#705000', border: 'rgba(192,136,0,0.25)' },
  encargos:     { label: 'Encargo',    bg: 'rgba(176,56,136,0.04)',  color: '#6C1250', border: 'rgba(176,56,136,0.25)' },
  consultas:    { label: 'Consulta',   bg: 'rgba(80,128,48,0.04)',   color: '#285010', border: 'rgba(80,128,48,0.25)' },
};

const TIPOS_CONTRATO = [
  { valor: '1', etiqueta: 'Obras',               desc: 'Construcción, reforma o demolición de bienes inmuebles.' },
  { valor: '2', etiqueta: 'Servicios',            desc: 'Prestación de servicios a la Administración.' },
  { valor: '3', etiqueta: 'Suministros',          desc: 'Entrega de bienes muebles o equipamiento.' },
  { valor: '4', etiqueta: 'Concesión de obras',   desc: 'El concesionario construye y explota la obra.' },
  { valor: '5', etiqueta: 'Concesión de servicios', desc: 'El concesionario gestiona el servicio público.' },
  { valor: '7', etiqueta: 'Otros',               desc: 'Tipos no clasificados en las categorías anteriores.' },
];

const POR_PAGINA_OPCIONES = [10, 20, 50, 100];
const EXPORT_CAP = 50_000;

const BASE_API = (typeof import.meta !== 'undefined' && (import.meta as any).env?.PUBLIC_API_URL) ?? 'http://localhost:8000';

function buildExportUrl(params: {
  q?: string; organismo_q?: string; adjudicatario_q?: string;
  tipo?: string; estado?: string; tipo_contrato?: string; cpv_sector?: string;
  fecha_desde?: string; fecha_hasta?: string;
  importe_min?: number; importe_max?: number; orden?: string;
  formato: 'csv' | 'json' | 'xlsx';
}): string {
  const url = new URL(`${BASE_API}/contratos/exportar`);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, String(v));
  });
  return url.toString();
}

function fmtImporte(n: number | null) {
  if (n == null) return '—';
  if (n >= 1_000_000) return `${(n / 1_000_000).toLocaleString('es-ES', { maximumFractionDigits: 1 })} M €`;
  return `${n.toLocaleString('es-ES', { maximumFractionDigits: 0 })} €`;
}

function fmtFecha(s: string | null) {
  if (!s || s === 'NaT') return '—';
  const fecha = s.slice(0, 10);
  const [y, m, d] = fecha.split('-');
  const anyo = parseInt(y, 10);
  if (anyo < 2000 || anyo > 2099) return '—';
  return `${d}/${m}/${y.slice(2)}`;
}

function toggle(set: Set<string>, valor: string): Set<string> {
  const next = new Set(set);
  next.has(valor) ? next.delete(valor) : next.add(valor);
  return next;
}

function Tooltip({ texto, children, dir = 'up' }: { texto: string; children: React.ReactNode; dir?: 'up' | 'down' }) {
  const pos = dir === 'down'
    ? 'top-full mt-2'
    : 'bottom-full mb-2';
  return (
    <span className="relative group/tip inline-flex items-center">
      {children}
      <span className={`pointer-events-none absolute z-50 ${pos} left-1/2 -translate-x-1/2 w-52 rounded-md border border-border bg-white dark:bg-zinc-900 px-2.5 py-1.5 text-xs text-foreground shadow-lg opacity-0 group-hover/tip:opacity-100 transition-opacity duration-150 text-left leading-relaxed`}>
        {texto}
      </span>
    </span>
  );
}

function IconInfo({ texto, dir }: { texto: string; dir?: 'up' | 'down' }) {
  return (
    <Tooltip texto={texto} dir={dir}>
      <span className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full border border-current text-[9px] leading-none cursor-help shrink-0 opacity-40 hover:opacity-80 transition-opacity ml-1">
        i
      </span>
    </Tooltip>
  );
}

// versión de IconInfo para usar dentro de <th> — los tooltips normales quedan cortados
// por el overflow:hidden de la tabla, así que este usa un portal y posición fija con getBoundingClientRect
function ThIconInfo({ texto }: { texto: string }) {
  const [rect, setRect] = useState<DOMRect | null>(null);
  return (
    <span
      className="relative inline-flex items-center"
      onMouseEnter={e => setRect((e.currentTarget as HTMLElement).getBoundingClientRect())}
      onMouseLeave={() => setRect(null)}
    >
      <span className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full border border-current text-[9px] leading-none cursor-help shrink-0 opacity-40 hover:opacity-80 transition-opacity ml-1">
        i
      </span>
      {rect && createPortal(
        <span
          className="fixed z-[9999] w-52 rounded-md border border-border bg-white px-2.5 py-1.5 text-xs text-foreground shadow-lg pointer-events-none leading-relaxed"
          style={{ left: rect.left + rect.width / 2, top: rect.top - 8, transform: 'translate(-50%, -100%)' }}
        >
          {texto}
        </span>,
        document.body
      )}
    </span>
  );
}

function SeccionFiltro({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <div className="filtro-seccion mb-4">
      <p className="text-[10px] font-semibold text-foreground/50 uppercase tracking-widest mb-2 border-b border-border pb-1">
        {titulo}
      </p>
      {children}
    </div>
  );
}

function MultiPills({ opciones, seleccion, onChange }: {
  opciones: { valor: string; etiqueta: string; punto?: string; desc?: string }[];
  seleccion: Set<string>;
  onChange: (s: Set<string>) => void;
}) {
  return (
    <div className="multi-pills flex flex-col gap-0.5">
      {opciones.map(op => {
        const activo = seleccion.has(op.valor);
        return (
          <button
            key={op.valor}
            onClick={() => onChange(toggle(seleccion, op.valor))}
            className={[
              'pill-btn flex items-center gap-2 text-sm px-2 py-1 rounded text-left w-full transition-colors group',
              activo
                ? 'bg-muted text-foreground font-medium'
                : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground',
            ].join(' ')}
          >
            {op.punto && (
              <span className="w-2 h-2 rounded-full shrink-0" style={{ background: op.punto }} />
            )}
            <span className="flex-1 truncate">{op.etiqueta}</span>
            {op.desc && <IconInfo texto={op.desc} />}
          </button>
        );
      })}
    </div>
  );
}

function Paginacion({ pagina, paginas, onChange }: {
  pagina: number; paginas: number; onChange: (p: number) => void;
}) {
  if (paginas <= 1) return null;

  const mostrarUltima = paginas <= 9999;

  const pagesToShow: number[] = [];
  if (paginas <= 7) {
    for (let i = 1; i <= paginas; i++) pagesToShow.push(i);
  } else if (pagina <= 4) {
    pagesToShow.push(1, 2, 3, 4, 5, -1);
    if (mostrarUltima) pagesToShow.push(paginas);
  } else if (mostrarUltima && pagina >= paginas - 3) {
    pagesToShow.push(1, -1, paginas - 4, paginas - 3, paginas - 2, paginas - 1, paginas);
  } else {
    pagesToShow.push(1, -1, pagina - 1, pagina, pagina + 1, -2);
    if (mostrarUltima) pagesToShow.push(paginas);
  }

  return (
    <div className="paginacion flex justify-center pt-2">
        <div className="flex items-center gap-1 w-fit mx-auto">

      <button
        onClick={() => onChange(pagina - 1)}
        disabled={pagina <= 1}
        className="px-3 py-1.5 text-sm rounded border border-input disabled:opacity-40 hover:bg-muted transition-colors"
      >
        ‹
      </button>
      {pagesToShow.map((p, i) =>
        p < 0 ? (
          <span key={`ellipsis-${i}`} className="px-1 text-muted-foreground">…</span>
        ) : (
          <button
            key={p}
            onClick={() => onChange(p)}
            className={[
              'min-w-8 px-1.5 py-1.5 text-sm rounded border transition-colors',
              p === pagina ? 'border-foreground bg-foreground text-background' : 'border-input hover:bg-muted',
            ].join(' ')}
          >
            {p}
          </button>
        )
      )}
      <button
        onClick={() => onChange(pagina + 1)}
        disabled={pagina >= paginas}
        className="px-3 py-1.5 text-sm rounded border border-input disabled:opacity-40 hover:bg-muted transition-colors"
      >
        ›
      </button>
      </div>
    </div>
  );
}

export default function ContratosBuscador() {
  const [q, setQ]               = useState('');
  const [busOrg, setBusOrg]     = useState('');
  const [busAdj, setBusAdj]     = useState('');
  const [fTipos, setFTipos]     = useState<Set<string>>(new Set());
  const [fEstados, setFEstados] = useState<Set<string>>(new Set());
  const [fTiposCtto, setFTiposCtto] = useState<Set<string>>(new Set());
  const [fSectores, setFSectores]   = useState<Set<string>>(new Set());
  const [fFechaDesde, setFFechaDesde] = useState('');
  const [fFechaHasta, setFFechaHasta] = useState('');
  const [fImporteMin, setFImporteMin] = useState('');
  const [fImporteMax, setFImporteMax] = useState('');
  const [fProcedimientos, setFProcedimientos] = useState<Set<string>>(new Set());
  const [orden, setOrden]       = useState('fecha_desc');
  const [pagina, setPagina]     = useState(1);
  const [porPagina, setPorPagina] = useState(20);

  const [resultado, setResultado]   = useState<PaginaContratos | null>(null);
  const [cargando, setCargando]     = useState(false);
  const [sectores, setSectores]     = useState<SectorCpv[]>([]);

  useEffect(() => {
    api.sectoresCpv().then(setSectores).catch(() => {});
  }, []);

  const resetPagina = useCallback(() => setPagina(1), []);

  // debounce de 350ms: espera a que el usuario deje de escribir antes de lanzar la búsqueda
  useEffect(() => {
    const timer = setTimeout(async () => {
      setCargando(true);
      try {
        const data = await api.contratos({
          q:               q || undefined,
          organismo_q:     busOrg || undefined,
          adjudicatario_q: busAdj || undefined,
          tipo:            fTipos.size    > 0 ? [...fTipos].join(',')     : undefined,
          estado:          fEstados.size  > 0 ? [...fEstados].join(',')   : undefined,
          tipo_contrato:   fTiposCtto.size > 0 ? [...fTiposCtto].join(',') : undefined,
          cpv_sector:      fSectores.size > 0 ? [...fSectores].join(',') : undefined,
          fecha_desde:     fFechaDesde || undefined,
          fecha_hasta:     fFechaHasta || undefined,
          importe_min:     fImporteMin ? parseFloat(fImporteMin) : undefined,
          importe_max:     fImporteMax ? parseFloat(fImporteMax) : undefined,
          tipo_procedimiento: fProcedimientos.size > 0 ? [...fProcedimientos].join(',') : undefined,
          orden,
          pagina,
          por_pagina: porPagina,
        });
        setResultado(data);
      } catch {
        setResultado(null);
      } finally {
        setCargando(false);
      }
    }, 350);
    return () => clearTimeout(timer);
  }, [q, busOrg, busAdj, fTipos, fEstados, fTiposCtto, fSectores, fFechaDesde, fFechaHasta, fImporteMin, fImporteMax, fProcedimientos, orden, pagina, porPagina]);

  // los sectores CPV se cargan aparte porque no dependen de los filtros activos
  const opcionesEstado = Object.entries(ESTADOS).map(([k, v]) => ({
    valor: k, etiqueta: v.etiqueta, punto: v.color, desc: v.desc,
  }));

  const opcionesSectores = [
    ...sectores.slice(0, 20).map(s => ({
      valor: s.division,
      etiqueta: NOMBRES_DIVISION[s.division] ?? `División ${s.division}`,
    })),
    { valor: '99', etiqueta: 'Otros' },
  ];

  return (
    <div className="contratos-buscador flex gap-8">
      {/* Sidebar de filtros */}
      <aside className="buscador-sidebar w-52 shrink-0">

        <SeccionFiltro titulo="Expediente">
          <MultiPills
            opciones={TIPOS_EXPEDIENTE}
            seleccion={fTipos}
            onChange={s => { setFTipos(s); resetPagina(); }}
          />
        </SeccionFiltro>

        <SeccionFiltro titulo="Estado">
          <MultiPills
            opciones={opcionesEstado}
            seleccion={fEstados}
            onChange={s => { setFEstados(s); resetPagina(); }}
          />
        </SeccionFiltro>

        <SeccionFiltro titulo="Fecha de adjudicación">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs text-muted-foreground">
              Desde
              <input
                type="date"
                value={fFechaDesde}
                onChange={e => { setFFechaDesde(e.target.value); resetPagina(); }}
                min="2012-01-01"
                max="2026-12-31"
                className="mt-0.5 w-full h-8 rounded-md border border-input bg-transparent px-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </label>
            <label className="text-xs text-muted-foreground">
              Hasta
              <input
                type="date"
                value={fFechaHasta}
                onChange={e => { setFFechaHasta(e.target.value); resetPagina(); }}
                min="2012-01-01"
                max="2026-12-31"
                className="mt-0.5 w-full h-8 rounded-md border border-input bg-transparent px-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </label>
          </div>
        </SeccionFiltro>

        <SeccionFiltro titulo="Importe adjudicado sin IVA (€)">
          <div className="flex items-center gap-1.5">
            <input
              type="number"
              value={fImporteMin}
              onChange={e => { setFImporteMin(e.target.value); resetPagina(); }}
              placeholder="mín"
              min={0}
              className="w-full h-8 rounded-md border border-input bg-transparent px-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            />
            <span className="text-muted-foreground text-xs shrink-0">–</span>
            <input
              type="number"
              value={fImporteMax}
              onChange={e => { setFImporteMax(e.target.value); resetPagina(); }}
              placeholder="máx"
              min={0}
              className="w-full h-8 rounded-md border border-input bg-transparent px-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
        </SeccionFiltro>

        <SeccionFiltro titulo="Tipo de contrato">
          <MultiPills
            opciones={TIPOS_CONTRATO}
            seleccion={fTiposCtto}
            onChange={s => { setFTiposCtto(s); resetPagina(); }}
          />
        </SeccionFiltro>

        <SeccionFiltro titulo="Procedimiento">
          <MultiPills
            opciones={PROCEDIMIENTOS}
            seleccion={fProcedimientos}
            onChange={s => { setFProcedimientos(s); resetPagina(); }}
          />
        </SeccionFiltro>

        <SeccionFiltro titulo="Organismo">
          <input
            type="text"
            value={busOrg}
            onChange={e => { setBusOrg(e.target.value); resetPagina(); }}
            placeholder="Nombre…"
            className="w-full h-8 rounded-md border border-input bg-transparent px-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </SeccionFiltro>

        <SeccionFiltro titulo="Adjudicatario">
          <input
            type="text"
            value={busAdj}
            onChange={e => { setBusAdj(e.target.value); resetPagina(); }}
            placeholder="Nombre o NIF…"
            className="w-full h-8 rounded-md border border-input bg-transparent px-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            title="Busca por nombre o introduce un NIF exacto (p. ej. B30126163)"
          />
        </SeccionFiltro>

        {opcionesSectores.length > 0 && (
          <SeccionFiltro titulo="Sector (CPV)">
            <div className="multi-pills flex flex-col gap-0.5">
              {opcionesSectores.map(op => {
                const activo = fSectores.has(op.valor);
                const nombre = NOMBRES_DIVISION[op.valor] ?? `División ${op.valor}`;
                const truncado = nombre.length > 28;
                return (
                  <button
                    key={op.valor}
                    onClick={() => { setFSectores(toggle(fSectores, op.valor)); resetPagina(); }}
                    title={nombre}
                    className={[
                      'pill-btn flex items-center gap-2 text-sm px-2 py-1 rounded text-left w-full transition-colors',
                      activo
                        ? 'bg-muted text-foreground font-medium'
                        : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground',
                    ].join(' ')}
                  >
                    <span className="truncate">{truncado ? nombre.slice(0, 28) + '…' : nombre}</span>
                  </button>
                );
              })}
            </div>
          </SeccionFiltro>
        )}
      </aside>

      {/* Área de resultados */}
      <div className="buscador-resultados flex-1 min-w-0 space-y-3">
        {/* Barra superior: búsqueda y orden */}
        <div className="resultados-barra flex items-center gap-3">
          <input
            type="text"
            value={q}
            onChange={e => { setQ(e.target.value); resetPagina(); }}
            placeholder="Buscar por título u objeto…"
            className="flex-1 h-9 rounded-md border border-input bg-transparent px-3 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
          />
          <select
            value={orden}
            onChange={e => { setOrden(e.target.value); resetPagina(); }}
            className="h-9 rounded-md border border-input bg-transparent px-3 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="fecha_desc">Más recientes</option>
            <option value="fecha_asc">Más antiguos</option>
            <option value="importe_desc">Mayor importe</option>
            <option value="importe_asc">Menor importe</option>
          </select>
        </div>

        {/* Meta: total + exportar */}
        <div className="resultados-meta flex items-center justify-between gap-3">
          <p className="text-xs text-muted-foreground shrink-0">
            {cargando
              ? 'Cargando…'
              : resultado
                ? `${resultado.total.toLocaleString('es-ES')} expedientes · página ${resultado.pagina} de ${resultado.paginas.toLocaleString('es-ES')}`
                : ''}
          </p>
          <div className="resultados-exportar flex items-center gap-3">
            {(['json', 'csv', 'xlsx'] as const).map(fmt => (
              <a
                key={fmt}
                href={buildExportUrl({
                  q: q || undefined,
                  organismo_q: busOrg || undefined,
                  adjudicatario_q: busAdj || undefined,
                  tipo: fTipos.size > 0 ? [...fTipos].join(',') : undefined,
                  estado: fEstados.size > 0 ? [...fEstados].join(',') : undefined,
                  tipo_contrato: fTiposCtto.size > 0 ? [...fTiposCtto].join(',') : undefined,
                  cpv_sector: fSectores.size > 0 ? [...fSectores].join(',') : undefined,
                  fecha_desde: fFechaDesde || undefined,
                  fecha_hasta: fFechaHasta || undefined,
                  importe_min: fImporteMin ? parseFloat(fImporteMin) : undefined,
                  importe_max: fImporteMax ? parseFloat(fImporteMax) : undefined,
                  orden,
                  formato: fmt,
                })}
                download={`contratos.${fmt}`}
                className="exportar-btn inline-flex items-center gap-1 h-7 px-2 text-xs rounded border border-input hover:bg-muted transition-colors text-muted-foreground whitespace-nowrap uppercase font-mono tracking-wide"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="w-3 h-3 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
                {fmt}
              </a>
            ))}
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span>Mostrar</span>
              <select
                value={porPagina}
                onChange={e => { setPorPagina(Number(e.target.value)); resetPagina(); }}
                className="h-7 rounded border border-input bg-transparent px-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
              >
                {POR_PAGINA_OPCIONES.map(n => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
              <span>por página</span>
            </div>
          </div>
        </div>
        {resultado && resultado.total > EXPORT_CAP && (
          <p className="text-xs text-muted-foreground bg-muted/50 rounded px-3 py-2">
            La exportación está limitada a {EXPORT_CAP.toLocaleString('es-ES')} registros. Aplica más filtros para reducir los resultados.
          </p>
        )}

        {/* Tabla de resultados */}
        <div className={`tabla-contenedor rounded-md border transition-opacity ${cargando ? 'opacity-50' : ''}`}>
          <div className="overflow-x-auto">
          <table className="contratos-tabla w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/40">
                <th
                  className="px-3 py-2.5 text-left font-medium text-muted-foreground whitespace-nowrap cursor-pointer select-none hover:text-foreground transition-colors"
                  onClick={() => { setOrden(o => o === 'fecha_desc' ? 'fecha_asc' : 'fecha_desc'); resetPagina(); }}
                >
                  <span className="inline-flex items-center gap-0.5">
                    Fecha
                    <span className="opacity-50">{orden === 'fecha_desc' ? '↓' : orden === 'fecha_asc' ? '↑' : '↕'}</span>
                    <ThIconInfo texto="Fecha de adjudicación del contrato. Fechas con año > 2030 corresponden a errores en la publicación original en PLACSP." />
                  </span>
                </th>
                <th className="px-3 py-2.5 text-left font-medium text-muted-foreground">
                  Contrato
                </th>
                <th className="px-3 py-2.5 text-left font-medium text-muted-foreground whitespace-nowrap">
                  <span className="inline-flex items-center gap-0.5">
                    Organismo
                    <ThIconInfo texto="Entidad pública contratante. Haz clic en el nombre para ver su perfil con todos sus contratos." />
                  </span>
                </th>
                <th className="px-3 py-2.5 text-left font-medium text-muted-foreground whitespace-nowrap">
                  <span className="inline-flex items-center gap-0.5">
                    Adjudicatario
                    <ThIconInfo texto="Empresa o autónomo que gana el contrato. Haz clic en el nombre para ver su perfil con todos los contratos recibidos." />
                  </span>
                </th>
                <th
                  className="px-3 py-2.5 text-right font-medium text-muted-foreground whitespace-nowrap cursor-pointer select-none hover:text-foreground transition-colors"
                  onClick={() => { setOrden(o => o === 'importe_desc' ? 'importe_asc' : 'importe_desc'); resetPagina(); }}
                >
                  <span className="inline-flex items-center justify-end gap-0.5">
                    Importe s/IVA
                    <span className="opacity-50">{orden === 'importe_desc' ? '↓' : orden === 'importe_asc' ? '↑' : '↕'}</span>
                    <ThIconInfo texto="Importe adjudicado sin IVA, redondeado. Puede diferir del presupuesto base. Los valores — indican que el contrato aún no tiene adjudicatario." />
                  </span>
                </th>
                <th className="px-3 py-2.5 text-left font-medium text-muted-foreground whitespace-nowrap">
                  <span className="inline-flex items-center gap-0.5">
                    Estado
                    <ThIconInfo texto="Estado del expediente al momento de la última actualización en PLACSP." />
                  </span>
                </th>
              </tr>
            </thead>
            <tbody>
              {resultado?.resultados.map((c, i) => {
                const est = ESTADOS[c.estado] ?? { etiqueta: c.estado, color: '#9ca3af', desc: '' };
                return (
                  <tr key={`${c.num_expediente}-${i}`} className={i % 2 === 1 ? 'contrato-row bg-muted/20' : 'contrato-row'}>
                    <td className="px-3 py-2.5 font-mono text-xs text-muted-foreground whitespace-nowrap align-top">
                      {fmtFecha(c.fecha_adjudicacion ?? (['RES', 'ADJ'].includes(c.estado) ? c.fecha_actualizacion : null))}
                    </td>
                    <td className="px-3 py-2.5 align-top">
                      <div className="flex items-start gap-1.5 mb-1">
                        <a
                          href={c.id_atom ? `/contratos/${atomNum(c.id_atom)}` : '#'}
                          className="font-medium leading-snug hover:underline"
                        >
                          {c.titulo || c.objeto || '—'}
                        </a>
                        {c.url_placsp && (
                          <a
                            href={c.url_placsp}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="shrink-0 text-muted-foreground/50 hover:text-muted-foreground mt-0.5"
                            title="Ver en PLACSP"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                              <polyline points="15 3 21 3 21 9"/>
                              <line x1="10" y1="14" x2="21" y2="3"/>
                            </svg>
                          </a>
                        )}
                      </div>
                      {/* contrato-badges: chips de tipo (licitación/menor/encargo) y estado del contrato */}
                      <div className="contrato-badges flex gap-1.5 flex-wrap">
                        {(() => {
                          const b = TIPO_EXPEDIENTE_BADGE[c.tipo];
                          return b ? (
                            <span
                              className="text-xs border rounded px-1.5 py-0.5 font-medium"
                              style={{ background: b.bg, color: b.color, borderColor: b.border }}
                            >
                              {b.label}
                            </span>
                          ) : null;
                        })()}
                        <Tooltip texto={TIPOS_CONTRATO.find(t => t.valor === c.tipo_contrato)?.desc ?? ''}>
                          <span className="text-xs border border-border rounded px-1.5 py-0.5 text-muted-foreground cursor-help">
                            {TIPO_CONTRATO[c.tipo_contrato] ?? '—'}
                          </span>
                        </Tooltip>
                        {c.codigos_cpv?.[0] && (
                          <Tooltip texto={NOMBRES_DIVISION[c.codigos_cpv[0].slice(0, 2)] ?? c.codigos_cpv[0]}>
                            <span className="text-xs border border-border rounded px-1.5 py-0.5 font-mono text-muted-foreground cursor-help">
                              {c.codigos_cpv[0]}
                            </span>
                          </Tooltip>
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-2.5 align-top">
                      {c.organo_id_plataforma ? (
                        <a
                          href={`/organismos/${c.organo_id_plataforma}`}
                          className="text-xs text-muted-foreground hover:underline block"
                        >
                          {c.organo_nombre}
                        </a>
                      ) : (
                        <p className="text-xs text-muted-foreground">{c.organo_nombre}</p>
                      )}
                      <code className="text-xs text-muted-foreground/60">{c.organo_nif}</code>
                    </td>
                    <td className="px-3 py-2.5 align-top">
                      {c.adjudicatario_nombre ? (
                        <>
                          {c.adjudicatario_id ? (
                            <a
                              href={`/adjudicatarios/${c.adjudicatario_id}`}
                              className="text-xs text-muted-foreground hover:underline block"
                            >
                              {c.adjudicatario_nombre}
                            </a>
                          ) : (
                            <p className="text-xs text-muted-foreground">{c.adjudicatario_nombre}</p>
                          )}
                          <code className="text-xs text-muted-foreground/60">{c.adjudicatario_nif}</code>
                        </>
                      ) : (
                        <span className="text-muted-foreground/40">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums font-mono text-xs align-top">
                      {fmtImporte(c.importe_adjudicacion_sin_iva)}
                    </td>
                    <td className="px-3 py-2.5 align-top">
                      <Tooltip texto={est.desc}>
                        <span className="inline-flex items-center gap-1.5 text-xs cursor-help">
                          <span className="w-2 h-2 rounded-full shrink-0" style={{ background: est.color }} />
                          {est.etiqueta}
                        </span>
                      </Tooltip>
                    </td>
                  </tr>
                );
              })}
              {!cargando && resultado?.resultados.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-3 py-8 text-center text-sm text-muted-foreground">
                    Sin resultados para los filtros seleccionados.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          </div>
        </div>

        {resultado && (
          <Paginacion
            pagina={resultado.pagina}
            paginas={resultado.paginas}
            onChange={setPagina}
          />
        )}
      </div>
    </div>
  );
}
