import { useState, useEffect } from 'react';
import { api, type Contrato } from '../lib/api';
import { formatEuro } from '../lib/format';
import cpvData from '../data/cpv.json';

const cpvMap = cpvData as Record<string, string>;

const TIPO_CONTRATO: Record<string, string> = {
  '1': 'Obras', '2': 'Servicios', '3': 'Suministros',
  '4': 'Concesión obras', '5': 'Concesión servicios', '7': 'Otros',
};

const ESTADOS: Record<string, { etiqueta: string; color: string }> = {
  ADJ:  { etiqueta: 'Adjudicada',    color: '#22c55e' },
  PUB:  { etiqueta: 'Publicada',     color: '#3b82f6' },
  EV:   { etiqueta: 'En evaluación', color: '#f59e0b' },
  RES:  { etiqueta: 'Resuelta',      color: '#6b7280' },
  ANUL: { etiqueta: 'Anulada',       color: '#ef4444' },
  DES:  { etiqueta: 'Desierta',      color: '#9ca3af' },
};

const DURACION_UNIDAD: Record<string, string> = {
  MES: 'meses', ANO: 'años', DIA: 'días',
};

function fmtFecha(s: string | null): string {
  if (!s) return '—';
  const [y, m, d] = s.split('-');
  const meses = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'];
  return `${parseInt(d)} de ${meses[parseInt(m) - 1]} de ${y}`;
}

function Skeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="space-y-2">
        <div className="h-3 bg-muted rounded w-32" />
        <div className="h-6 bg-muted rounded w-3/4" />
        <div className="h-4 bg-muted rounded w-full" />
        <div className="h-4 bg-muted rounded w-2/3" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {[...Array(4)].map((_, i) => <div key={i} className="border rounded-lg h-32 bg-muted/30" />)}
      </div>
    </div>
  );
}

