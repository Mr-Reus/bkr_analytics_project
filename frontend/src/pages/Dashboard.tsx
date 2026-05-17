/* eslint-disable react-hooks/set-state-in-effect */
/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Typography,
  Button,
  Box,
  Paper,
  Slider,
  CircularProgress,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Skeleton,
  AppBar,
  Toolbar,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  CssBaseline,
  Divider,
  Avatar,
  Grid,
} from "@mui/material";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  ZAxis,
  Legend,
  ReferenceArea,
} from "recharts";
import type { TooltipProps } from "recharts";
import PlotlyChart from "react-plotly.js";
import  api from "../api/axios";

const Plot = (PlotlyChart as any).default || PlotlyChart;
const drawerWidth = 240;

interface AssociationRule {
  if_bought: string[];
  then_buy: string[];
  support: number;
  confidence: number;
  lift: number;
}

interface RFMCustomer {
  buyer_id: string;
  recency: number;
  frequency: number;
  monetary: number;
  cluster: number;
  customer_count?: number;
}

interface KPIData {
  total_revenue: number;
  total_customers: number;
}

interface AnalystUser {
  id: number;
  email: string;
  created_at: string;
}

interface CustomTooltipProps extends TooltipProps<number, string> {
  payload?: any[];
}

const CustomTooltip = ({ active, payload }: CustomTooltipProps) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <Paper
        elevation={3}
        sx={{
          p: 2,
          backgroundColor: "rgba(255, 255, 255, 0.98)",
          borderLeft: data.z > 2 ? "4px solid #2e7d32" : "4px solid #9e9e9e",
        }}
      >
        <Typography
          variant="body2"
          color="textPrimary"
          sx={{ fontWeight: "bold", mb: 1 }}
        >
          {data.name}
        </Typography>
        <Typography variant="body2" color="textSecondary">
          Support (частота):{" "}
          <strong style={{ color: "#333" }}>
            {(data.x * 100).toFixed(2)}%
          </strong>
        </Typography>
        <Typography variant="body2" color="textSecondary">
          Confidence (ймовірність):{" "}
          <strong style={{ color: "#333" }}>
            {(data.y * 100).toFixed(1)}%
          </strong>
        </Typography>
        <Typography
          variant="body2"
          sx={{
            color: data.z > 2 ? "#2e7d32" : "text.secondary",
            fontWeight: "bold",
          }}
        >
          Lift: {data.z.toFixed(2)}
        </Typography>
      </Paper>
    );
  }
  return null;
};

const formatCurrency = (value: number | undefined): string => {
  if (value === undefined || isNaN(value)) return "0.00";
  if (value >= 1000000) {
    return (value / 1000000).toFixed(2) + "M"; 
  }
  if (value >= 1000) {
    return (value / 1000).toFixed(1) + "K"; 
  }
  return value.toFixed(2); 
};

