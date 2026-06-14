import { useState, useEffect } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { api, atomNum, type PerfilOrganismo, type PerfilAdjudicatario, type Contrato } from '../lib/api';
import { formatEuro, formatNum, iniciales } from '../lib/format';

// ─── tipos internos ───────────────────────────────────────────────────────────

type Evolucion      = { anno: number; contratos: number; importe: number };
type Contraparte    = { nombre: string; href: string; num_contratos: number; importe: number };
type ContratoReciente = { titulo: string; expediente: string; href: string | null; contraparte: string | null; contraparteHref: string | null; importe: number | null; fecha: string; estado: string };

type PerfilData = {
  tipo: 'organismo' | 'adjudicatario';
  nombre: string;
  nif: string | null;
  chips: string[];
  kpis: { etiqueta: string; valor: string; sub?: string }[];
  evolucion: Evolucion[];
  contrapartes: Contraparte[];
  ultimos: ContratoReciente[];
  concentracion: number;
};

// ─── transformaciones ─────────────────────────────────────────────────────────

const TIPO_ORGANISMO: Record<string, string> = {
  '1': 'Administración del Estado',
  '2': 'Administración autonómica',
  '3': 'Administración local',
  '4': 'Organismo autonómico',
  '5': 'Entidad pública',
  '6': 'Seguridad Social',
  '7': 'Universidad pública',
  '8': 'Organismo público',
  '9': 'Empresa pública',
};

// normaliza la respuesta de la API al tipo interno — separa la forma del API del render
function fromOrganismo(d: PerfilOrganismo): PerfilData {
  // qué % del importe total va a un solo proveedor — valor alto indica poca diversificación
  const concentracion = d.total_adjudicado
    ? ((d.principales_adjudicatarios[0]?.total_adjudicado ?? 0) / d.total_adjudicado) * 100
    : 0;
  return {
    tipo: 'organismo',
    nombre: d.organo_nombre,
    nif: d.organo_nif ?? null,
    chips: [
      d.organo_ciudad,
      d.organo_nif ? `NIF ${d.organo_nif}` : null,
    ].filter(Boolean) as string[],
    kpis: [
      { etiqueta: 'Contratos',      valor: formatNum(d.num_contratos),     sub: d.primer_contrato ? `desde ${String(d.primer_contrato).slice(0, 4)}` : undefined },
      { etiqueta: 'Importe total',  valor: formatEuro(d.total_adjudicado),  sub: 'adjudicado' },
      { etiqueta: 'Adjudicatarios', valor: formatNum(d.num_adjudicatarios), sub: 'distintos' },
      { etiqueta: 'Importe medio',  valor: formatEuro(d.importe_medio),     sub: 'por contrato' },
      { etiqueta: 'Concentración',  valor: `${concentracion.toFixed(1)}%`,  sub: 'al principal proveedor' },
    ],
    evolucion: d.por_anno.filter(p => p.anno >= 2012).map(p => ({ anno: p.anno, contratos: p.num_contratos, importe: p.total_adjudicado ?? 0 })),
    contrapartes: d.principales_adjudicatarios.slice(0, 5).map(a => ({
      nombre: a.adjudicatario_nombre,
      href: `/adjudicatarios/${encodeURIComponent(a.adjudicatario_nif ?? a.adjudicatario_nombre)}`,
      num_contratos: a.num_contratos,
      importe: a.total_adjudicado ?? 0,
    })),
    ultimos: (d.ultimos_contratos as any[]).map(c => ({
      titulo:          c.titulo ?? c.objeto ?? '(sin título)',
      expediente:      c.num_expediente ?? '—',
      href:            atomNum(c.id_atom) ? `/contratos/${atomNum(c.id_atom)}` : null,
      contraparte:     c.adjudicatario_nombre ?? null,
      contraparteHref: c.adjudicatario_id ? `/adjudicatarios/${encodeURIComponent(c.adjudicatario_id)}` : null,
      importe:         c.importe_adjudicacion_sin_iva ?? null,
      fecha:           c.fecha_adjudicacion ?? '',
      estado:          c.estado ?? 'PUB',
    })),
    concentracion,
  };
}