export default function ContratoFicha({ id }: { id: string }) {
  const [contrato, setContrato] = useState<Contrato | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    api.contrato(id)
      .then(c => { setContrato(c); setLoading(false); })
      .catch(() => { setError(true); setLoading(false); });
  }, [id]);

  if (loading) return <Skeleton />;
  if (error || !contrato) return (
    <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
      No se ha encontrado el contrato. Comprueba que la API está activa.
    </div>
  );

  const est = ESTADOS[contrato.estado] ?? { etiqueta: contrato.estado, color: '#9ca3af' };
  const cpvs = contrato.codigos_cpv ?? [];

  /* contrato-ficha: vista completa de un contrato individual */
  return (
    <div className="contrato-ficha space-y-6">

      {/* contrato-header: número de expediente, chips de clasificación y enlace a PLACSP */}
      <div className="contrato-header flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <code className="text-xs font-mono text-muted-foreground">{contrato.num_expediente}</code>
          {/* contrato-badges: chips de tipo (licitación/menor), tipo de contrato, procedimiento y estado */}
          <div className="contrato-badges flex flex-wrap gap-1.5 my-2">
            <span className="contrato-badge text-xs border border-border rounded px-2 py-0.5 text-muted-foreground">
              {contrato.tipo === 'menores' ? 'Contrato menor' : 'Licitación'}
            </span>
            {TIPO_CONTRATO[contrato.tipo_contrato] && (
              <span className="contrato-badge text-xs border border-border rounded px-2 py-0.5 text-muted-foreground">
                {TIPO_CONTRATO[contrato.tipo_contrato]}
              </span>
            )}
            {contrato.tipo_procedimiento && (
              <span className="contrato-badge text-xs border border-border rounded px-2 py-0.5 text-muted-foreground">
                {contrato.tipo_procedimiento}
              </span>
            )}
            <span className="contrato-badge inline-flex items-center gap-1.5 text-xs border border-border rounded px-2 py-0.5">
              <span className="w-2 h-2 rounded-full shrink-0" style={{ background: est.color }} />
              {est.etiqueta}
            </span>
          </div>
          <h1 className="text-xl font-semibold tracking-tight leading-snug">
            {contrato.titulo || contrato.objeto || '(sin título)'}
          </h1>
          {contrato.objeto && contrato.objeto !== contrato.titulo && (
            <p className="mt-2 text-sm text-muted-foreground leading-relaxed">{contrato.objeto}</p>
          )}
        </div>
        {contrato.url_placsp && (
          <a
            href={contrato.url_placsp}
            target="_blank"
            rel="noopener noreferrer"
            className="contrato-placsp-link shrink-0 text-sm border border-border rounded px-3 py-1.5 hover:bg-muted transition-colors"
          >
            Ver en PLACSP ↗
          </a>
        )}
      </div>

      {/* contrato-detalles: cuadrícula con tarjetas de importe, organismo, fechas y adjudicatario */}
      <div className="contrato-detalles grid grid-cols-1 md:grid-cols-2 gap-4">

        {/* detalle-importe: presupuesto base y precio de adjudicación sin IVA */}
        <div className="detalle-card detalle-importe border rounded-lg p-4 space-y-3">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Importe</p>
          <div className="flex gap-6 flex-wrap">
            <div>
              <p className="text-xs text-muted-foreground">Adjudicado (sin IVA)</p>
              <p className="text-2xl font-bold tracking-tight mt-0.5">
                {formatEuro(contrato.importe_adjudicacion_sin_iva)}
              </p>
            </div>
            {contrato.presupuesto_sin_iva != null && (
              <div>
                <p className="text-xs text-muted-foreground">Presupuesto base</p>
                <p className="text-lg font-semibold text-muted-foreground mt-0.5">
                  {formatEuro(contrato.presupuesto_sin_iva)}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* detalle-organo: nombre, NIF y enlace al perfil del organismo contratante */}
        <div className="detalle-card detalle-organo border rounded-lg p-4 space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Órgano contratante</p>
          <p className="font-medium">{contrato.organo_nombre}</p>
          {contrato.organo_nif && (
            <p className="text-xs font-mono text-muted-foreground">{contrato.organo_nif}</p>
          )}
          {contrato.organo_id_plataforma && (
            <a
              href={`/organismos/${encodeURIComponent(contrato.organo_id_plataforma)}`}
              className="block text-xs text-muted-foreground hover:underline mt-1"
            >
              Ver ficha del organismo →
            </a>
          )}
        </div>

        {/* detalle-adjudicatario: empresa o persona adjudicada, NIF y enlace a su perfil */}
        {contrato.adjudicatario_nombre && (
          <div className="detalle-card detalle-adjudicatario border rounded-lg p-4 space-y-2">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Adjudicatario</p>
            <p className="font-medium">{contrato.adjudicatario_nombre}</p>
            {contrato.adjudicatario_nif && (
              <p className="text-xs font-mono text-muted-foreground">NIF {contrato.adjudicatario_nif}</p>
            )}
            {contrato.adjudicado_pyme && (
              <span className="inline-block text-xs bg-green-50 text-green-700 border border-green-200 rounded px-2 py-0.5">PYME</span>
            )}
            {contrato.adjudicatario_id && (
              <a
                href={`/adjudicatarios/${encodeURIComponent(contrato.adjudicatario_id)}`}
                className="block text-xs text-muted-foreground hover:underline mt-1"
              >
                Ver ficha de la empresa →
              </a>
            )}
          </div>
        )}

        {/* detalle-expediente: fechas de publicación, adjudicación y formalización */}
        <div className="detalle-card detalle-expediente border rounded-lg p-4 space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Expediente</p>
          <table className="w-full text-sm">
            <tbody>
              {contrato.lugar_ejecucion && (
                <tr className="border-b border-border/50">
                  <td className="py-1.5 pr-4 text-muted-foreground w-2/5">Lugar</td>
                  <td className="py-1.5">{contrato.lugar_ejecucion}</td>
                </tr>
              )}
              {contrato.duracion_valor != null && (
                <tr className="border-b border-border/50">
                  <td className="py-1.5 pr-4 text-muted-foreground">Duración</td>
                  <td className="py-1.5">{contrato.duracion_valor} {DURACION_UNIDAD[contrato.duracion_unidad ?? ''] ?? contrato.duracion_unidad}</td>
                </tr>
              )}
              {contrato.num_ofertas_recibidas != null && (
                <tr className="border-b border-border/50">
                  <td className="py-1.5 pr-4 text-muted-foreground">Ofertas</td>
                  <td className="py-1.5">{contrato.num_ofertas_recibidas === 0 ? 'Sin ofertas' : contrato.num_ofertas_recibidas}</td>
                </tr>
              )}
              <tr className="border-b border-border/50">
                <td className="py-1.5 pr-4 text-muted-foreground">Publicación</td>
                <td className="py-1.5">{fmtFecha(contrato.fecha_publicacion)}</td>
              </tr>
              <tr className="border-b border-border/50">
                <td className="py-1.5 pr-4 text-muted-foreground">Adjudicación</td>
                {/* si fecha_adjudicacion es null pero el contrato ya está resuelto/adjudicado, usamos fecha_actualizacion como aproximación */}
                <td className="py-1.5">{fmtFecha(contrato.fecha_adjudicacion ?? (['RES', 'ADJ'].includes(contrato.estado) ? contrato.fecha_actualizacion : null))}</td>
              </tr>
              <tr>
                <td className="py-1.5 pr-4 text-muted-foreground">Formalización</td>
                <td className="py-1.5">{fmtFecha(contrato.fecha_formalizacion)}</td>
              </tr>
            </tbody>
          </table>
        </div>

      </div>

      {/* detalle-cpv: códigos CPV del contrato con su descripción */}
      {cpvs.length > 0 && (
        <div className="detalle-card detalle-cpv border rounded-lg p-4 space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Código CPV</p>
          <div className="flex flex-col gap-2">
            {cpvs.map(codigo => (
              <div key={codigo} className="cpv-item">
                <code className="text-xs text-muted-foreground">{codigo}</code>
                {cpvMap[codigo] && <p className="text-sm mt-0.5">{cpvMap[codigo]}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  );
}
