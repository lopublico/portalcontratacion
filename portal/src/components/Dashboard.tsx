import { useState, useEffect } from 'react';
import {
  LineChart, Line, BarChart, Bar, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { api, type EstadisticasGenerales, type PuntoAnual, type SectorCpv } from '../lib/api';
import cpvData from '../data/cpv.json';

const NOMBRES_DIVISION: Record<string, string> = Object.fromEntries(
  Object.entries(cpvData as Record<string, string>)
    .filter(([k]) => k !== '_fuente' && k.endsWith('000000'))
    .map(([k, v]) => [k.slice(0, 2), v])
);

// si cambia el año hay que actualizar también el filtro de datos parciales del footer de la gráfica
const ANNO_ACTUAL = 2026;
const ANNO_MIN = 2012;

const TIPO_META: Record<string, { etiqueta: string; desc: string }> = {
  licitaciones: { etiqueta: 'Licitaciones',            desc: 'Contratos con licitación pública — obras, servicios y suministros' },
  menores:      { etiqueta: 'Contratos menores',        desc: 'Adjudicación directa sin licitación (< 15.000 € servicios / < 40.000 € obras)' },
  encargos:     { etiqueta: 'Encargos a medio propio',  desc: 'Encargos entre entidades públicas, sin concurrencia de mercado' },
  consultas:    { etiqueta: 'Consultas preliminares',   desc: 'Consultas al mercado previas a la licitación — sin importe' },
};

const FILTROS_TIPO = [
  { valor: '',             etiqueta: 'Todos',        color: null },
  { valor: 'licitaciones', etiqueta: 'Licitaciones', color: '#0A8FA8' },
  { valor: 'menores',      etiqueta: 'Menores',      color: '#C08800' },
  { valor: 'encargos',     etiqueta: 'Encargos',     color: '#B03888' },
];

const CPV_COLORS = [
  '#0A8FA8', '#C03838', '#5A7EC0', '#C08800', '#5E9040',
  '#B03888', '#C8922A', '#508030', '#8E6AAC', '#7E7A6C',
];

function fmtM(n: number | null | undefined) {
  if (n == null || n === 0) return '—';
  if (Math.abs(n) >= 1_000_000_000) return `${(n / 1_000_000_000).toLocaleString('es-ES', { maximumFractionDigits: 1 })} mil millones €`;
  if (Math.abs(n) >= 1_000_000)     return `${(n / 1_000_000).toLocaleString('es-ES', { maximumFractionDigits: 0 })} M €`;
  return `${(n / 1_000).toLocaleString('es-ES', { maximumFractionDigits: 0 })} mil €`;
}

function fmtNum(n: number | null | undefined) {
  if (n == null) return '—';
  return n.toLocaleString('es-ES');
}

function RankList({ items }: { items: { nombre: string; importe: number | null; href: string | null }[] }) {
  return (
    <div className="flex flex-col gap-2">
      {items.map((item, idx) => (
        <div key={idx} className="flex items-start justify-between gap-3">
          {item.href
            ? <a href={item.href} className="text-sm font-medium hover:underline min-w-0 leading-snug [display:-webkit-box] [-webkit-line-clamp:2] [-webkit-box-orient:vertical] overflow-hidden">
                {item.nombre}
              </a>
            : <span className="text-sm font-medium min-w-0 leading-snug [display:-webkit-box] [-webkit-line-clamp:2] [-webkit-box-orient:vertical] overflow-hidden text-muted-foreground">
                {item.nombre}
              </span>
          }
          <span className="text-sm font-medium tabular-nums shrink-0 text-foreground">
            {fmtM(item.importe)}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats]                   = useState<EstadisticasGenerales | null>(null);
  const [evolucion, setEvolucion]           = useState<PuntoAnual[]>([]);
  const [tiposContrato, setTiposContrato]   = useState<{ tipo_contrato: string; num_contratos: number; total_adjudicado: number | null }[]>([]);
  const [sectores, setSectores]             = useState<SectorCpv[]>([]);
  const [totalOrganismos, setTotalOrg]      = useState<number | null>(null);
  const [totalAdjudicatarios, setTotalAdj]  = useState<number | null>(null);
  const [tipoEv, setTipoEv]                 = useState('');
  const [cargando, setCargando]             = useState(true);

  useEffect(() => {
    // el dashboard hace 6 llamadas; guardamos en sessionStorage para que las visitas
    // siguientes dentro del mismo tab sean inmediatas. el número del key invalida el caché si
    // cambia la estructura de los datos (basta subir dashboard_v1 → dashboard_v2)
    const CACHE_KEY = 'dashboard_v2';
    const cached = sessionStorage.getItem(CACHE_KEY);
    if (cached) {
      try {
        const { s, ev, tc, sec, orgTotal, adjTotal } = JSON.parse(cached);
        setStats(s);
        setEvolucion(ev);
        setTiposContrato(tc);
        setSectores(sec);
        setTotalOrg(orgTotal);
        setTotalAdj(adjTotal);
        setCargando(false);
        return;
      } catch { /* cache corrupto, recargamos */ }
    }

    Promise.all([
      api.estadisticas(),
      api.estadisticasAnual(),
      api.tipoContrato(),
      api.sectoresCpv(),
      api.organismos(undefined, 1, 1),
      api.adjudicatarios(undefined, 1, 1),
    ]).then(([s, ev, tc, sec, org, adj]) => {
      const evFiltrado = (ev as PuntoAnual[]).filter(p => p.anno >= ANNO_MIN && p.anno <= ANNO_ACTUAL + 1);
      const orgTotal = (org as any).total ?? null;
      const adjTotal = (adj as any).total ?? null;
      setStats(s);
      setEvolucion(evFiltrado);
      setTiposContrato(tc as any);
      setSectores(sec);
      setTotalOrg(orgTotal);
      setTotalAdj(adjTotal);
      sessionStorage.setItem(CACHE_KEY, JSON.stringify({ s, ev: evFiltrado, tc, sec, orgTotal, adjTotal }));
    }).catch(console.error).finally(() => setCargando(false));
  }, []);

  // la API devuelve una fila por (anno, tipo), así que sin filtro hay que agrupar por año sumando
  const evData = (() => {
    const base = tipoEv ? evolucion.filter(p => p.tipo === tipoEv) : evolucion;
    const acc: Record<number, { anno: number; num_contratos: number; total_adjudicado: number }> = {};
    base.forEach(p => {
      if (!acc[p.anno]) acc[p.anno] = { anno: p.anno, num_contratos: 0, total_adjudicado: 0 };
      acc[p.anno].num_contratos    += p.num_contratos;
      acc[p.anno].total_adjudicado += p.total_adjudicado ?? 0;
    });
    return Object.values(acc).sort((a, b) => a.anno - b.anno);
  })();

  const ev2026 = evolucion.filter(p => p.anno === ANNO_ACTUAL);
  const contratos2026      = ev2026.reduce((s, p) => s + p.num_contratos, 0);
  const licitaciones2026   = ev2026.find(p => p.tipo === 'licitaciones')?.num_contratos ?? 0;
  const menores2026        = ev2026.find(p => p.tipo === 'menores')?.num_contratos ?? 0;
  const importe2026        = ev2026.find(p => p.tipo === 'licitaciones')?.total_adjudicado ?? 0;
  const importeMenores2026 = ev2026.find(p => p.tipo === 'menores')?.total_adjudicado ?? 0;

  const tiposSinConsultas = stats?.por_tipo.filter(t => t.tipo !== 'consultas') ?? [];
  const totalImporte = tiposSinConsultas.reduce((s, t) => s + (t.total_adjudicado ?? 0), 0);
  const totalNum     = tiposSinConsultas.reduce((s, t) => s + t.num_contratos, 0);

  const TIPO_CONTRATO_LABEL: Record<string, string> = {
    '1': 'Obras', '2': 'Servicios', '3': 'Suministros',
    '4': 'Concesión obras', '5': 'Concesión servicios',
    '7': 'Patrimoniales', '8': 'Servicios ex Anexo II',
    '21': 'Concesión obra (ant.)', '22': 'Gestión servicios',
    '31': 'Arrendamiento', '32': 'Permuta',
    '40': 'Colaboración PP', '50': 'Mixto', '999': 'Sin clasificar',
  };

  const tipoContratoData = tiposContrato.slice(0, 6).map(t => ({
    label: TIPO_CONTRATO_LABEL[t.tipo_contrato] ?? `Tipo ${t.tipo_contrato}`,
    num:   t.num_contratos,
  }));

  const topSectores = sectores.slice(0, 10).map(s => ({
    division: s.division,
    nombre:   NOMBRES_DIVISION[s.division] ?? `División ${s.division}`,
    num:      s.num_contratos,
  }));
  const sectoresCol1 = topSectores.slice(0, 5);
  const sectoresCol2 = topSectores.slice(5, 10);

  if (cargando) {
    return (
      <div className="dashboard-skeleton space-y-8 animate-pulse">
        <div>
          <div className="h-3 w-32 bg-muted/30 rounded mb-3" />
          <div className="flex gap-4">
            {[0,1,2,3,4].map(i => <div key={i} className="h-24 bg-muted/30 rounded-lg flex-auto" />)}
          </div>
        </div>
        <div>
          <div className="h-3 w-24 bg-muted/30 rounded mb-3" />
          <div className="flex gap-4">
            {[0,1,2,3].map(i => <div key={i} className="h-24 bg-muted/30 rounded-lg flex-auto" />)}
          </div>
        </div>
        <div className="h-48 bg-muted/30 rounded-lg" />
        <div className="grid grid-cols-2 gap-6">
          {[0,1].map(i => <div key={i} className="h-56 bg-muted/30 rounded-lg" />)}
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard space-y-8">

      {/* KPIs 2026 */}
      <div className="kpi-section kpi-section-anual">
        <p className="text-xs text-muted-foreground uppercase tracking-wider mb-3">En lo que va de {ANNO_ACTUAL}</p>
        <div className="kpi-row flex flex-wrap gap-4">
          <div className="kpi-card border rounded-lg p-4 space-y-1 w-[calc(50%-0.5rem)] sm:w-auto sm:flex-1">
            <p className="text-xs text-muted-foreground">Contratos publicados</p>
            <p className="text-2xl font-bold tracking-tight text-foreground">{fmtNum(contratos2026 || null)}</p>
            <p className="text-xs text-muted-foreground">todos los tipos</p>
          </div>
          <div className="kpi-card border rounded-lg p-4 space-y-1 w-[calc(50%-0.5rem)] sm:w-auto sm:flex-1">
            <p className="text-xs text-muted-foreground">Licitaciones</p>
            <p className="text-2xl font-bold tracking-tight text-foreground">{fmtNum(licitaciones2026 || null)}</p>
            <p className="text-xs text-muted-foreground">expedientes</p>
          </div>
          <div className="kpi-card border rounded-lg p-4 space-y-1 w-[calc(50%-0.5rem)] sm:w-auto sm:flex-1">
            <p className="text-xs text-muted-foreground">Importe licitaciones</p>
            <p className="text-2xl font-bold tracking-tight text-foreground">{fmtM(importe2026 || null)}</p>
            <p className="text-xs text-muted-foreground">sin IVA · adjudicado</p>
          </div>
          <div className="kpi-card border rounded-lg p-4 space-y-1 w-[calc(50%-0.5rem)] sm:w-auto sm:flex-1">
            <p className="text-xs text-muted-foreground">Contratos menores</p>
            <p className="text-2xl font-bold tracking-tight text-foreground">{fmtNum(menores2026 || null)}</p>
            <p className="text-xs text-muted-foreground">adjudicación directa</p>
          </div>
          <div className="kpi-card border rounded-lg p-4 space-y-1 w-[calc(50%-0.5rem)] sm:w-auto sm:flex-1">
            <p className="text-xs text-muted-foreground">Importe menores</p>
            <p className="text-2xl font-bold tracking-tight text-foreground">{fmtM(importeMenores2026 || null)}</p>
            <p className="text-xs text-muted-foreground">sin IVA · adjudicado</p>
          </div>
        </div>
      </div>

      {/* KPIs históricos */}
      <div className="kpi-section kpi-section-historico">
        <p className="text-xs text-muted-foreground uppercase tracking-wider mb-3">Desde {ANNO_MIN}</p>
        <div className="kpi-row flex flex-wrap gap-4">
          <div className="kpi-card border rounded-lg p-4 space-y-1 w-[calc(50%-0.5rem)] sm:w-auto sm:flex-1">
            <p className="text-xs text-muted-foreground">Registros totales</p>
            <p className="text-2xl font-bold tracking-tight text-foreground">{fmtNum(stats?.total)}</p>
            <p className="text-xs text-muted-foreground">licitaciones · menores · encargos</p>
          </div>
          <div className="kpi-card border rounded-lg p-4 space-y-1 w-[calc(50%-0.5rem)] sm:w-auto sm:flex-1">
            <p className="text-xs text-muted-foreground">Importe adjudicado</p>
            <p className="text-2xl font-bold tracking-tight text-foreground">{fmtM(stats?.por_tipo.find(t => t.tipo === 'licitaciones')?.total_adjudicado)}</p>
            <p className="text-xs text-muted-foreground">sin IVA · solo licitaciones</p>
          </div>
          <div className="kpi-card border rounded-lg p-4 space-y-1 w-[calc(50%-0.5rem)] sm:w-auto sm:flex-1">
            <p className="text-xs text-muted-foreground">Organismos</p>
            <p className="text-2xl font-bold tracking-tight text-foreground">{fmtNum(totalOrganismos)}</p>
            <p className="text-xs text-muted-foreground">contratantes distintos</p>
          </div>
          <div className="kpi-card border rounded-lg p-4 space-y-1 w-[calc(50%-0.5rem)] sm:w-auto sm:flex-1">
            <p className="text-xs text-muted-foreground">Adjudicatarios</p>
            <p className="text-2xl font-bold tracking-tight text-foreground">{fmtNum(totalAdjudicatarios)}</p>
            <p className="text-xs text-muted-foreground">empresas distintas</p>
          </div>
        </div>
      </div>

      {/* Distribución por tipo */}
      <div className="distribucion-tipo border rounded-lg p-4">
        <p className="text-sm font-medium mb-4">
          Distribución por tipo de contrato <span className="text-muted-foreground font-normal">· {ANNO_MIN}–{ANNO_ACTUAL}</span>
        </p>
        <div className="flex flex-col gap-5">
          {stats?.por_tipo.filter(t => t.tipo !== 'consultas').map(t => {
            const meta     = TIPO_META[t.tipo] ?? { etiqueta: t.tipo, desc: '' };
            const pctImp   = totalImporte > 0 && t.total_adjudicado != null ? (t.total_adjudicado / totalImporte * 100) : null;
            const pctNum   = totalNum > 0 ? (t.num_contratos / totalNum * 100) : 0;
            return (
              <div key={t.tipo} className="tipo-row">
                <div className="flex items-start justify-between gap-4 mb-2">
                  <div className="min-w-0">
                    <p className="text-sm font-medium leading-snug">{meta.etiqueta}</p>
                    <p className="text-xs text-muted-foreground leading-snug">{meta.desc}</p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-lg font-bold tabular-nums tracking-tight text-foreground">
                      {pctImp != null ? `${pctImp.toFixed(1)}%` : `${pctNum.toFixed(1)}%`}
                    </p>
                    {pctImp != null
                      ? <p className="text-xs text-muted-foreground tabular-nums">{fmtM(t.total_adjudicado)} adjudicado</p>
                      : <p className="text-xs text-muted-foreground tabular-nums">sin importe publicado</p>
                    }
                    <p className="text-xs text-muted-foreground tabular-nums">{t.num_contratos.toLocaleString('es-ES')} registros · {pctNum.toFixed(1)}% del total</p>
                  </div>
                </div>
                <div className="progress-bar h-1.5 bg-border rounded-full overflow-hidden">
                  <div className="progress-bar-fill h-full bg-foreground/25 rounded-full" style={{ width: `${pctImp ?? pctNum}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Evolución + sectores CPV */}
      <div className="graficas-grid grid grid-cols-1 md:grid-cols-2 gap-6">

        <div className="evolucion-card border rounded-lg p-4">
          <div className="evolucion-header flex items-start justify-between gap-2 mb-4 flex-wrap">
            <p className="text-sm font-medium">
              Evolución anual <span className="text-muted-foreground font-normal">· nº de contratos</span>
            </p>
            <div className="filtros-evolucion flex gap-1 flex-wrap">
              {FILTROS_TIPO.map(f => {
                const activo = tipoEv === f.valor;
                return (
                  <button
                    key={f.valor}
                    onClick={() => setTipoEv(f.valor)}
                    className="filtro-btn text-xs px-2 py-0.5 rounded border transition-colors whitespace-nowrap flex items-center gap-1"
                    style={activo && f.color
                      ? { borderColor: f.color, background: f.color, color: '#fff' }
                      : activo
                      ? { borderColor: '#111', background: '#111', color: '#fff' }
                      : { borderColor: '#e5e7eb', color: '#6b7280' }
                    }
                  >
                    {f.color && <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: activo ? '#fff' : f.color }} />}
                    {f.etiqueta}
                  </button>
                );
              })}
            </div>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={evData}>
              <CartesianGrid vertical={false} stroke="#e5e7eb" />
              <XAxis dataKey="anno" tick={{ fontSize: 11, fill: '#6b7280' }} axisLine={false} tickLine={false} />
              <YAxis
                tick={{ fontSize: 11, fill: '#6b7280' }} axisLine={false} tickLine={false} width={52}
                tickFormatter={v => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v)}
              />
              <Tooltip
                formatter={(v: number) => [v.toLocaleString('es-ES'), 'Contratos']}
                contentStyle={{ fontSize: 12, border: '1px solid #e5e7eb', borderRadius: 6 }}
                cursor={{ stroke: '#e5e7eb' }}
              />
              <Line
                dataKey="num_contratos"
                stroke="rgba(17,17,17,0.6)" strokeWidth={2}
                dot={false} activeDot={{ r: 4, fill: '#111' }}
              />
            </LineChart>
          </ResponsiveContainer>
          <p className="text-xs text-muted-foreground mt-2">
            {ANNO_ACTUAL} muestra datos parciales: el año está en curso y muchos contratos publicados en {ANNO_ACTUAL} aún no tienen adjudicación registrada.
          </p>
        </div>

        <div className="tipo-contrato-card border rounded-lg p-4">
          <p className="text-sm font-medium mb-4">
            Por tipo de contrato <span className="text-muted-foreground font-normal">· nº de contratos</span>
          </p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={tipoContratoData} layout="vertical" barSize={12} margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid horizontal={false} stroke="#e5e7eb" />
              <XAxis
                type="number" tick={{ fontSize: 10, fill: '#6b7280' }} axisLine={false} tickLine={false}
                tickFormatter={v => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v)}
              />
              <YAxis
                type="category" dataKey="label"
                tick={{ fontSize: 10, fill: '#6b7280' }} axisLine={false} tickLine={false} width={90}
              />
              <Tooltip
                formatter={(v: number) => [v.toLocaleString('es-ES'), 'Contratos']}
                contentStyle={{ fontSize: 12, border: '1px solid #e5e7eb', borderRadius: 6 }}
                cursor={false}
              />
              <Bar dataKey="num" radius={[0, 3, 3, 0]} background={{ fill: 'transparent' }}>
                {tipoContratoData.map((_entry, i) => (
                  <Cell key={i} fill={CPV_COLORS[i % CPV_COLORS.length]} fillOpacity={0.75} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <p className="text-xs text-muted-foreground mt-2">
            «Servicios ex Anexo II» son contratos de la LCSP anterior a 2017 (consultoría, I+D, salud…) con régimen aligerado. La LCSP 2017 eliminó esta categoría; los registros corresponden a datos históricos.
          </p>
        </div>

      </div>

      {/* Principales sectores CPV: top 10 dividido en dos columnas de 5 para mejor lectura */}
      <div className="sectores-cpv-card border rounded-lg p-4">
        <p className="text-sm font-medium mb-3">
          Principales sectores CPV <span className="text-muted-foreground font-normal">· nº de contratos</span>
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8">
          {[sectoresCol1, sectoresCol2].map((col, ci) => (
            <div key={ci}>
              {col.map((s, idx) => {
                const rank = ci * 5 + idx + 1;
                return (
                  <div key={s.division} className="cpv-row flex items-center justify-between gap-3 py-1.5 border-b border-border/50">
                    <div className="flex items-baseline gap-1.5 min-w-0 flex-1">
                      <span className="text-xs tabular-nums text-foreground shrink-0 w-4 text-right">{rank}</span>
                      <span className="text-xs text-muted-foreground/60 shrink-0">{"-"}</span>
                      <span className="text-xs text-muted-foreground/60 shrink-0">{s.division}</span>
                      <span className="text-xs text-muted-foreground truncate flex-1">{s.nombre}</span>
                    </div>
                    <span className="text-xs tabular-nums font-medium text-foreground shrink-0">{s.num.toLocaleString('es-ES')}</span>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>

      {/* Top organismos + adjudicatarios */}
      <div className="top-rankings grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="top-organismos-card border rounded-lg p-4">
          <p className="text-sm font-medium mb-4">
            Top organismos <span className="text-muted-foreground font-normal">— importe adjudicado</span>
          </p>
          <RankList items={stats?.top_organismos.map(o => ({
            nombre:  o.organo_nombre,
            importe: o.total_adjudicado,
            href:    o.organo_id_plataforma ? `/organismos/${o.organo_id_plataforma}` : null,
          })) ?? []} />
        </div>
        <div className="top-adjudicatarios-card border rounded-lg p-4">
          <p className="text-sm font-medium mb-4">
            Top adjudicatarios <span className="text-muted-foreground font-normal">— importe recibido</span>
          </p>
          <RankList items={stats?.top_adjudicatarios.map(a => ({
            nombre:  a.adjudicatario_nombre,
            importe: a.total_adjudicado,
            href:    (a.adjudicatario_id ?? a.adjudicatario_nif) ? `/adjudicatarios/${encodeURIComponent(a.adjudicatario_id ?? a.adjudicatario_nif ?? '')}` : null,
          })) ?? []} />
        </div>
      </div>

    </div>
  );
}