// normaliza la respuesta de la API al tipo interno — separa la forma del API del render
function fromAdjudicatario(d: PerfilAdjudicatario): PerfilData {
  // qué % del importe total viene de un solo cliente — valor alto indica poca diversificación
  const concentracion = d.total_adjudicado
    ? ((d.principales_organismos[0]?.total_adjudicado ?? 0) / d.total_adjudicado) * 100
    : 0;
  return {
    tipo: 'adjudicatario',
    nombre: d.adjudicatario_nombre,
    nif: d.adjudicatario_nif ?? null,
    chips: [
      d.adjudicatario_nif ? `NIF ${d.adjudicatario_nif}` : null,
      d.adjudicatario_pais && d.adjudicatario_pais !== 'ES' ? d.adjudicatario_pais : 'España',
    ].filter(Boolean) as string[],
    kpis: [
      { etiqueta: 'Contratos',     valor: formatNum(d.num_contratos),     sub: 'adjudicados' },
      { etiqueta: 'Importe total', valor: formatEuro(d.total_adjudicado),  sub: 'recibido' },
      { etiqueta: 'Organismos',    valor: formatNum(d.num_organismos),     sub: 'clientes' },
      { etiqueta: 'Importe medio', valor: formatEuro(d.importe_medio),     sub: 'por contrato' },
      { etiqueta: 'Concentración', valor: `${concentracion.toFixed(1)}%`,  sub: 'del principal cliente' },
    ],
    evolucion: d.por_anno.filter(p => p.anno >= 2012).map(p => ({ anno: p.anno, contratos: p.num_contratos, importe: p.total_adjudicado ?? 0 })),
    contrapartes: d.principales_organismos.slice(0, 5).map(o => ({
      nombre: o.organo_nombre,
      href:   o.organo_id_plataforma ? `/organismos/${encodeURIComponent(o.organo_id_plataforma)}` : '#',
      num_contratos: o.num_contratos,
      importe: o.total_adjudicado ?? 0,
    })),
    ultimos: ((d as any).ultimos_contratos ?? []).map((c: any) => ({
      titulo:          c.titulo ?? c.objeto ?? '(sin título)',
      expediente:      c.num_expediente ?? '—',
      href:            atomNum(c.id_atom) ? `/contratos/${atomNum(c.id_atom)}` : null,
      contraparte:     c.organo_nombre ?? null,
      contraparteHref: c.organo_id_plataforma ? `/organismos/${encodeURIComponent(c.organo_id_plataforma)}` : null,
      importe:         c.importe_adjudicacion_sin_iva ?? null,
      fecha:           c.fecha_adjudicacion ?? '',
      estado:          c.estado ?? 'ADJ',
    })),
    concentracion,
  };
}

// ─── subcomponentes ───────────────────────────────────────────────────────────

const ESTADOS: Record<string, { etiqueta: string; color: string }> = {
  ADJ:  { etiqueta: 'Adjudicada',    color: '#22c55e' },
  PUB:  { etiqueta: 'Publicada',     color: '#3b82f6' },
  EV:   { etiqueta: 'En evaluación', color: '#f59e0b' },
  RES:  { etiqueta: 'Resuelta',      color: '#6b7280' },
  ANUL: { etiqueta: 'Anulada',       color: '#ef4444' },
  DES:  { etiqueta: 'Desierta',      color: '#9ca3af' },
};

