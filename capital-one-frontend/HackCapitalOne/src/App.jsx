import React, { useEffect, useState } from 'react';
import {
  Bell, ArrowUpRight, ArrowDownRight, PiggyBank, ChevronRight, Loader2, AlertTriangle,
} from 'lucide-react';
import { getPredicciones, getKpis, getRecomendaciones, getGraficaUrl } from './services/api';

const WEEKDAY_LABELS = ['do.', 'lu.', 'ma.', 'mi.', 'ju.', 'vi.', 'sá.'];

const currency = (value) =>
  (value ?? 0).toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

function monthLabel(year, month) {
  return new Date(year, month - 1, 1).toLocaleDateString('es-ES', { month: 'long', year: 'numeric' });
}

/** Arma la cuadrícula de 7 columnas para el calendario, rellenando los
 *  huecos de inicio/fin de mes con celdas vacías para alinear los días
 *  de la semana. */
function buildGridCells(dias) {
  if (!dias || dias.length === 0) return [];
  const leading = Array(dias[0].day_of_week).fill(null);
  const cells = [...leading, ...dias];
  const trailing = Array((7 - (cells.length % 7)) % 7).fill(null);
  return [...cells, ...trailing];
}

function describeDay(dia, mesLabel) {
  if (!dia) return 'Selecciona un día del calendario para ver su detalle.';
  const monto = currency(dia.net_flow);
  return dia.tipo === 'real'
    ? `Día ${dia.day} de ${mesLabel}: Registro histórico procesado. Flujo neto real: ${monto}.`
    : `Día ${dia.day} de ${mesLabel}: Proyección predictiva activa. Flujo neto estimado por el modelo: ${monto}.`;
}

function getButtonStyle(tipo) {
  switch (tipo) {
    case 'danger': return 'bg-[#D01C1F] hover:bg-red-800 text-white';
    case 'warning': return 'bg-amber-600 hover:bg-amber-700 text-white';
    default: return 'bg-[#0D233A] hover:bg-blue-950 text-white';
  }
}

