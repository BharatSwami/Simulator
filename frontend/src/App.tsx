import { useEffect, useMemo, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

type AssetsSnapshot = Record<string, number>;

type SnapshotMessage = {
  type: "snapshot";
  current: {
    tick: number;
    timestamp: number;
    factors: Record<string, number>;
    assets: AssetsSnapshot;
  };
  history: {
    tick: number;
    timestamp: number;
    factors: Record<string, number>;
    assets: AssetsSnapshot;
  }[];
};

type TickMessage = {
  type: "tick";
  tick: number;
  timestamp: number;
  factors: Record<string, number>;
  assets: AssetsSnapshot;
};

type AckMessage = {
  type: "ack";
  state: {
    tick: number;
    running: boolean;
  };
};

// const WS_URL = import.meta.env.VITE_WS_URL ?? "ws://localhost:8000/ws/sim";
const WS_URL = import.meta.env.VITE_WS_URL ?? "wss://simulator-uk25.onrender.com/ws/sim";


// const WS_URL = import.meta.env.VITE_WS_URL ?? "wss://your-render-url.onrender.com/ws/sim";

type SeriesPoint = { tick: number; value: number };
type AssetSeries = Record<string, SeriesPoint[]>;

type AssetMeta = {
  id: string;
  label: string;
  category: string;
};

// Static metadata mirroring backend/config/model.json categories & assets
const ASSET_METAS: AssetMeta[] = [
  { id: "WHEAT", label: "Wheat", category: "commodities" },
  { id: "OIL", label: "Oil", category: "commodities" },
  { id: "CORN", label: "Corn", category: "commodities" },
  { id: "COPPER", label: "Copper", category: "metals" },
  { id: "ALUMINIUM", label: "Aluminium", category: "metals" },
  { id: "LITHIUM", label: "Lithium", category: "metals" },
  { id: "USD_IDX", label: "USD Index", category: "currency" },
  { id: "EUR_IDX", label: "EUR Index", category: "currency" },
  { id: "JPY_IDX", label: "JPY Index", category: "currency" },
  { id: "TECH_CO", label: "Tech Co", category: "stocks" },
  { id: "BANK_CO", label: "Bank Co", category: "stocks" },
  { id: "ENERGY_CO", label: "Energy Co", category: "stocks" },
  { id: "CALL_TECH", label: "Call on Tech", category: "derivatives" },
  { id: "FUT_OIL", label: "Oil Future", category: "derivatives" },
  { id: "SWAP_IR", label: "IR Swap", category: "derivatives" },
  { id: "BTC", label: "Bitcoin", category: "crypto" },
  { id: "ETH", label: "Ethereum", category: "crypto" },
  { id: "ALT1", label: "Altcoin 1", category: "crypto" }
];

const CATEGORY_LABELS: Record<string, string> = {
  commodities: "Commodities",
  metals: "Metals",
  currency: "Currency",
  stocks: "Stocks",
  derivatives: "Derivatives",
  crypto: "Crypto"
};

function App() {
  const [series, setSeries] = useState<AssetSeries>({});
  const [running, setRunning] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<
    "connecting" | "open" | "closed"
  >("connecting");

  const latestTick = useMemo(() => {
    const allPoints = Object.values(series).flat();
    return allPoints.at(-1);
  }, [series]);

  useEffect(() => {
    let ws: WebSocket | null = new WebSocket(WS_URL);
    setConnectionStatus("connecting");

    ws.onopen = () => {
      setConnectionStatus("open");
    };

    ws.onmessage = (event) => {
      const msg = JSON.parse(
        event.data
      ) as SnapshotMessage | TickMessage | AckMessage | any;

      if (msg.type === "snapshot") {
        const allSeries: AssetSeries = {};
        const pushPoint = (tick: number, assets: AssetsSnapshot) => {
          for (const [id, value] of Object.entries(assets)) {
            if (!allSeries[id]) allSeries[id] = [];
            allSeries[id].push({ tick, value });
          }
        };
        for (const h of msg.history) {
          pushPoint(h.tick, h.assets);
        }
        pushPoint(msg.current.tick, msg.current.assets);
        for (const key of Object.keys(allSeries)) {
          if (allSeries[key].length > 500) {
            allSeries[key] = allSeries[key].slice(-500);
          }
        }
        setSeries(allSeries);
      } else if (msg.type === "tick") {
        setSeries((prev) => {
          const next: AssetSeries = { ...prev };
          for (const [id, value] of Object.entries(msg.assets)) {
            const arr = next[id] ? [...next[id]] : [];
            arr.push({ tick: msg.tick, value: Number(value) });
            next[id] = arr.slice(-500);
          }
          return next;
        });
      } else if (msg.type === "ack" && msg.state) {
        setRunning(msg.state.tick > 0 && msg.state.running === true);
      }
    };

    ws.onclose = () => {
      setConnectionStatus("closed");
    };

    ws.onerror = () => {
      setConnectionStatus("closed");
    };

    return () => {
      ws?.close();
      ws = null;
    };
  }, []);

  const handleControl = (action: "start" | "pause" | "reset") => {
    const ws = new WebSocket(WS_URL);
    ws.onopen = () => {
      ws.send(JSON.stringify({ type: "control", action }));
      ws.close();
    };
  };

  const assetsByCategory: Record<string, AssetMeta[]> = useMemo(() => {
    const byCat: Record<string, AssetMeta[]> = {};
    for (const meta of ASSET_METAS) {
      if (!byCat[meta.category]) byCat[meta.category] = [];
      byCat[meta.category].push(meta);
    }
    return byCat;
  }, []);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h2>Economic World Simulator</h2>
          <div className="status-text">
            {connectionStatus === "connecting" && "Connecting to backend..."}
            {connectionStatus === "open" && "Connected to backend"}
            {connectionStatus === "closed" && "Disconnected from backend"}
          </div>
        </div>
        <div className="controls">
          <button
            className="primary"
            onClick={() => handleControl("start")}
            disabled={connectionStatus !== "open"}
          >
            Start
          </button>
          <button
            onClick={() => handleControl("pause")}
            disabled={connectionStatus !== "open"}
          >
            Pause
          </button>
          <button
            onClick={() => handleControl("reset")}
            disabled={connectionStatus !== "open"}
          >
            Reset
          </button>
        </div>
      </header>

      <div className="charts-grid">
        {Object.entries(assetsByCategory).map(([category, metas]) => (
          <div key={category}>
            <h3 className="chart-title">
              {CATEGORY_LABELS[category] ?? category}
            </h3>
            <div className="charts-grid">
              {metas.slice(0, 3).map((meta) => (
                <ChartCard
                  key={meta.id}
                  title={meta.label}
                  data={series[meta.id] ?? []}
                  color="#4f46e5"
                />
              ))}
            </div>
          </div>
        ))}
      </div>

      <section className="params-panel">
        <div className="param-actions">
          <span className="status-text">
            {latestTick
              ? `Last tick: ${latestTick.tick}`
              : "No data yet"}
          </span>
        </div>
      </section>
    </div>
  );
}

type ChartCardProps = {
  title: string;
  data: SeriesPoint[];
  color: string;
};

function ChartCard({ title, data, color }: ChartCardProps) {
  return (
    <div className="chart-card">
      <div className="chart-title">{title}</div>
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={data}>
          <CartesianGrid stroke="#111827" strokeDasharray="3 3" />
          <XAxis dataKey="tick" tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 10 }} />
          <Tooltip
            contentStyle={{
              background: "#020617",
              border: "1px solid #1f2937",
              borderRadius: "0.5rem",
              fontSize: "0.75rem",
            }}
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={1.8}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default App;