function RankBar({ items, maxImporte }: { items: { nombre: string; href: string; importe: number }[]; maxImporte: number }) {
  return (
    <div className="rank-list flex flex-col gap-3">
      {items.map(item => (
        <div key={item.nombre} className="rank-bar-item">
          <div className="flex items-center justify-between mb-1">
            <a href={item.href} className="text-sm font-medium hover:underline truncate mr-2">{item.nombre}</a>
            <span className="text-sm text-muted-foreground tabular-nums shrink-0">{formatEuro(item.importe)}</span>
          </div>
          <div className="rank-bar h-1 bg-border rounded-full overflow-hidden">
            <div className="rank-bar-fill h-full bg-foreground/20 rounded-full" style={{ width: `${(item.importe / maxImporte * 100).toFixed(1)}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function Skeleton() {
  return (
    <div className="perfil-skeleton space-y-8 animate-pulse">
      <div className="flex items-start gap-4">
        <div className="w-12 h-12 bg-muted rounded" />
        <div className="space-y-2 flex-1">
          <div className="h-4 bg-muted rounded w-1/4" />
          <div className="h-6 bg-muted rounded w-1/2" />
        </div>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => <div key={i} className="border rounded-lg p-4 h-24 bg-muted/30" />)}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="border rounded-lg h-64 bg-muted/20" />
        <div className="border rounded-lg h-64 bg-muted/20" />
      </div>
    </div>
  );
}

// ─── componente principal ─────────────────────────────────────────────────────

export default function PerfilEntidad({
  tipo,
  id,
}: {
  tipo: 'organismo' | 'adjudicatario';
  id: string;
}) {
  const [perfil, setPerfil] = useState<PerfilData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(false);
    // mismo componente para las dos rutas — la transformación hace el trabajo de adaptar la respuesta
    const fetcher = tipo === 'organismo'
      ? api.organismo(id).then(fromOrganismo)
      : api.adjudicatario(id).then(fromAdjudicatario);

    fetcher
      .then(p => { setPerfil(p); setLoading(false); })
      .catch(() => { setError(true); setLoading(false); });
  }, [id, tipo]);

  if (loading) return <Skeleton />;
  if (error || !perfil) return (
    <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
      No se ha podido cargar el perfil. Comprueba que la API está activa.
    </div>
  );

  const labelContrapartes = tipo === 'organismo' ? 'Principales adjudicatarios' : 'Principales organismos clientes';
  const maxContrapartes   = Math.max(...perfil.contrapartes.map(c => c.importe), 1);

  return (
    <div className="perfil-entidad space-y-8">

      {/* perfil-header: avatar con iniciales, nombre, tipo y chips de NIF/país */}
      <div className="perfil-header flex items-start gap-4">
        <div className="perfil-avatar w-12 h-12 rounded bg-muted flex items-center justify-center text-lg font-semibold shrink-0">
          {iniciales(perfil.nombre)}
        </div>
        <div>
          <p className="text-sm text-muted-foreground mb-1">
            {tipo === 'organismo' ? 'Organismo contratante' : 'Empresa adjudicataria'}
          </p>
          <h1 className="text-2xl font-semibold tracking-tight leading-snug">{perfil.nombre}</h1>
          {/* perfil-chips: NIF, país u otras etiquetas identificativas */}
          <div className="perfil-chips flex flex-wrap gap-1.5 mt-2">
            {perfil.chips.map(c => (
              <span key={c} className="perfil-chip text-xs border border-border rounded px-2 py-0.5 text-muted-foreground">{c}</span>
            ))}
          </div>
        </div>
      </div>

      {/* perfil-kpis: métricas resumen (contratos, importe total, contrapartes, importe medio, concentración) */}
      <div className="perfil-kpis grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-4">
        {perfil.kpis.map(k => (
          <div key={k.etiqueta} className="perfil-kpi border rounded-lg p-4 space-y-1">
            <p className="text-xs text-muted-foreground">{k.etiqueta}</p>
            <p className="text-2xl font-semibold tracking-tight">{k.valor}</p>
            {k.sub && <p className="text-xs text-muted-foreground">{k.sub}</p>}
          </div>
        ))}
      </div>

      {/* perfil-graficas: evolución anual de contratos y ranking de principales contrapartes */}
      <div className="perfil-graficas grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* perfil-evolucion: barras de número de contratos por año */}
        <div className="perfil-evolucion border rounded-lg p-4">
          <p className="text-sm font-medium mb-4">Evolución anual</p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={perfil.evolucion} barSize={28}>
              <CartesianGrid vertical={false} stroke="#e5e7eb" />
              <XAxis dataKey="anno" tick={{ fontSize: 11, fill: '#6b7280' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: '#6b7280' }} axisLine={false} tickLine={false} width={44} />
              <Tooltip
                formatter={(v: number) => [v.toLocaleString('es-ES'), 'Contratos']}
                contentStyle={{ fontSize: 12, border: '1px solid #e5e7eb', borderRadius: 6 }}
              />
              <Bar dataKey="contratos" fill="rgba(17,17,17,0.15)" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* perfil-contrapartes: ranking de los 5 principales adjudicatarios u organismos */}
        <div className="perfil-contrapartes border rounded-lg p-4">
          <p className="text-sm font-medium mb-4">{labelContrapartes}</p>
          {perfil.contrapartes.length > 0
            ? <RankBar items={perfil.contrapartes} maxImporte={maxContrapartes} />
            : <p className="text-sm text-muted-foreground">Sin datos</p>
          }
        </div>
      </div>

      {/* perfil-ultimos: tabla con los 10 contratos más recientes de esta entidad */}
      {perfil.ultimos.length > 0 && (
        <div className="perfil-ultimos">
          <div className="flex items-baseline justify-between mb-3">
            <p className="text-sm font-medium">Últimos contratos</p>
            <p className="text-xs text-muted-foreground">
              Se muestran los 10 más recientes.{' '}
              <a href="/contratos" className="hover:underline">
                Consulta el total en el buscador
              </a>
              {perfil.nif && (
                <> · CIF: <code className="font-mono">{perfil.nif}</code></>
              )}
            </p>
          </div>
          <div className="rounded-md border overflow-x-auto">
            {/* perfil-contratos-tabla: fecha, título con enlace, contraparte e importe de cada contrato */}
            <table className="perfil-contratos-tabla w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/40">
                  <th className="px-3 py-3 text-left font-medium text-muted-foreground w-24">Fecha</th>
                  <th className="px-3 py-3 text-left font-medium text-muted-foreground">Contrato</th>
                  <th className="px-3 py-3 text-left font-medium text-muted-foreground w-40">
                    {tipo === 'organismo' ? 'Adjudicatario' : 'Organismo'}
                  </th>
                  <th className="px-3 py-3 text-right font-medium text-muted-foreground w-28">Importe</th>
                  <th className="px-3 py-3 text-left font-medium text-muted-foreground w-28">Estado</th>
                </tr>
              </thead>
              <tbody>
                {perfil.ultimos.map((c, i) => {
                  const est = ESTADOS[c.estado] ?? { etiqueta: c.estado, color: '#9ca3af' };
                  return (
                    <tr key={c.expediente + i} className={i % 2 === 1 ? 'contrato-row bg-muted/20' : 'contrato-row'}>
                      <td className="px-3 py-3 font-mono text-xs text-muted-foreground align-top whitespace-nowrap">
                        {c.fecha ? c.fecha.slice(0, 10) : '—'}
                      </td>
                      <td className="px-3 py-3 align-top">
                        {c.href
                          ? <a href={c.href} className="font-medium leading-snug hover:underline block">{c.titulo}</a>
                          : <span className="font-medium leading-snug block">{c.titulo}</span>}
                        <code className="text-xs text-muted-foreground/60">{c.expediente}</code>
                      </td>
                      <td className="px-3 py-3 text-xs text-muted-foreground align-top">
                        {c.contraparte
                          ? c.contraparteHref
                            ? <a href={c.contraparteHref} className="hover:underline">{c.contraparte}</a>
                            : c.contraparte
                          : '—'}
                      </td>
                      <td className="px-3 py-3 text-right tabular-nums font-mono align-top">{formatEuro(c.importe)}</td>
                      <td className="px-3 py-3 align-top">
                        <span className="inline-flex items-center gap-1.5 text-xs">
                          <span className="w-2 h-2 rounded-full shrink-0" style={{ background: est.color }} />
                          {est.etiqueta}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

    </div>
  );
}
