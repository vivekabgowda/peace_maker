'use client';

import { useQuery } from '@tanstack/react-query';
import {
  ColorType,
  CrosshairMode,
  createChart,
  type CandlestickData,
  type HistogramData,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type MouseEventParams,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts';
import { useEffect, useMemo, useRef, useState } from 'react';

import { Card } from '@/components/ui/Card';
import { getCandles, getInstruments, getSymbolTrades, type Candle } from '@/features/charts/api';
import type { JournalEntry } from '@/features/journal/api';
import { ema } from '@/features/charts/indicators';
import { cn, formatINR } from '@/lib/utils';

// Chart colours drawn from the dark theme (tailwind.config.ts).
const C = {
  bg: '#161b22',
  grid: '#1c2230',
  border: '#2a3140',
  text: '#8b98a9',
  gain: '#26a269',
  loss: '#e5484d',
  accent: '#1f6feb',
  caution: '#e3b341',
};

const TIMEFRAMES: { label: string; tf: string }[] = [
  { label: '1m', tf: '1m' },
  { label: '5m', tf: '5m' },
  { label: '15m', tf: '15m' },
  { label: '1h', tf: '1h' },
  { label: '1D', tf: '1d' },
];

const toTime = (iso: string): UTCTimestamp => Math.floor(Date.parse(iso) / 1000) as UTCTimestamp;

interface Legend {
  o: number;
  h: number;
  l: number;
  c: number;
  vol: number;
  ema20: number | null;
  ema50: number | null;
  up: boolean;
}

function legendFromCandle(
  candles: Candle[],
  e20: (number | null)[],
  e50: (number | null)[],
): Legend | null {
  const last = candles.at(-1);
  if (!last) return null;
  return {
    o: last.open,
    h: last.high,
    l: last.low,
    c: last.close,
    vol: last.volume,
    ema20: e20.at(-1) ?? null,
    ema50: e50.at(-1) ?? null,
    up: last.close >= last.open,
  };
}

function LegendRow({ legend, symbol, tf }: { legend: Legend | null; symbol: string; tf: string }) {
  if (!legend) return null;
  const num = (v: number) =>
    v.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const chg = legend.o ? ((legend.c - legend.o) / legend.o) * 100 : 0;
  return (
    <div className="pointer-events-none absolute left-3 top-3 z-10 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
      <span className="font-semibold text-content">
        {symbol} · {tf}
      </span>
      <span className="text-content-muted">
        O <span className="tabular text-content">{num(legend.o)}</span>
      </span>
      <span className="text-content-muted">
        H <span className="tabular text-content">{num(legend.h)}</span>
      </span>
      <span className="text-content-muted">
        L <span className="tabular text-content">{num(legend.l)}</span>
      </span>
      <span className="text-content-muted">
        C{' '}
        <span className={cn('tabular', legend.up ? 'text-gain' : 'text-loss')}>
          {num(legend.c)}
        </span>
      </span>
      <span className={cn('tabular', chg >= 0 ? 'text-gain' : 'text-loss')}>
        {chg >= 0 ? '+' : ''}
        {chg.toFixed(2)}%
      </span>
      <span className="text-content-muted">
        Vol <span className="tabular text-content">{legend.vol.toLocaleString('en-IN')}</span>
      </span>
      {legend.ema20 != null ? (
        <span style={{ color: C.accent }}>EMA20 {num(legend.ema20)}</span>
      ) : null}
      {legend.ema50 != null ? (
        <span style={{ color: C.caution }}>EMA50 {num(legend.ema50)}</span>
      ) : null}
    </div>
  );
}

function TradeDetail({ trade, onClose }: { trade: JournalEntry; onClose: () => void }) {
  const rows: [string, string, string?][] = [
    ['Direction', trade.direction, trade.direction === 'long' ? 'text-gain' : 'text-loss'],
    ['Entry', `${trade.entry_price} · ${new Date(trade.entry_ts).toLocaleString('en-IN')}`],
    ['Exit', `${trade.exit_price} · ${new Date(trade.exit_ts).toLocaleString('en-IN')}`],
    ['P&L', formatINR(trade.net_pnl), trade.net_pnl >= 0 ? 'text-gain' : 'text-loss'],
    ['R multiple', trade.r_multiple.toFixed(2), trade.r_multiple >= 0 ? 'text-gain' : 'text-loss'],
    ['Strategy', trade.strategy_key ?? '—'],
    ['Exit reason', trade.exit_reason ?? '—'],
  ];
  return (
    <Card className="relative">
      <button
        type="button"
        onClick={onClose}
        className="absolute right-3 top-3 text-xs text-content-muted hover:text-content"
      >
        ✕
      </button>
      <h3 className="mb-3 text-sm font-semibold text-content">
        {trade.symbol} trade #{trade.id}
      </h3>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs sm:grid-cols-3">
        {rows.map(([label, value, tone]) => (
          <div key={label}>
            <dt className="text-content-muted">{label}</dt>
            <dd className={cn('tabular mt-0.5 capitalize text-content', tone)}>{value}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}

export function ChartView() {
  const [symbol, setSymbol] = useState<string | null>(null);
  const [tf, setTf] = useState('5m');
  const [legend, setLegend] = useState<Legend | null>(null);
  const [selectedTradeId, setSelectedTradeId] = useState<number | null>(null);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volumeRef = useRef<ISeriesApi<'Histogram'> | null>(null);
  const ema20Ref = useRef<ISeriesApi<'Line'> | null>(null);
  const ema50Ref = useRef<ISeriesApi<'Line'> | null>(null);
  const defaultLegendRef = useRef<Legend | null>(null);
  const tradeMetaRef = useRef<{ time: number; tradeId: number }[]>([]);
  const toleranceRef = useRef<number>(0);

  const instrumentsQuery = useQuery({ queryKey: ['chart-instruments'], queryFn: getInstruments });

  // Pick a sensible default symbol once instruments load.
  useEffect(() => {
    if (symbol || !instrumentsQuery.data?.length) return;
    const preferred = instrumentsQuery.data.find((i) => i.symbol === 'NIFTY');
    setSymbol(preferred?.symbol ?? instrumentsQuery.data[0]?.symbol ?? null);
  }, [instrumentsQuery.data, symbol]);

  const candlesQuery = useQuery({
    queryKey: ['chart-candles', symbol, tf],
    queryFn: () => getCandles(symbol as string, tf, 500),
    enabled: Boolean(symbol),
    refetchInterval: 15000,
  });
  const tradesQuery = useQuery({
    queryKey: ['chart-trades', symbol],
    queryFn: () => getSymbolTrades(symbol as string),
    enabled: Boolean(symbol),
    refetchInterval: 20000,
  });

  const candles = useMemo(() => candlesQuery.data ?? [], [candlesQuery.data]);

  // --- Create the chart once on mount ---
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const chart = createChart(el, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: C.bg }, textColor: C.text },
      grid: { vertLines: { color: C.grid }, horzLines: { color: C.grid } },
      rightPriceScale: { borderColor: C.border },
      timeScale: { borderColor: C.border, timeVisible: true, secondsVisible: false },
      crosshair: { mode: CrosshairMode.Normal },
    });
    const candle = chart.addCandlestickSeries({
      upColor: C.gain,
      downColor: C.loss,
      borderVisible: false,
      wickUpColor: C.gain,
      wickDownColor: C.loss,
    });
    candle.priceScale().applyOptions({ scaleMargins: { top: 0.1, bottom: 0.28 } });
    const volume = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: '',
    });
    volume.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    const ema20 = chart.addLineSeries({
      color: C.accent,
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    const ema50 = chart.addLineSeries({
      color: C.caution,
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    chartRef.current = chart;
    candleRef.current = candle;
    volumeRef.current = volume;
    ema20Ref.current = ema20;
    ema50Ref.current = ema50;

    chart.subscribeCrosshairMove((param: MouseEventParams) => {
      const bar = param.seriesData.get(candle) as CandlestickData | undefined;
      if (!bar) {
        setLegend(defaultLegendRef.current);
        return;
      }
      const vol = param.seriesData.get(volume) as HistogramData | undefined;
      const e20 = param.seriesData.get(ema20) as LineData | undefined;
      const e50 = param.seriesData.get(ema50) as LineData | undefined;
      setLegend({
        o: bar.open,
        h: bar.high,
        l: bar.low,
        c: bar.close,
        vol: vol?.value ?? 0,
        ema20: e20?.value ?? null,
        ema50: e50?.value ?? null,
        up: bar.close >= bar.open,
      });
    });

    chart.subscribeClick((param: MouseEventParams) => {
      if (param.time == null) return;
      const t = param.time as number;
      let best: { time: number; tradeId: number } | null = null;
      let bestD = Infinity;
      for (const meta of tradeMetaRef.current) {
        const d = Math.abs(meta.time - t);
        if (d < bestD) {
          bestD = d;
          best = meta;
        }
      }
      if (best && bestD <= toleranceRef.current) setSelectedTradeId(best.tradeId);
    });

    return () => {
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      volumeRef.current = null;
      ema20Ref.current = null;
      ema50Ref.current = null;
    };
  }, []);

  // --- Push candle / volume / EMA data whenever candles change ---
  useEffect(() => {
    const candle = candleRef.current;
    const volume = volumeRef.current;
    const e20s = ema20Ref.current;
    const e50s = ema50Ref.current;
    if (!candle || !volume || !e20s || !e50s) return;

    if (candles.length === 0) {
      candle.setData([]);
      volume.setData([]);
      e20s.setData([]);
      e50s.setData([]);
      setLegend(null);
      return;
    }

    const closes = candles.map((c) => c.close);
    const e20 = ema(closes, 20);
    const e50 = ema(closes, 50);

    const candleData: CandlestickData[] = candles.map((c) => ({
      time: toTime(c.ts),
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));
    const volumeData: HistogramData[] = candles.map((c) => ({
      time: toTime(c.ts),
      value: c.volume,
      color: c.close >= c.open ? 'rgba(38,162,105,0.5)' : 'rgba(229,72,77,0.5)',
    }));
    const e20Data: LineData[] = [];
    const e50Data: LineData[] = [];
    candles.forEach((c, i) => {
      const t = toTime(c.ts);
      const v20 = e20[i];
      const v50 = e50[i];
      if (v20 != null) e20Data.push({ time: t, value: v20 });
      if (v50 != null) e50Data.push({ time: t, value: v50 });
    });

    candle.setData(candleData);
    volume.setData(volumeData);
    e20s.setData(e20Data);
    e50s.setData(e50Data);
    chartRef.current?.timeScale().fitContent();

    defaultLegendRef.current = legendFromCandle(candles, e20, e50);
    setLegend(defaultLegendRef.current);

    // Bar spacing (seconds) → click tolerance for matching trade markers.
    if (candles.length >= 2) {
      const a = candles.at(-1);
      const b = candles.at(-2);
      if (a && b) toleranceRef.current = Math.max(1, (toTime(a.ts) - toTime(b.ts)) * 1.5);
    }
  }, [candles]);

  // --- Draw trade markers whenever trades or candles change ---
  useEffect(() => {
    const candle = candleRef.current;
    if (!candle) return;
    const trades = tradesQuery.data ?? [];
    if (candles.length === 0 || trades.length === 0) {
      candle.setMarkers([]);
      tradeMetaRef.current = [];
      return;
    }
    const times = candles.map((c) => toTime(c.ts));
    const snap = (iso: string): UTCTimestamp => {
      const target = toTime(iso);
      let nearest = times[0] as UTCTimestamp;
      let bestD = Infinity;
      for (const t of times) {
        const d = Math.abs(t - target);
        if (d < bestD) {
          bestD = d;
          nearest = t;
        }
      }
      return nearest;
    };

    const markers: SeriesMarker<Time>[] = [];
    const meta: { time: number; tradeId: number }[] = [];
    for (const trade of trades) {
      const long = trade.direction === 'long';
      const entryT = snap(trade.entry_ts);
      const exitT = snap(trade.exit_ts);
      markers.push({
        time: entryT,
        position: long ? 'belowBar' : 'aboveBar',
        color: long ? C.gain : C.loss,
        shape: long ? 'arrowUp' : 'arrowDown',
        text: long ? 'BUY' : 'SELL',
      });
      markers.push({
        time: exitT,
        position: long ? 'aboveBar' : 'belowBar',
        color: trade.net_pnl >= 0 ? C.gain : C.loss,
        shape: long ? 'arrowDown' : 'arrowUp',
        text: 'EXIT',
      });
      meta.push({ time: entryT, tradeId: trade.id }, { time: exitT, tradeId: trade.id });
    }
    markers.sort((a, b) => (a.time as number) - (b.time as number));
    candle.setMarkers(markers);
    tradeMetaRef.current = meta;
  }, [tradesQuery.data, candles]);

  const trades = tradesQuery.data ?? [];
  const selectedTrade = trades.find((t) => t.id === selectedTradeId) ?? null;
  const showEmpty = Boolean(symbol) && candlesQuery.isSuccess && candles.length === 0;
  const showError = candlesQuery.isError || instrumentsQuery.isError;

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <select
          value={symbol ?? ''}
          onChange={(e) => {
            setSymbol(e.target.value);
            setSelectedTradeId(null);
          }}
          className="rounded-md border border-surface-border bg-surface-raised px-3 py-1.5 text-sm text-content focus:outline-none focus:ring-2 focus:ring-accent/50"
        >
          {!symbol ? <option value="">Loading symbols…</option> : null}
          {(instrumentsQuery.data ?? []).map((i) => (
            <option key={i.symbol} value={i.symbol}>
              {i.symbol}
            </option>
          ))}
        </select>

        <div className="flex items-center gap-1 rounded-md border border-surface-border bg-surface-raised p-0.5">
          {TIMEFRAMES.map((t) => (
            <button
              key={t.tf}
              type="button"
              onClick={() => setTf(t.tf)}
              className={cn(
                'rounded px-3 py-1 text-xs font-medium transition-colors',
                tf === t.tf ? 'bg-accent text-white' : 'text-content-muted hover:text-content',
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Chart */}
      <Card className="relative overflow-hidden p-0">
        <LegendRow legend={legend} symbol={symbol ?? '—'} tf={tf} />
        <div ref={containerRef} className="h-[380px] w-full sm:h-[480px]" />

        {(candlesQuery.isLoading || instrumentsQuery.isLoading) && !showError ? (
          <div className="absolute inset-0 z-20 grid place-items-center bg-surface/60 text-sm text-content-muted">
            Loading chart…
          </div>
        ) : null}
        {showError ? (
          <div className="absolute inset-0 z-20 grid place-items-center bg-surface/70 px-6 text-center text-sm text-loss">
            Could not load chart data:{' '}
            {candlesQuery.error instanceof Error ? candlesQuery.error.message : 'request failed'}
          </div>
        ) : null}
        {showEmpty ? (
          <div className="absolute inset-0 z-20 grid place-items-center bg-surface/70 px-6 text-center">
            <div>
              <p className="text-sm font-medium text-content">
                No candles for {symbol} on {tf} yet.
              </p>
              <p className="mt-1 text-xs text-content-muted">
                The simulated feed builds candles during a live session. Try another timeframe, or
                let the feed run — this refreshes automatically.
              </p>
            </div>
          </div>
        ) : null}
      </Card>

      {/* Trade detail (from click or list) */}
      {selectedTrade ? (
        <TradeDetail trade={selectedTrade} onClose={() => setSelectedTradeId(null)} />
      ) : null}

      {/* Trades for this symbol — clicking selects (and the chart markers mirror these) */}
      {trades.length > 0 ? (
        <Card className="overflow-x-auto p-0">
          <div className="border-b border-surface-border px-5 py-3">
            <h2 className="text-sm font-semibold text-content">Trades on {symbol}</h2>
            <p className="mt-0.5 text-xs text-content-muted">
              Click a row (or a ▲/▼ marker on the chart) for full detail.
            </p>
          </div>
          <table className="w-full min-w-[520px] text-sm">
            <thead>
              <tr className="border-b border-surface-border text-left text-xs text-content-muted">
                <th className="px-4 py-2.5 font-medium">Side</th>
                <th className="px-4 py-2.5 text-right font-medium">Entry</th>
                <th className="px-4 py-2.5 text-right font-medium">Exit</th>
                <th className="px-4 py-2.5 text-right font-medium">Net P&L</th>
                <th className="px-4 py-2.5 text-right font-medium">R</th>
                <th className="px-4 py-2.5 font-medium">Closed</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((t) => (
                <tr
                  key={t.id}
                  onClick={() => setSelectedTradeId(t.id)}
                  className={cn(
                    'cursor-pointer border-b border-surface-border/50 last:border-0 hover:bg-surface-overlay/50',
                    selectedTradeId === t.id && 'bg-surface-overlay/60',
                  )}
                >
                  <td className="px-4 py-2.5">
                    <span className={cn(t.direction === 'long' ? 'text-gain' : 'text-loss')}>
                      {t.direction}
                    </span>
                  </td>
                  <td className="tabular px-4 py-2.5 text-right text-content-muted">
                    {t.entry_price}
                  </td>
                  <td className="tabular px-4 py-2.5 text-right text-content-muted">
                    {t.exit_price}
                  </td>
                  <td
                    className={cn(
                      'tabular px-4 py-2.5 text-right font-medium',
                      t.net_pnl > 0
                        ? 'text-gain'
                        : t.net_pnl < 0
                          ? 'text-loss'
                          : 'text-content-muted',
                    )}
                  >
                    {formatINR(t.net_pnl)}
                  </td>
                  <td
                    className={cn(
                      'tabular px-4 py-2.5 text-right',
                      t.r_multiple > 0
                        ? 'text-gain'
                        : t.r_multiple < 0
                          ? 'text-loss'
                          : 'text-content-muted',
                    )}
                  >
                    {t.r_multiple.toFixed(2)}
                  </td>
                  <td className="px-4 py-2.5 text-content-muted">
                    {new Date(t.exit_ts).toLocaleString('en-IN', {
                      day: '2-digit',
                      month: 'short',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      ) : null}
    </div>
  );
}
