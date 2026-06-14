import { useState, useEffect, useCallback, useMemo } from 'react';
import { api } from '../lib/api';
import { formatEuro } from '../lib/format';

type Organismo = {
  organo_id_plataforma: string;
  organo_nombre: string;
  organo_nif: string | null;
  organo_tipo: string | null;
  num_contratos: number;
  total_adjudicado: number | null;
  primer_contrato: string | null;
};

type Pagina = {
  total: number;
  pagina: number;
  paginas: number;
  resultados: Organismo[];
};

const POR_PAGINA = 25;

function yearDesde(val: string | null): string {
  if (!val) return '—';
  const y = parseInt(String(val).slice(0, 4), 10);
  return y >= 2000 && y <= 2099 ? String(y) : '—';
}

function Skeleton() {
  return (
    <div className="animate-pulse space-y-2">
      {[...Array(8)].map((_, i) => (
        <div key={i} className="h-10 bg-muted/40 rounded" />
      ))}
    </div>
  );
}

export default function OrganismosTabla() {
  const [datos, setDatos] = useState<Pagina | null>(null);
  const [loading, setLoading] = useState(true);
  // inputQ es el valor del input mientras el usuario escribe; q es el que dispara la búsqueda (al pulsar Enter o el botón)
  const [q, setQ] = useState('');
  const [inputQ, setInputQ] = useState('');
  const [pagina, setPagina] = useState(1);
  // la ordenación por importe se hace en cliente sobre la página actual — no vale la pena una petición extra al servidor para esto
  const [importeDir, setImporteDir] = useState<'asc' | 'desc' | null>(null);

  const cargar = useCallback(() => {
    setLoading(true);
    api.organismos(q || undefined, pagina, POR_PAGINA)
      .then(d => { setDatos(d as Pagina); setLoading(false); })
      .catch(() => setLoading(false));
  }, [q, pagina]);

  useEffect(() => { cargar(); }, [cargar]);

  function buscar() {
    setQ(inputQ);
    setPagina(1);
  }

  function toggleImporte() {
    setImporteDir(d => d === 'desc' ? 'asc' : 'desc');
  }

  const resultados = useMemo(() => {
    const base = datos?.resultados ?? [];
    if (!importeDir) return base;
    return [...base].sort((a, b) => {
      const va = a.total_adjudicado ?? -Infinity;
      const vb = b.total_adjudicado ?? -Infinity;
      return importeDir === 'desc' ? vb - va : va - vb;
    });
  }, [datos, importeDir]);

  return (
    <div className="organismos-tabla space-y-4">

      {/* buscador */}
      <div className="tabla-busqueda flex gap-2">
        <input
          type="text"
          value={inputQ}
          onChange={e => setInputQ(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && buscar()}
          placeholder="Buscar organismo…"
          className="h-9 rounded-md border border-input bg-transparent px-3 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-ring w-72"
        />
        <button
          onClick={buscar}
          className="h-9 px-4 rounded-md border border-input text-sm hover:bg-muted transition-colors"
        >
          Buscar
        </button>
      </div>

      {datos && (
        <p className="tabla-total text-xs text-muted-foreground">
          {datos.total.toLocaleString('es-ES')} organismos
          {q && ` · filtrando por «${q}»`}
        </p>
      )}

      {/* tabla */}
      {loading ? <Skeleton /> : (
        <div className="tabla-contenedor rounded-md border overflow-x-auto">
          <table className="organismos-tabla-datos w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/40">
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">Organismo</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Contratos</th>
                <th
                  className="px-4 py-3 text-right font-medium text-muted-foreground cursor-pointer select-none hover:text-foreground transition-colors"
                  onClick={toggleImporte}
                >
                  Importe total {importeDir === 'desc' ? '↓' : importeDir === 'asc' ? '↑' : <span className="opacity-25">↕</span>}
                </th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">Desde</th>
              </tr>
            </thead>
            <tbody>
              {resultados.map((o, i) => (
                <tr key={o.organo_id_plataforma + i} className={i % 2 === 1 ? 'organismo-row bg-muted/20' : 'organismo-row'}>
                  <td className="px-4 py-3">
                    <a
                      href={`/organismos/${encodeURIComponent(o.organo_id_plataforma)}`}
                      className="font-medium hover:underline"
                    >
                      {o.organo_nombre}
                    </a>
                    {o.organo_nif && (
                      <span className="block text-xs text-muted-foreground/60">{o.organo_nif}</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums font-mono text-muted-foreground">
                    {o.num_contratos.toLocaleString('es-ES')}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums font-mono">
                    {formatEuro(o.total_adjudicado)}
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {yearDesde(o.primer_contrato)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* paginación */}
      {datos && datos.paginas > 1 && (
        <div className="tabla-paginacion flex items-center justify-between text-sm">
          <button
            onClick={() => setPagina(p => Math.max(1, p - 1))}
            disabled={pagina === 1}
            className="px-3 py-1.5 rounded border border-input disabled:opacity-40 hover:bg-muted transition-colors"
          >
            ← Anterior
          </button>
          <span className="text-muted-foreground">
            Página {pagina} de {datos.paginas.toLocaleString('es-ES')}
          </span>
          <button
            onClick={() => setPagina(p => Math.min(datos.paginas, p + 1))}
            disabled={pagina === datos.paginas}
            className="px-3 py-1.5 rounded border border-input disabled:opacity-40 hover:bg-muted transition-colors"
          >
            Siguiente →
          </button>
        </div>
      )}

    </div>
  );
}