export const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const [currentView, setCurrentView] = useState<string>("Dashboard Overview");
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const [successMsg, setSuccessMsg] = useState<string>("");

  const [userNickname, setUserNickname] = useState<string>("User");

  const [kpis, setKpis] = useState<KPIData | null>(null);

  const [tenantKey, setTenantKey] = useState<string>("");
  const [analysts, setAnalysts] = useState<AnalystUser[]>([]);
  const [newAnalystEmail, setNewAnalystEmail] = useState<string>("");
  const [newAnalystPassword, setNewAnalystPassword] = useState<string>("");

  const [minSupport, setMinSupport] = useState<number>(0.01);
  const [minConfidence, setMinConfidence] = useState<number>(0.5);
  const [rules, setRules] = useState<AssociationRule[]>([]);
  const [lastFpTime, setLastFpTime] = useState<number>(0);

  const [rfmData, setRfmData] = useState<RFMCustomer[]>([]);

  const [refAreaLeft, setRefAreaLeft] = useState<number | null>(null);
  const [refAreaRight, setRefAreaRight] = useState<number | null>(null);
  const [refAreaTop, setRefAreaTop] = useState<number | null>(null);
  const [refAreaBottom, setRefAreaBottom] = useState<number | null>(null);
  const [xDomain, setXDomain] = useState<[number | string, number | string]>([
    "auto",
    "auto",
  ]);
  const [yDomain, setYDomain] = useState<[number | string, number | string]>([
    "auto",
    "auto",
  ]);
  const [isZoomed, setIsZoomed] = useState(false);

  const zoomOut = useCallback(() => {
    setXDomain(["auto", "auto"]);
    setYDomain(["auto", "auto"]);
    setIsZoomed(false);
  }, []);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split(".")[1]));
        const roleName = payload.role === "admin" ? "Admin" : "Business Analyst";
        setUserNickname(`${roleName} #${payload.sub}`);
      } catch (e) {
        console.error("Помилка розшифровки токена", e);
      }
    }
  }, []);

  const fetchKPIs = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get("/api/analytics/kpis");
      setKpis(response.data);
    } catch {
      setError("Не вдалося завантажити показники бізнес-ефективності KPI");
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchTenantKey = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get("/api/admin/integration-key");
      setTenantKey(response.data.tenant_key);
    } catch {
      setError("Не вдалося отримати маркер інтеграції тенанта");
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchAnalysts = useCallback(async () => {
    try {
      const response = await api.get("/api/admin/analysts");
      setAnalysts(response.data);
    } catch {
      console.error("Не вдалося виконати читання списку аналітиків");
    }
  }, []);

  const fetchFPResults = useCallback(
    async (isPolling = false) => {
      if (!isPolling) setLoading(true);
      setError("");
      try {
        const response = await api.get(
          "/api/analytics/export-json?report_type=fp_growth_rules",
        );
        if (response.data && response.data.association_rules) {
          setRules(response.data.association_rules);
          const reportTime = response.data.created_at
            ? new Date(response.data.created_at).getTime()
            : Date.now();
          setLastFpTime(reportTime);
          if (!isPolling) zoomOut();
          return reportTime;
        }
        return 0;
      } catch (err: any) {
        if (err.response?.status !== 404 && !isPolling) {
          setError(
            "Не вдалося отримати звіт інтелектуального аналізу FP-Growth",
          );
        }
        return 0;
      } finally {
        if (!isPolling) setLoading(false);
      }
    },
    [zoomOut],
  );

  const fetchRFMResults = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await api.get(
        "/api/analytics/export-json?report_type=rfm_analysis",
      );
      if (response.data && response.data.segments) {
        const normalized = Object.values(response.data.segments).map(
          (item: any) => ({
            buyer_id: `Cluster ${item.cluster_id}`,
            recency: Number(item.recency || 0),
            frequency: Number(item.frequency || 0),
            monetary: Number(item.monetary || 0),
            cluster: Number(item.cluster_id || 0),
            customer_count: Number(item.customer_count || 0),
          }),
        );
        setRfmData(normalized);
      }
    } catch (err: any) {
      if (err.response?.status !== 404) {
        setError("Не вдалося завантажити сформовані кластери сегментації");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setError("");
    setSuccessMsg("");
    if (currentView === "Dashboard Overview") {
      fetchKPIs();
    } else if (currentView === "Market Basket Rules") {
      fetchFPResults();
    } else if (currentView === "RFM Segmentation") {
      fetchRFMResults();
    } else if (currentView === "Tenant Settings") {
      fetchTenantKey();
      fetchAnalysts();
    }
  }, [
    currentView,
    fetchKPIs,
    fetchFPResults,
    fetchRFMResults,
    fetchTenantKey,
    fetchAnalysts,
  ]);
  
  const handleCreateAnalyst = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccessMsg("");
    if (!newAnalystEmail || !newAnalystPassword) {
      setError("Для ініціації створення заповніть всі обов'язкові поля");
      return;
    }
    try {
      await api.post("/api/admin/analysts", {
        email: newAnalystEmail,
        password: newAnalystPassword,
      });
      setSuccessMsg(
        "✓ Новий обліковий запис бізнес-аналітика успішно збережено в базі сховища",
      );
      setNewAnalystEmail("");
      setNewAnalystPassword("");
      fetchAnalysts();
      setTimeout(() => setSuccessMsg(""), 4000);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Помилка реєстрації аналітика");
    }
  };

  const handleDeleteAnalyst = async (id: number) => {
    setError("");
    setSuccessMsg("");
    if (
      !window.confirm(
        "Скасувати легітимний доступ даного користувача до аналітичного рушія системи?",
      )
    )
      return;
    try {
      await api.delete(`/api/admin/analysts/${id}`);
      setSuccessMsg("✓ Обліковий запис успішно деактивовано (видалено)");
      fetchAnalysts();
      setTimeout(() => setSuccessMsg(""), 4000);
    } catch {
      setError("Не вдалося видалити обрану сутність");
    }
  };

  const handleRunFpAnalytics = async () => {
    setLoading(true);
    setError("");
    setSuccessMsg("");
    setRules([]);
    try {
      await api.post("/api/analytics/run", {
        min_support: minSupport,
        min_threshold: minConfidence,
      });
      setSuccessMsg(
        "⚙️ Пайплайн Data Mining запущено у фоновому режимі...",
      );
      let attempts = 0;
      const maxAttempts = 15;
      const pollInterval = setInterval(async () => {
        attempts++;
        const newReportTime = await fetchFPResults(true);
        if (
          newReportTime > lastFpTime ||
          (lastFpTime === 0 && newReportTime > 0)
        ) {
          clearInterval(pollInterval);
          setSuccessMsg("✓ Фоновий аналіз успішно завершено, дані оновлено");
          setLoading(false);
          zoomOut();
          setTimeout(() => setSuccessMsg(""), 4000);
        } else if (attempts >= maxAttempts) {
          clearInterval(pollInterval);
          setError("Час очікування завершення фонового завдання вичерпано");
          setSuccessMsg("");
          setLoading(false);
        }
      }, 3000);
    } catch {
      setError("Помилка ініціалізації фонового аналітичного рушія");
      setLoading(false);
    }
  };

  const handleRunRfmPipeline = async () => {
    setLoading(true);
    setError("");
    setSuccessMsg("");
    try {
      await api.post("/api/analytics/run", {
        min_support: minSupport,
        min_threshold: minConfidence,
      });
      setSuccessMsg("⚙️ Ініційовано перерахунок K-Means Clustering у фоні...");
      setTimeout(async () => {
        await fetchRFMResults();
        setSuccessMsg("✓ Параметри сегментації успішно перераховано");
        setTimeout(() => setSuccessMsg(""), 4000);
      }, 4000);
    } catch {
      setError("Помилка запуску сегментації");
      setLoading(false);
    }
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(tenantKey);
    setSuccessMsg("📋 Ключ інтеграції успішно скопійовано в буфер обміну");
    setTimeout(() => setSuccessMsg(""), 3000);
  };

  const zoom = () => {
    let left = refAreaLeft;
    let right = refAreaRight;
    let bottom = refAreaBottom;
    let top = refAreaTop;
    if (left === right || bottom === top) {
      setRefAreaLeft(null);
      setRefAreaRight(null);
      setRefAreaTop(null);
      setRefAreaBottom(null);
      return;
    }
    if (left !== null && right !== null && left > right)
      [left, right] = [right, left];
    if (bottom !== null && top !== null && bottom > top)
      [bottom, top] = [top, bottom];
    setRefAreaLeft(null);
    setRefAreaRight(null);
    setRefAreaTop(null);
    setRefAreaBottom(null);
    setXDomain([left as number, right as number]);
    setYDomain([bottom as number, top as number]);
    setIsZoomed(true);
  };

  const handleExportCSV = () => {
    if (rules.length === 0) return;
    const headers = [
      "Antecedent",
      "Consequent",
      "Support",
      "Confidence",
      "Lift",
    ];
    const csvRows = rules.map((rule) => [
      `"${rule.if_bought.join(", ")}"`,
      `"${rule.then_buy.join(", ")}"`,
      rule.support.toFixed(4),
      rule.confidence.toFixed(4),
      rule.lift.toFixed(4),
    ]);
    const csvContent = [
      headers.join(","),
      ...csvRows.map((e) => e.join(",")),
    ].join("\n");
    const blob = new Blob(["\uFEFF" + csvContent], {
      type: "text/csv;charset=utf-8;",
    });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `bkr_association_rules.csv`;
    link.click();
  };

  const handleLogout = () => {
    localStorage.removeItem("access_token");
    navigate("/");
  };

  const renderRFMPlot = () => {
    if (rfmData.length === 0) return null;
    const colors = [
      "#1f77b4",
      "#ff7f0e",
      "#2ca02c",
      "#d62728",
      "#9467bd",
      "#8c564b",
    ];
    const maxMonetary = Math.max(...rfmData.map((d) => d.monetary), 0);
    const sizeRef = maxMonetary > 0 ? (2.0 * maxMonetary) / 80 ** 2 : 1;

    const traces = rfmData.map((clusterData, index) => ({
      x: [clusterData.recency],
      y: [clusterData.frequency],
      text: [
        `<b>Кластер ${clusterData.cluster}</b><br>Клієнтів: ${clusterData.customer_count} осіб<br>Середня давність: ${clusterData.recency.toFixed(1)} дн.<br>Середня частота: ${clusterData.frequency.toFixed(1)} зам.<br>Середній чек: $${clusterData.monetary.toFixed(2)}`,
      ],
      mode: "markers",
      type: "scatter",
      name: `Сегмент ${clusterData.cluster} (${clusterData.customer_count} чол)`,
      marker: {
        size: [clusterData.monetary],
        sizemode: "area",
        sizeref: sizeRef,
        sizemin: 15,
        color: colors[index % colors.length],
        opacity: 0.8,
        line: { width: 2, color: "white" },
      },
      hoverinfo: "text",
    }));

    return (
      <Plot
        data={traces}
        layout={{
          autosize: true,
          margin: { l: 60, r: 40, b: 60, t: 20 },
          paper_bgcolor: "transparent",
          plot_bgcolor: "#fafafa",
          xaxis: {
            title: {
              text: "Recency (Середня давність останньої покупки, днів)",
            },
            gridcolor: "#eeeeee",
            zeroline: false,
          },
          yaxis: {
            title: { text: "Frequency (Середня кількість замовлень)" },
            gridcolor: "#eeeeee",
            zeroline: false,
          },
          legend: { orientation: "h", y: 1.1, x: 0 },
          hovermode: "closest",
        }}
        useResizeHandler={true}
        style={{ width: "100%", height: "100%", minHeight: "500px" }}
        config={{ responsive: true, displaylogo: false }}
      />
    );
  };

  const allChartData = rules
    .map((rule) => ({
      x: rule.support,
      y: rule.confidence,
      z: rule.lift,
      name: `${rule.if_bought.join(", ")} -> ${rule.then_buy.join(", ")}`,
    }))
    .sort((a, b) => b.z - a.z);
  const highLiftData = allChartData.slice(0, 300).filter((d) => d.z > 2);
  const normalLiftData = allChartData.slice(0, 300).filter((d) => d.z <= 2);

  return (
    <Box sx={{ display: "flex" }}>
      <CssBaseline />
      <AppBar
        position="fixed"
        sx={{
          zIndex: (theme) => theme.zIndex.drawer + 1,
          backgroundColor: "#1976d2",
          boxShadow: "none",
          borderBottom: "1px solid rgba(255,255,255,0.2)",
        }}
      >
        <Toolbar>
          <Typography
            variant="h6"
            noWrap
            component="div"
            sx={{ flexGrow: 1, fontWeight: "bold" }}
          >
            BKR Analytics Platform
          </Typography>
          <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
            <Avatar
              sx={{
                width: 32,
                height: 32,
                bgcolor: "transparent",
                border: "1px solid white",
              }}
            />
            <Typography variant="body2" sx={{ mr: 2, fontWeight: 500 }}>
              {userNickname}
            </Typography>
            <Button
              color="inherit"
              variant="outlined"
              onClick={handleLogout}
              sx={{ borderColor: "rgba(255,255,255,0.5)", borderRadius: 2 }}
            >
              Logout
            </Button>
          </Box>
        </Toolbar>
      </AppBar>

      <Drawer
        variant="permanent"
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          [`& .MuiDrawer-paper`]: {
            width: drawerWidth,
            boxSizing: "border-box",
            backgroundColor: "#ffffff",
            borderRight: "1px solid #e0e0e0",
          },
        }}
      >
        <Toolbar />
        <Box sx={{ overflow: "auto", mt: 3 }}>
          <Typography
            variant="caption"
            sx={{
              px: 3,
              color: "#9e9e9e",
              fontWeight: "bold",
              textTransform: "uppercase",
              letterSpacing: 1,
            }}
          >
            Workspaces
          </Typography>
          <List sx={{ mt: 1 }}>
            {[
              "Dashboard Overview",
              "RFM Segmentation",
              "Market Basket Rules",
              "Tenant Settings",
            ].map((text) => (
              <ListItem key={text} disablePadding>
                <ListItemButton
                  selected={currentView === text}
                  onClick={() => setCurrentView(text)}
                  sx={{
                    py: 1.5,
                    mx: 1,
                    borderRadius: 1,
                    mb: 0.5,
                    color: currentView === text ? "#1976d2" : "#616161",
                    "&.Mui-selected": { backgroundColor: "#e3f2fd" },
                  }}
                >
                  <Typography
                    sx={{
                      fontWeight: currentView === text ? 600 : 400,
                      fontSize: "0.9rem",
                    }}
                  >
                    {text}
                  </Typography>
                </ListItemButton>
              </ListItem>
            ))}
          </List>
        </Box>
      </Drawer>

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: { xs: 2, md: 4 },
          backgroundColor: "#f4f6f8",
          minHeight: "100vh",
        }}
      >
        <Toolbar />

        {error && (
          <Alert severity="error" sx={{ mb: 3, borderRadius: 2 }}>
            {error}
          </Alert>
        )}
        {successMsg && (
          <Alert
            severity="success"
            variant="filled"
            sx={{ mb: 3, borderRadius: 2 }}
          >
            {successMsg}
          </Alert>
        )}

        {currentView === "Dashboard Overview" && (
          <Box sx={{ maxWidth: 1400, margin: "0 auto" }}>
            <Box sx={{ mb: 4 }}>
              <Typography
                variant="h4"
                sx={{ fontWeight: 800, color: "#212121", mb: 1 }}
              >
                Головна панель показників (KPI)
              </Typography>
              <Typography variant="body1" sx={{ color: "#616161" }}>
                Зведена бізнес-аналітика поточного бізнес-користувача
              </Typography>
            </Box>

            <Grid container spacing={4} sx={{ mb: 5 }}>
              <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                <Paper
                  elevation={0}
                  sx={{
                    p: 4,
                    borderRadius: 3,
                    border: "1px solid #e0e0e0",
                    backgroundColor: "#ffffff",
                    height: "100%",
                    minHeight: 220,
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "center",
                  }}
                >
                  <Typography
                    variant="subtitle2"
                    sx={{
                      color: "#757575",
                      fontWeight: 600,
                      textTransform: "uppercase",
                      mb: 1,
                    }}
                  >
                    Загальний Валовий Дохід
                  </Typography>
                  {loading ? (
                    <Skeleton width="80%" height={60} />
                  ) : (
                    <Typography
                      variant="h4"
                      sx={{
                        fontWeight: 800,
                        color: "#107c10",
                        wordBreak: "break-word",
                        fontSize: { xs: "2rem", md: "2.5rem" },
                      }}
                    >
                      ${formatCurrency(kpis?.total_revenue)}
                    </Typography>
                  )}
                  <Typography
                    variant="caption"
                    sx={{ color: "#9e9e9e", display: "block", mt: 2 }}
                  >
                    Фактичний обсяг грошових надходжень від усіх замовлень
                  </Typography>
                </Paper>
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                <Paper
                  elevation={0}
                  sx={{
                    p: 4,
                    borderRadius: 3,
                    border: "1px solid #e0e0e0",
                    backgroundColor: "#ffffff",
                    height: "100%",
                    minHeight: 220,
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "center",
                  }}
                >
                  <Typography
                    variant="subtitle2"
                    sx={{
                      color: "#757575",
                      fontWeight: 600,
                      textTransform: "uppercase",
                      mb: 1,
                    }}
                  >
                    Активна база клієнтів
                  </Typography>
                  {loading ? (
                    <Skeleton width="60%" height={60} />
                  ) : (
                    <Typography
                      variant="h4"
                      sx={{
                        fontWeight: 800,
                        color: "#1976d2",
                        wordBreak: "break-word",
                        fontSize: { xs: "2rem", md: "2.5rem" },
                      }}
                    >
                      {kpis?.total_customers || "0"}
                    </Typography>
                  )}
                  <Typography
                    variant="caption"
                    sx={{ color: "#9e9e9e", display: "block", mt: 2 }}
                  >
                    Кількість унікальних людей, які здійснили хоча б одну
                    покупку
                  </Typography>
                </Paper>
              </Grid>
              
              <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                <Paper
                  elevation={0}
                  sx={{
                    p: 4,
                    borderRadius: 3,
                    border: "1px solid #e0e0e0",
                    backgroundColor: "#ffffff",
                    height: "100%",
                    minHeight: 220,
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "center",
                  }}
                >
                  <Typography
                    variant="subtitle2"
                    sx={{
                      color: "#757575",
                      fontWeight: 600,
                      textTransform: "uppercase",
                      mb: 1,
                    }}
                  >
                    Середній чек клієнта
                  </Typography>
                  {loading ? (
                    <Skeleton width="70%" height={60} />
                  ) : (
                    <Typography
                      variant="h4"
                      sx={{
                        fontWeight: 800,
                        color: "#212121",
                        wordBreak: "break-word",
                        fontSize: { xs: "2rem", md: "2.5rem" },
                      }}
                    >
                      
                      ${formatCurrency(
                        kpis && kpis.total_customers > 0
                          ? kpis.total_revenue / kpis.total_customers
                          : 0,
                      )}
                    </Typography>
                  )}
                  <Typography
                    variant="caption"
                    sx={{ color: "#9e9e9e", display: "block", mt: 2 }}
                  >
                    Середня сума грошей, яку залишає один клієнт за весь час
                  </Typography>
                </Paper>
              </Grid>
            </Grid>

            <Paper
              elevation={0}
              sx={{
                p: 5,
                borderRadius: 3,
                border: "1px solid #e0e0e0",
                backgroundColor: "#ffffff",
              }}
            >
              <Typography variant="h6" sx={{ fontWeight: "bold", mb: 2 }}>
                Статус готовності аналітичних моделей до CRISP-DM
              </Typography>
              <Divider sx={{ mb: 3 }} />
              <Typography
                variant="body1"
                component="p"
                sx={{ color: "#424242", mb: 2, lineHeight: 1.6 }}
              >
                Дана платформа та реалізує повноцінний закритий цикл архітектури
                бізнес-аналітики (BI) для систем електронної комерції
              </Typography>
              <Typography
                variant="body2"
                sx={{
                  color: "#616161",
                  p: 2,
                  backgroundColor: "#f5f5f5",
                  borderRadius: 2,
                }}
              >
                💡 <strong>Порада по роботі:</strong> якщо KPI показують нулі,
                скористайтеся вкладкою <strong>Tenant Settings</strong>, щоб
                скопіювати токен, запустити десктопний ETL-модуль, виконайте
                вивантаження даних і запустити математичні ядра у відповідних
                вкладках
              </Typography>
            </Paper>
          </Box>
        )}

        {currentView === "Market Basket Rules" && (
          <Box sx={{ maxWidth: 1400, margin: "0 auto" }}>
            <Box sx={{ mb: 4 }}>
              <Typography
                variant="h5"
                sx={{ fontWeight: 800, color: "#212121", mb: 1 }}
              >
                Цільові крос-сейл комбінації концентруються у зоні високого
                Confidence
              </Typography>
              <Typography
                variant="body1"
                sx={{ color: "#616161", maxWidth: 900 }}
              >
                Правила з <strong>високим Lift {">"} 2 (зелені ромби)</strong>{" "}
                демонструють найвищу ефективність спільних покупок і мають
                використовуватися для рекомендаційних систем. Графік відображає
                топ-300 найсильніших правил.
              </Typography>
            </Box>
            <Grid container spacing={3}>
              <Grid size={{ xs: 12, md: 3 }}>
                <Paper
                  elevation={0}
                  sx={{
                    p: 4,
                    height: "100%",
                    borderRadius: 3,
                    border: "1px solid #e0e0e0",
                  }}
                >
                  <Typography
                    variant="subtitle2"
                    sx={{ fontWeight: "bold", color: "#757575", mb: 2 }}
                  >
                    Parameters
                  </Typography>
                  <Divider sx={{ mb: 3 }} />
                  <Typography variant="body2" sx={{ fontWeight: 500 }}>
                    Min Support: {minSupport}
                  </Typography>
                  <Slider
                    value={minSupport}
                    onChange={(_, val) => setMinSupport(val as number)}
                    min={0.001}
                    max={0.1}
                    step={0.001}
                    sx={{ mb: 3 }}
                  />
                  <Typography variant="body2" sx={{ fontWeight: 500 }}>
                    Min Confidence: {minConfidence}
                  </Typography>
                  <Slider
                    value={minConfidence}
                    onChange={(_, val) => setMinConfidence(val as number)}
                    min={0.1}
                    max={1.0}
                    step={0.05}
                  />
                  <Button
                    variant="contained"
                    fullWidth
                    sx={{
                      mt: 4,
                      py: 1.5,
                      fontWeight: "bold",
                      borderRadius: 2,
                      backgroundColor: "#212121",
                    }}
                    onClick={handleRunFpAnalytics}
                    disabled={loading}
                  >
                    {loading ? (
                      <CircularProgress size={24} color="inherit" />
                    ) : (
                      "GENERATE REPORT"
                    )}
                  </Button>
                </Paper>
              </Grid>

              <Grid size={{ xs: 12, md: 9 }}>
                <Paper
                  elevation={0}
                  sx={{
                    p: 4,
                    height: 500,
                    display: "flex",
                    flexDirection: "column",
                    borderRadius: 3,
                    border: "1px solid #e0e0e0",
                    position: "relative",
                  }}
                >
                  {isZoomed && (
                    <Button
                      variant="contained"
                      size="small"
                      color="secondary"
                      onClick={zoomOut}
                      sx={{
                        position: "absolute",
                        top: 16,
                        right: 16,
                        zIndex: 10,
                        borderRadius: 20,
                      }}
                    >
                      Скинути Зум
                    </Button>
                  )}
                  <Box sx={{ flexGrow: 1, mt: 2, position: "relative" }}>
                    {loading && rules.length === 0 ? (
                      <Skeleton variant="rounded" width="100%" height="100%" />
                    ) : rules.length > 0 ? (
                      <Box
                        sx={{
                          position: "absolute",
                          top: 0,
                          left: 0,
                          right: 0,
                          bottom: 0,
                        }}
                      >
                        <ResponsiveContainer width="100%" height="100%">
                          <ScatterChart
                            margin={{
                              top: 10,
                              right: 20,
                              bottom: 20,
                              left: -20,
                            }}
                            onMouseDown={(e: any) => {
                              if (e) {
                                setRefAreaLeft(e.xValue);
                                setRefAreaBottom(e.yValue);
                              }
                            }}
                            onMouseMove={(e: any) => {
                              if (e && refAreaLeft !== null) {
                                setRefAreaRight(e.xValue);
                                setRefAreaTop(e.yValue);
                              }
                            }}
                            onMouseUp={zoom}
                          >
                            <CartesianGrid
                              strokeDasharray="3 3"
                              stroke="#eeeeee"
                              vertical={false}
                            />
                            <XAxis
                              dataKey="x"
                              type="number"
                              domain={xDomain}
                              allowDataOverflow
                              tickFormatter={(val) =>
                                `${(val * 100).toFixed(0)}%`
                              }
                            />
                            <YAxis
                              dataKey="y"
                              type="number"
                              domain={yDomain}
                              allowDataOverflow
                              tickFormatter={(val) =>
                                `${(val * 100).toFixed(0)}%`
                              }
                            />
                            <ZAxis
                              dataKey="z"
                              type="number"
                              range={[60, 500]}
                              name="Lift"
                            />
                            <RechartsTooltip
                              content={<CustomTooltip />}
                              cursor={{ strokeDasharray: "3 3" }}
                            />
                            <Legend
                              verticalAlign="top"
                              align="left"
                              wrapperStyle={{ paddingBottom: 20 }}
                            />
                            <Scatter
                              name="Цільові (Lift > 2)"
                              data={highLiftData}
                              fill="#2e7d32"
                              shape="diamond"
                              fillOpacity={0.8}
                              isAnimationActive={false}
                            />
                            <Scatter
                              name="Фонові (Lift ≤ 2)"
                              data={normalLiftData}
                              fill="#bdbdbd"
                              shape="circle"
                              fillOpacity={0.5}
                              isAnimationActive={false}
                            />
                            {refAreaLeft !== null &&
                            refAreaRight !== null &&
                            refAreaTop !== null &&
                            refAreaBottom !== null ? (
                              <ReferenceArea
                                x1={refAreaLeft}
                                x2={refAreaRight}
                                y1={refAreaBottom}
                                y2={refAreaTop}
                                fill="#1976d2"
                                fillOpacity={0.1}
                              />
                            ) : null}
                          </ScatterChart>
                        </ResponsiveContainer>
                      </Box>
                    ) : (
                      <Typography
                        color="textSecondary"
                        align="center"
                        sx={{ mt: 10 }}
                      >
                        Немає розрахованих асоціативних зв'язків
                      </Typography>
                    )}
                  </Box>
                </Paper>
              </Grid>

              <Grid size={{ xs: 12 }}>
                <Paper
                  elevation={0}
                  sx={{
                    p: 0,
                    borderRadius: 3,
                    border: "1px solid #e0e0e0",
                    overflow: "hidden",
                  }}
                >
                  <Box
                    sx={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      p: 3,
                      borderBottom: "1px solid #e0e0e0",
                      backgroundColor: "#fafafa",
                    }}
                  >
                    <Typography variant="subtitle1" sx={{ fontWeight: "bold" }}>
                      Таблиця асоціативних правил (Усі {rules.length})
                    </Typography>
                    <Button
                      variant="outlined"
                      size="small"
                      onClick={handleExportCSV}
                      sx={{ borderRadius: 2, fontWeight: "bold" }}
                    >
                      EXPORT TO CSV
                    </Button>
                  </Box>
                  {rules.length > 0 ? (
                    <TableContainer sx={{ maxHeight: 500 }}>
                      <Table stickyHeader size="medium">
                        <TableHead>
                          <TableRow>
                            <TableCell>Antecedent</TableCell>
                            <TableCell>Consequent</TableCell>
                            <TableCell align="right">Support</TableCell>
                            <TableCell align="right">Confidence</TableCell>
                            <TableCell align="right">Lift</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {allChartData.map((rule, index) => (
                            <TableRow key={index} hover>
                              <TableCell sx={{ color: "#616161" }}>
                                {rule.name.split(" -> ")[0]}
                              </TableCell>
                              <TableCell
                                sx={{ fontWeight: "bold", color: "#212121" }}
                              >
                                {rule.name.split(" -> ")[1]}
                              </TableCell>
                              <TableCell align="right">
                                {(rule.x * 100).toFixed(2)}%
                              </TableCell>
                              <TableCell align="right">
                                {(rule.y * 100).toFixed(1)}%
                              </TableCell>
                              <TableCell align="right">
                                <Box
                                  component="span"
                                  sx={{
                                    backgroundColor:
                                      rule.z > 2 ? "#e8f5e9" : "transparent",
                                    color: rule.z > 2 ? "#2e7d32" : "#757575",
                                    fontWeight: rule.z > 2 ? "bold" : "normal",
                                    px: 1,
                                    borderRadius: 1,
                                  }}
                                >
                                  {rule.z.toFixed(2)}
                                </Box>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  ) : (
                    <Typography
                      color="textSecondary"
                      align="center"
                      sx={{ py: 5 }}
                    >
                      Немає даних
                    </Typography>
                  )}
                </Paper>
              </Grid>
            </Grid>
          </Box>
        )}


        {currentView === "RFM Segmentation" && (
          <Box sx={{ maxWidth: 1400, margin: "0 auto" }}>
            <Box sx={{ mb: 4 }}>
              <Typography
                variant="h5"
                sx={{ fontWeight: 800, color: "#212121", mb: 1 }}
              >
                Сегментація клієнтської бази (RFM Clustering)
              </Typography>
              <Typography
                variant="body1"
                sx={{ color: "#616161", maxWidth: 900 }}
              >
                2D-візуалізація кластерів клієнтів (Bubble Chart).{" "}
                <strong>Вісь X</strong> — Recency (Давність),{" "}
                <strong>Вісь Y</strong> — Frequency (Частота).{" "}
                <strong>Розмір бульбашки</strong> відповідає за Monetary (суму
                витрат).
              </Typography>
            </Box>
            <Grid container spacing={3}>
              <Grid size={{ xs: 12 }}>
                <Paper
                  elevation={0}
                  sx={{
                    p: 4,
                    borderRadius: 3,
                    border: "1px solid #e0e0e0",
                    backgroundColor: "#ffffff",
                  }}
                >
                  <Box
                    sx={{
                      display: "flex",
                      justifyContent: "space-between",
                      mb: 3,
                    }}
                  >
                    <Typography
                      variant="subtitle1"
                      sx={{
                        fontWeight: "bold",
                        color: "#757575",
                        textTransform: "uppercase",
                      }}
                    >
                      K-Means Distribution
                    </Typography>
                    <Box sx={{ display: "flex", gap: 2 }}>
                      <Button
                        variant="outlined"
                        color="primary"
                        onClick={fetchRFMResults}
                        disabled={loading}
                        sx={{ px: 3 }}
                      >
                        Завантажити з БД
                      </Button>
                      <Button
                        variant="contained"
                        color="primary"
                        onClick={handleRunRfmPipeline}
                        disabled={loading}
                        disableElevation
                        sx={{ px: 3 }}
                      >
                        ЗАПУСТИТИ ML PIPELINE
                      </Button>
                    </Box>
                  </Box>
                  {loading ? (
                    <Skeleton variant="rounded" width="100%" height={600} />
                  ) : rfmData.length > 0 ? (
                    <Box
                      sx={{ height: 600, width: "100%", position: "relative" }}
                    >
                      {renderRFMPlot()}
                    </Box>
                  ) : (
                    <Typography
                      color="textSecondary"
                      align="center"
                      sx={{ py: 10 }}
                    >
                      Дані RFM відсутні.
                    </Typography>
                  )}
                </Paper>
              </Grid>
            </Grid>
          </Box>
        )}

        {currentView === "Tenant Settings" && (
          <Box sx={{ maxWidth: 1400, margin: "0 auto" }}>
            <Box sx={{ mb: 4 }}>
              <Typography
                variant="h4"
                sx={{ fontWeight: 800, color: "#212121", mb: 1 }}
              >
                Параметри інтеграції та керування робочим простором
              </Typography>
              <Typography variant="body1" sx={{ color: "#616161" }}>
                Адміністрування шлюзів обміну даними та управління обліковими
                записами аналітиків компанії
              </Typography>
            </Box>

            <Grid container spacing={4} sx={{ alignItems: "stretch" }}>
              <Grid size={{ xs: 12, md: 5 }}>
                <Paper
                  elevation={0}
                  sx={{
                    p: 5,
                    borderRadius: 3,
                    border: "1px solid #e0e0e0",
                    backgroundColor: "#ffffff",
                    height: "100%",
                    minHeight: 380,
                    display: "flex",
                    flexDirection: "column",
                  }}
                >
                  <Typography variant="h5" sx={{ fontWeight: "bold", mb: 2 }}>
                    Ключ API Інтеграції
                  </Typography>
                  <Typography
                    variant="body1"
                    sx={{ color: "#757575", mb: 4, flexGrow: 1 }}
                  >
                    Токен для наскрізної автентифікації десктопного
                    ETL-колектора
                  </Typography>

                  <Box
                    sx={{
                      backgroundColor: "#f4f6f8",
                      p: 3,
                      borderRadius: 2,
                      border: "1px solid #e0e0e0",
                      mb: 3,
                    }}
                  >
                    <Typography
                      variant="body1"
                      sx={{
                        fontFamily: "Consolas, monospace",
                        fontWeight: "bold",
                        color: "#A4262C",
                        wordBreak: "break-all",
                      }}
                    >
                      {tenantKey || "Завантаження ключа..."}
                    </Typography>
                  </Box>

                  <Button
                    variant="contained"
                    fullWidth
                    color="primary"
                    onClick={copyToClipboard}
                    disabled={!tenantKey}
                    sx={{
                      fontWeight: "bold",
                      py: 1.5,
                      mb: 4,
                      fontSize: "1rem",
                    }}
                  >
                    КОПІЮВАТИ ТОКЕН БЕЗПЕКИ
                  </Button>

                  <Divider sx={{ my: 2 }} />
                  <Typography
                    variant="subtitle1"
                    sx={{ fontWeight: "bold", color: "#1976d2", mb: 1 }}
                  >
                    Синхронізація (CRISP-DM):
                  </Typography>
                  <Typography
                    variant="body2"
                    component="p"
                    sx={{ color: "#616161", lineHeight: 1.6 }}
                  >
                    Вставте цей ключ у вікно локального колектора Tkinter,
                    налаштуйте SQL-запит із фільтрацією клієнтів (Entity
                    sampling) та запустіть міграцію для наповнення бази даних
                  </Typography>
                </Paper>
              </Grid>

              <Grid size={{ xs: 12, md: 7 }}>
                <Paper
                  elevation={0}
                  sx={{
                    p: 5,
                    borderRadius: 3,
                    border: "1px solid #e0e0e0",
                    backgroundColor: "#ffffff",
                    height: "100%",
                    minHeight: 380,
                    display: "flex",
                    flexDirection: "column",
                  }}
                >
                  <Typography variant="h5" sx={{ fontWeight: "bold", mb: 2 }}>
                    Реєстрація бізнес-аналітиків
                  </Typography>
                  <Typography variant="body1" sx={{ color: "#757575", mb: 4 }}>
                    Створення нових облікових записів з обмеженими правами
                    доступу до аналітичного рушія системи
                  </Typography>
                  
                  <Box
                    component="form"
                    onSubmit={handleCreateAnalyst}
                    sx={{ display: "flex", flexWrap: "wrap", gap: 3, mb: 4 }}
                  >
                    <input
                      type="email"
                      placeholder="Email аналітика"
                      value={newAnalystEmail}
                      onChange={(e) => setNewAnalystEmail(e.target.value)}
                      style={{
                        flex: "1 1 220px",
                        padding: "16px",
                        borderRadius: "8px",
                        border: "1px solid #d1d1d1",
                        fontSize: "1rem",
                      }}
                    />
                    <input
                      type="password"
                      placeholder="Тимчасовий пароль"
                      value={newAnalystPassword}
                      onChange={(e) => setNewAnalystPassword(e.target.value)}
                      style={{
                        flex: "1 1 220px",
                        padding: "16px",
                        borderRadius: "8px",
                        border: "1px solid #d1d1d1",
                        fontSize: "1rem",
                      }}
                    />
                    <Button
                      type="submit"
                      variant="contained"
                      sx={{
                        flex: "1 1 140px",
                        backgroundColor: "#212121",
                        color: "white",
                        fontWeight: "bold",
                        px: 4,
                        py: 1.5,
                        borderRadius: 2,
                        fontSize: "1rem",
                        "&:hover": { backgroundColor: "#333" },
                      }}
                    >
                      ДОДАТИ
                    </Button>
                  </Box>

                  <Box
                    sx={{
                      p: 3,
                      backgroundColor: "#f9fbe7",
                      borderRadius: 2,
                      borderLeft: "4px solid #4caf50",
                    }}
                  >
                    <Typography
                      variant="body2"
                      sx={{ color: "#2e7d32", fontWeight: 500 }}
                    >
                      Користувачі з роллю "Business Analyst" можуть запускати
                      моделі машинного навчання та переглядати звіти, але не
                      мають доступу до цієї панелі налаштувань tenant
                    </Typography>
                  </Box>
                </Paper>
              </Grid>

              <Grid size={{ xs: 12 }}>
                <Paper
                  elevation={0}
                  sx={{
                    borderRadius: 3,
                    border: "1px solid #e0e0e0",
                    overflow: "hidden",
                  }}
                >
                  <Box
                    sx={{
                      p: 3,
                      backgroundColor: "#fafafa",
                      borderBottom: "1px solid #e0e0e0",
                    }}
                  >
                    <Typography variant="h6" sx={{ fontWeight: "bold" }}>
                      Управління доступами аналітиків компанії
                    </Typography>
                  </Box>
                  <TableContainer sx={{ maxHeight: 400 }}>
                    <Table size="medium" stickyHeader>
                      <TableHead>
                        <TableRow>
                          <TableCell
                            sx={{
                              fontWeight: 600,
                              color: "#757575",
                              fontSize: "1rem",
                            }}
                          >
                            ID користувача
                          </TableCell>
                          <TableCell
                            sx={{
                              fontWeight: 600,
                              color: "#757575",
                              fontSize: "1rem",
                            }}
                          >
                            Електронна пошта (логін)
                          </TableCell>
                          <TableCell
                            sx={{
                              fontWeight: 600,
                              color: "#757575",
                              fontSize: "1rem",
                            }}
                          >
                            Роль у системі
                          </TableCell>
                          <TableCell
                            align="right"
                            sx={{
                              fontWeight: 600,
                              color: "#757575",
                              fontSize: "1rem",
                              pr: 4,
                            }}
                          >
                            Дії
                          </TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {analysts.length > 0 ? (
                          analysts.map((analyst) => (
                            <TableRow key={analyst.id} hover>
                              <TableCell
                                sx={{
                                  fontFamily: "Consolas, monospace",
                                  color: "#616161",
                                  fontSize: "1rem",
                                }}
                              >
                                #{analyst.id}
                              </TableCell>
                              <TableCell
                                sx={{
                                  fontWeight: 600,
                                  color: "#212121",
                                  fontSize: "1rem",
                                }}
                              >
                                {analyst.email}
                              </TableCell>
                              <TableCell>
                                <Box
                                  component="span"
                                  sx={{
                                    backgroundColor: "#e3f2fd",
                                    color: "#1976d2",
                                    px: 2,
                                    py: 1,
                                    borderRadius: 1,
                                    fontSize: "0.9rem",
                                    fontWeight: 600,
                                  }}
                                >
                                  Business Analyst
                                </Box>
                              </TableCell>
                              <TableCell align="right" sx={{ pr: 3 }}>
                                <Button
                                  size="medium"
                                  color="error"
                                  variant="outlined"
                                  onClick={() =>
                                    handleDeleteAnalyst(analyst.id)
                                  }
                                  sx={{
                                    fontWeight: "bold",
                                    borderWidth: 2,
                                    "&:hover": { borderWidth: 2 },
                                  }}
                                >
                                  Анулювати доступ
                                </Button>
                              </TableCell>
                            </TableRow>
                          ))
                        ) : (
                          <TableRow>
                            <TableCell
                              colSpan={4}
                              align="center"
                              sx={{ py: 6, color: "#9e9e9e", fontSize: "1rem" }}
                            >
                              Жодного аналітика ще не зареєстровано у цьому
                              робочому просторі
                            </TableCell>
                          </TableRow>
                        )}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </Paper>
              </Grid>
            </Grid>
          </Box>
        )}
      </Box>
    </Box>
  );
};
