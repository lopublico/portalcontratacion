
const BASE = import.meta.env.PUBLIC_API_URL ?? 'http://localhost:8000';

async function get<T>(path: string, params?: Record<string, string | number | boolean | undefined>): Promise<T> {
  const url = new URL(BASE + path);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, String(v));
    });
  }
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  return res.json();
}

// ---------- tipos ----------

export interface Contrato {
  tipo: string;
  num_expediente: string;
  titulo: string;
  objeto: string;
  estado: string;
  organo_nombre: string;
  organo_nif: string;
  organo_id_plataforma: string;
  tipo_contrato: string;
  tipo_procedimiento: string;
  presupuesto_sin_iva: number | null;
  importe_adjudicacion_sin_iva: number | null;
  adjudicatario_nombre: string | null;
  adjudicatario_nif: string | null;
  adjudicatario_id: string | null;
  adjudicado_pyme: boolean | null;
  fecha_adjudicacion: string | null;
  fecha_actualizacion: string | null;
  fecha_publicacion: string | null;
  fecha_formalizacion: string | null;
  fecha_inicio: string | null;
  fecha_fin: string | null;
  codigos_cpv: string[] | null;
  id_atom: string | null;
  url_placsp: string | null;
  lugar_ejecucion: string | null;
  duracion_valor: number | null;
  duracion_unidad: string | null;
  num_ofertas_recibidas: number | null;
}

export interface PaginaContratos {
  total: number;
  pagina: number;
  paginas: number;
  por_pagina: number;
  resultados: Contrato[];
}

export interface FiltrosContratos {
  tipo?: string;
  q?: string;
  organismo_id?: string;
  organismo_q?: string;
  adjudicatario_nif?: string;
  adjudicatario_q?: string;
  estado?: string;
  tipo_contrato?: string;
  cpv_sector?: string;
  tipo_procedimiento?: string;
  anno?: number;
  importe_min?: number;
  importe_max?: number;
  fecha_desde?: string;
  fecha_hasta?: string;
  orden?: string;
  pagina?: number;
  por_pagina?: number;
}

export interface SectorCpv {
  division: string;
  num_contratos: number;
}

export interface EstadisticasGenerales {
  total: number;
  por_tipo: { tipo: string; num_contratos: number; total_adjudicado: number }[];
  pyme: { num_contratos: number; total_adjudicado: number };
  top_organismos: { organo_nombre: string; organo_id_plataforma: string; num_contratos: number; total_adjudicado: number }[];
  top_adjudicatarios: { adjudicatario_nombre: string; adjudicatario_id: string | null; adjudicatario_nif: string | null; num_contratos: number; total_adjudicado: number }[];
}

export interface PuntoAnual {
  anno: number;
  tipo: string;
  num_contratos: number;
  total_adjudicado: number;
}

export interface PuntoMensual {
  mes: string;
  tipo: string;
  num_contratos: number;
  total_adjudicado: number;
}

export interface PerfilOrganismo {
  organo_id_plataforma: string;
  organo_nombre: string;
  organo_nif: string;
  organo_tipo: string;
  organo_ciudad: string;
  organo_perfil_url: string;
  num_contratos: number;
  total_adjudicado: number;
  num_adjudicatarios: number;
  importe_medio: number;
  primer_contrato: string;
  ultimo_contrato: string;
  por_tipo: { tipo: string; num_contratos: number; total_adjudicado: number }[];
  por_anno: { anno: number; num_contratos: number; total_adjudicado: number }[];
  por_mes: { mes: string; num_contratos: number; total_adjudicado: number }[];
  principales_adjudicatarios: { adjudicatario_nombre: string; adjudicatario_nif: string; num_contratos: number; total_adjudicado: number }[];
  ultimos_contratos: Contrato[];
}

export interface PerfilAdjudicatario {
  adjudicatario_nombre: string;
  adjudicatario_id: string;
  adjudicatario_nif: string;
  adjudicatario_pais: string;
  num_contratos: number;
  total_adjudicado: number;
  num_organismos: number;
  importe_medio: number;
  primer_contrato: string;
  ultimo_contrato: string;
  por_tipo: { tipo: string; num_contratos: number; total_adjudicado: number }[];
  por_anno: { anno: number; num_contratos: number; total_adjudicado: number }[];
  por_mes: { mes: string; num_contratos: number; total_adjudicado: number }[];
  principales_organismos: { organo_nombre: string; organo_id_plataforma: string; num_contratos: number; total_adjudicado: number }[];
}

// ---------- helpers ----------

// extrae el sufijo numérico del atom:id — ese número es globalmente único y es lo que usamos como ID en las URLs del portal
export function atomNum(id_atom: string | null | undefined): string | null {
  if (!id_atom) return null;
  const m = id_atom.match(/\/([^/]+)$/);
  return m ? m[1] : null;
}

// ---------- funciones ----------

export const api = {
  estadisticas: () => get<EstadisticasGenerales>('/estadisticas'),

  estadisticasAnual: (tipo?: string) =>
    get<PuntoAnual[]>('/estadisticas/anual', { tipo }),

  estadisticasMensual: (tipo?: string) =>
    get<PuntoMensual[]>('/estadisticas/mensual', { tipo }),

  contratos: (filtros: FiltrosContratos) =>
    get<PaginaContratos>('/contratos', filtros as Record<string, string | number | boolean | undefined>),

  contrato: (atom_num: string) =>
    get<Contrato>(`/contratos/atom/${encodeURIComponent(atom_num)}`),

  organismos: (q?: string, pagina = 1, por_pagina = 20) =>
    get('/organismos', { q, pagina, por_pagina }),

  organismo: (id: string) =>
    get<PerfilOrganismo>(`/organismos/${encodeURIComponent(id)}`),

  adjudicatarios: (q?: string, pagina = 1, por_pagina = 20) =>
    get('/adjudicatarios', { q, pagina, por_pagina }),

  adjudicatario: (id: string) =>
    get<PerfilAdjudicatario>(`/adjudicatarios/${encodeURIComponent(id)}`),

  sectoresCpv: () => get<SectorCpv[]>('/estadisticas/sectores-cpv'),

  tipoContrato: () => get<{ tipo_contrato: string; num_contratos: number; total_adjudicado: number | null }[]>('/estadisticas/tipo-contrato'),

};