export default function App() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [calendario, setCalendario] = useState(null);
  const [kpis, setKpis] = useState(null);
  const [recomendaciones, setRecomendaciones] = useState([]);
  const [selectedLapso, setSelectedLapso] = useState(null);
  const [selectedDay, setSelectedDay] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [pred, kpisData, recos] = await Promise.all([
          getPredicciones(),
          getKpis(),
          getRecomendaciones(),
        ]);
        if (cancelled) return;
        setCalendario(pred);
        setKpis(kpisData);
        setRecomendaciones(recos);
        setSelectedDay(pred.dias.find((d) => d.is_today) ?? pred.dias.at(-1) ?? null);
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#F7F9FB] flex flex-col items-center justify-center gap-3 text-[#0D233A]">
        <Loader2 className="w-8 h-8 animate-spin" />
        <p className="text-sm font-bold">Conectando con el motor de liquidez…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-[#F7F9FB] flex flex-col items-center justify-center gap-3 text-center px-6">
        <AlertTriangle className="w-10 h-10 text-[#D01C1F]" />
        <p className="text-sm font-bold text-[#0D233A]">No se pudo cargar la información del backend</p>
        <p className="text-xs text-slate-500 max-w-md">{error}</p>
        <p className="text-xs text-slate-400">
          Verifica que la API esté corriendo (uvicorn app.main:app --port 8000) en capital-one-backend.
        </p>
      </div>
    );
  }

  const mesLabel = monthLabel(calendario.year, calendario.month);
  const gridCells = buildGridCells(calendario.dias);

  return (
    <div className="min-h-screen bg-[#F7F9FB] text-[#0D233A] font-sans antialiased flex flex-col selection:bg-[#0D233A] selection:text-white">

      {/* Top Navbar Capital One Style */}
      <header className="bg-[#0D233A] text-white px-8 py-4 flex items-center justify-between shadow-xl relative overflow-hidden border-b-4 border-[#D01C1F]">
        <div className="absolute top-0 right-0 w-[500px] h-full opacity-15 bg-gradient-to-l from-[#D01C1F] via-[#D01C1F]/40 to-transparent pointer-events-none transform skew-x-12"></div>

        <div className="flex items-center space-x-4 z-10">
          <div className="flex items-baseline font-black tracking-tight text-3xl">
            <span className="text-white italic">Capital</span>
            <span className="text-[#D01C1F] italic ml-1">PyMe</span>
          </div>
          <span className="bg-[#D01C1F]/20 text-red-200 border border-[#D01C1F]/40 text-[10px] font-bold uppercase px-2.5 py-1 rounded tracking-wider hidden sm:inline">
            Liquidity Engine
          </span>
        </div>

        <div className="flex items-center space-x-5 z-10">
          <div className="relative cursor-pointer bg-white/10 p-2 rounded-full hover:bg-white/20 transition-colors">
            <Bell className="w-5 h-5 text-white" />
            <span className="absolute -top-1 -right-1 bg-[#D01C1F] text-white text-[10px] w-4 h-4 rounded-full flex items-center justify-center font-bold shadow-sm">1</span>
          </div>
          <div className="flex items-center space-x-3 border-l border-white/20 pl-4">
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-[#D01C1F] to-red-700 text-white flex items-center justify-center font-black text-xs shadow-md border border-white/20">
              CF
            </div>
            <div className="hidden md:block text-left">
              <p className="text-xs font-bold text-white leading-tight">Cafetería Don Pancho</p>
              <p className="text-[10px] text-red-300 font-medium">Cuenta Comercial Verificada</p>
            </div>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-8 grid grid-cols-1 lg:grid-cols-3 gap-8">

        {/* Columna Principal: Calendario Estilo Tradicional */}
        <div className="lg:col-span-2 space-y-6">

          {/* Tarjetas KPI Superiores */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white p-5 rounded-xl shadow-sm border-t-4 border-t-[#0D233A] border-x border-b border-slate-200/80">
              <p className="text-[11px] font-extrabold text-slate-400 uppercase tracking-wider">Liquidez Actual (Real)</p>
              <h3 className="text-2xl font-black text-[#0D233A] mt-1">{currency(kpis.liquidez_actual)}</h3>
              <div className="flex items-center text-emerald-600 text-xs font-bold mt-2 bg-emerald-50 w-fit px-2 py-0.5 rounded">
                <ArrowUpRight className="w-3.5 h-3.5 mr-1" /> Cierre al {kpis.fecha_corte}
              </div>
            </div>

            <div className="bg-white p-5 rounded-xl shadow-sm border-t-4 border-t-[#D01C1F] border-x border-b border-slate-200/80">
              <p className="text-[11px] font-extrabold text-slate-400 uppercase tracking-wider">Proyección 30 Días</p>
              <h3 className="text-2xl font-black text-[#D01C1F] mt-1">{currency(kpis.proyeccion_30_dias)}</h3>
              <span className="inline-flex items-center gap-1 bg-red-50 text-[#D01C1F] text-[10px] font-bold px-2 py-0.5 rounded mt-2 border border-red-200">
                {kpis.variacion_pct_30_dias >= 0
                  ? <ArrowUpRight className="w-3 h-3" />
                  : <ArrowDownRight className="w-3 h-3" />}
                {kpis.variacion_pct_30_dias >= 0 ? '+' : ''}{kpis.variacion_pct_30_dias}% vs. hoy (modelo)
              </span>
            </div>

            <div className="bg-white p-5 rounded-xl shadow-sm border-t-4 border-t-[#0D233A] border-x border-b border-slate-200/80">
              <p className="text-[11px] font-extrabold text-slate-400 uppercase tracking-wider">Reserva Sugerida</p>
              <h3 className="text-2xl font-black text-[#0D233A] mt-1">{currency(kpis.reserva_sugerida)}</h3>
              <span className="inline-block bg-blue-50 text-[#0D233A] text-[10px] font-bold px-2 py-0.5 rounded mt-2 border border-blue-200">
                💡 Colchón sugerido por el modelo (RMSE {kpis.rmse_modelo})
              </span>
            </div>
          </div>

          {/* Calendario Estilo Cuadrícula Tradicional */}
          <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200/80 relative overflow-hidden">
            <div className="absolute top-0 left-0 w-1.5 h-full bg-[#0D233A]"></div>

            {/* Cabecera del Calendario */}
            <div className="flex justify-between items-center mb-6 pl-2">
              <div>
                <h4 className="font-black text-[#0D233A] text-lg capitalize">{mesLabel}</h4>
                <p className="text-xs text-slate-400">Haz clic en cualquier día para consultar su estado financiero</p>
              </div>
              <div className="flex items-center space-x-4 text-xs">
                <span className="flex items-center font-bold text-slate-600"><span className="w-2.5 h-2.5 rounded-full bg-slate-400 mr-1.5"></span> Histórico (Real)</span>
                <span className="flex items-center font-bold text-[#0D233A]"><span className="w-2.5 h-2.5 rounded-full bg-[#0D233A] mr-1.5"></span> Proyección</span>
              </div>
            </div>

            {/* Días de la semana */}
            <div className="grid grid-cols-7 gap-2 text-center font-bold text-xs text-slate-400 mb-2 pb-2 border-b border-slate-100">
              {WEEKDAY_LABELS.map((label) => <div key={label}>{label}</div>)}
            </div>

            {/* Cuadrícula de los días */}
            <div className="grid grid-cols-7 gap-2">
              {gridCells.map((dia, index) => {
                if (!dia) {
                  return <div key={`blank-${index}`} className="h-12" />;
                }
                const isToday = dia.is_today;
                const isPast = dia.tipo === 'real' && !isToday;
                const isSelected = selectedDay?.date === dia.date;

                return (
                  <button
                    key={dia.date}
                    onClick={() => setSelectedDay(dia)}
                    className={`h-12 rounded-lg flex flex-col items-center justify-center relative transition-all text-xs font-bold ${
                      isToday
                        ? 'bg-[#0D233A] text-white ring-2 ring-[#D01C1F] shadow-md'
                        : isPast
                          ? 'bg-slate-100 text-slate-700 hover:bg-slate-200 border border-slate-200'
                          : 'bg-blue-50/60 text-[#0D233A] hover:bg-blue-100 border border-blue-200'
                    } ${isSelected && !isToday ? 'ring-2 ring-[#0D233A]' : ''}`}
                  >
                    <span>{dia.day}</span>
                    <span className={`w-1 h-1 rounded-full mt-1 ${dia.tipo === 'real' ? 'bg-slate-400' : 'bg-[#D01C1F]'}`}></span>
                  </button>
                );
              })}
            </div>

            {/* Panel inferior de información del día seleccionado */}
            <div className="mt-6 p-4 bg-slate-50 rounded-lg border border-slate-200 flex flex-col sm:flex-row justify-between items-start sm:items-center">
              <div>
                <span className="text-[10px] font-black uppercase tracking-wider text-[#0D233A]">
                  Estado del Día {selectedDay?.day ?? '—'} ({selectedDay?.tipo === 'real' ? 'Dato Histórico Real' : 'Proyección Predictiva'})
                </span>
                <p className="text-xs text-slate-700 mt-1 font-medium">
                  {describeDay(selectedDay, mesLabel)}
                </p>
              </div>
            </div>

          </div>

          {/* Gráfica de tendencia de liquidez (histórico + proyección del modelo) */}
          <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200/80">
            <img
              src={getGraficaUrl()}
              alt="Tendencia de liquidez: histórico real y proyección del modelo"
              className="w-full h-auto rounded-lg"
            />
          </div>

        </div>

        {/* Columna Lateral: Recomendaciones por Lapsos de Tiempo */}
        <div className="space-y-6">
          <div className="bg-white p-6 rounded-xl shadow-sm border-t-4 border-t-[#0D233A] border-x border-b border-slate-200/80 flex flex-col h-full">
            <div className="flex justify-between items-center mb-4 pb-3 border-b border-slate-100">
              <h4 className="font-black text-[#0D233A] text-base flex items-center">
                <PiggyBank className="w-5 h-5 mr-2 text-[#0D233A]" /> Recomendaciones por Lapsos
              </h4>
              <span className="text-[10px] font-extrabold bg-[#0D233A] text-white px-2.5 py-0.5 rounded-full shadow-sm">
                Estrategia Mensual
              </span>
            </div>

            <p className="text-xs text-slate-500 mb-4 font-medium">
              Selecciona un lapso estratégico del mes para consultar las optimizaciones de costos fijos y reservas:
            </p>

            {/* Listado de Lapsos */}
            <div className="space-y-3 flex-1">
              {recomendaciones.map((lapso) => {
                const isSelected = selectedLapso?.id === lapso.id;
                return (
                  <div
                    key={lapso.id}
                    onClick={() => setSelectedLapso(lapso)}
                    className={`p-3.5 rounded-lg border cursor-pointer transition-all ${
                      isSelected ? 'border-[#0D233A] bg-blue-50/40 ring-1 ring-[#0D233A]' : 'border-slate-200 bg-white hover:border-slate-300'
                    }`}
                  >
                    <div className="flex justify-between items-center mb-1">
                      <span className={`text-[10px] font-black px-2 py-0.5 rounded ${lapso.badgeColor}`}>
                        {lapso.rango}
                      </span>
                      <ChevronRight className={`w-4 h-4 text-slate-400 transition-transform ${isSelected ? 'rotate-90 text-[#0D233A]' : ''}`} />
                    </div>
                    <h5 className="font-bold text-xs text-[#0D233A] mt-1">{lapso.titulo}</h5>
                  </div>
                );
              })}
            </div>

            {/* Panel de Detalle del Lapso Seleccionado */}
            {selectedLapso ? (
              <div className="mt-4 p-4 bg-slate-50 rounded-lg border border-slate-200 animate-fade-in">
                <span className="text-[10px] font-black uppercase tracking-wider text-[#D01C1F]">
                  {selectedLapso.rango}
                </span>
                <p className="text-xs text-slate-700 mt-1.5 font-medium leading-relaxed">
                  {selectedLapso.mensaje}
                </p>
                <button className={`mt-3 text-xs font-black px-3.5 py-2 rounded-lg flex items-center transition-colors shadow-sm ${getButtonStyle(selectedLapso.tipo)}`}>
                  {selectedLapso.accion} <ChevronRight className="w-3.5 h-3.5 ml-1" />
                </button>
              </div>
            ) : (
              <div className="mt-4 p-4 bg-slate-50 rounded-lg border border-slate-200 text-center">
                <p className="text-xs text-slate-400 font-medium">
                  Haz clic en cualquiera de los lapsos superiores para ver la recomendación táctica del motor de liquidez.
                </p>
              </div>
            )}

            {/* Sello de Marca Inferior */}
            <div className="mt-6 pt-4 border-t border-slate-100 text-center">
              <p className="text-[10px] font-black text-[#0D233A] uppercase tracking-widest">
                Capital One • Business Intelligence
              </p>
            </div>
          </div>
        </div>

      </main>
    </div>
  );
}
