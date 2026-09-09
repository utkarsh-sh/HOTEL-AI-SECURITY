import { useCallback, useEffect, useMemo, useState } from "react";
import "./App.css";

import {
  login,
  getStoredUser,
  logout,
  getCameras,
  getEvents,
  getHealth,
  acknowledgeEvent,
  dispatchEvent,
  resolveEvent,
  markFalsePositive,
  getEventAuditLogs,
  getCameraHealthSummary,
  getCameraHealth,
  getEventEvidence,
} from "./api";

function App() {
  const [cameras, setCameras] = useState([]);
  const [events, setEvents] = useState([]);
  const [systemHealth, setSystemHealth] = useState(null);
  const [cameraHealthSummary, setCameraHealthSummary] = useState(null);

  const [selectedEvent, setSelectedEvent] = useState(null);
const [selectedCamera, setSelectedCamera] = useState(null);

  // Secure evidence video state
  const [evidenceUrl, setEvidenceUrl] = useState(null);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [evidenceError, setEvidenceError] = useState(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(null);
  const [auditLogs, setAuditLogs] = useState([]);
  const [auditLoading, setAuditLoading] = useState(false);

  // =========================
  // AUTHENTICATION
  // =========================

  const [authUser, setAuthUser] = useState(() => getStoredUser());
  const [loginUsername, setLoginUsername] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState(null);

  async function handleLogin(event) {
    event.preventDefault();

    setLoginLoading(true);
    setLoginError(null);

    try {
      const result = await login(
        loginUsername.trim(),
        loginPassword
      );

      setAuthUser(result.user);
      setLoginPassword("");
      setError(null);
    } catch (err) {
      console.error("Login failed:", err);
      setLoginError(err.message);
    } finally {
      setLoginLoading(false);
    }
  }

  function handleLogout() {
    logout();

    setAuthUser(null);
    setCameras([]);
    setEvents([]);
    setSystemHealth(null);
    setSelectedEvent(null);
    setCameraHealthSummary(null);
    setEvidenceUrl(null);
    setEvidenceError(null);
    setEvidenceLoading(false);
    setAuditLogs([]);
    setError(null);
  }

  // =========================
  // AUDIT HISTORY
  // =========================

  const loadEventAuditLogs = useCallback(async (eventId) => {
    setAuditLoading(true);

    try {
      const result = await getEventAuditLogs(eventId);
      setAuditLogs(result.logs);
    } catch (error) {
      console.error("Failed to load audit logs:", error);
      setAuditLogs([]);
    } finally {
      setAuditLoading(false);
    }
  }, []);

  // =========================
  // SECURE EVIDENCE LOADING
  // =========================

  useEffect(() => {
    let objectUrl = null;
    let cancelled = false;

    async function loadEvidence() {
      if (!selectedEvent?.evidence_path) {
        setEvidenceUrl(null);
        setEvidenceLoading(false);
        setEvidenceError(null);
        return;
      }

      setEvidenceLoading(true);
      setEvidenceError(null);
      setEvidenceUrl(null);

      try {
        const videoBlob = await getEventEvidence(
          selectedEvent.id
        );

        if (cancelled) {
          return;
        }

        objectUrl = URL.createObjectURL(videoBlob);

        setEvidenceUrl(objectUrl);
      } catch (error) {
        if (cancelled) {
          return;
        }

        console.error(
          "Failed to load event evidence:",
          error
        );

        setEvidenceError(error.message);
      } finally {
        if (!cancelled) {
          setEvidenceLoading(false);
        }
      }
    }

    loadEvidence();

    return () => {
      cancelled = true;

      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [selectedEvent]);

  // =========================
  // DASHBOARD DATA
  // =========================

  const openCamera = async (camera) => {
    try {
      const health = await getCameraHealth(camera.camera_id);
      setSelectedCamera({
        ...camera,
        health,
      });
    } catch (error) {
      setSelectedCamera({
        ...camera,
        health: {
          error: error.message,
        },
      });
    }
  };

  const closeCamera = () => {
    setSelectedCamera(null);
  };

  async function loadDashboardData() {
    try {
      setError(null);

    const [
      cameraData,
      eventData,
      healthData,
      cameraHealthSummaryData,
    ] = await Promise.all([
      getCameras(),
      getEvents(),
      getHealth(),
      getCameraHealthSummary(),
    ]);

    setCameras(cameraData.cameras || []);
    setEvents(eventData.events || []);
    setSystemHealth(healthData);
    setCameraHealthSummary(cameraHealthSummaryData);
  } catch (err) {
    console.error("Dashboard API error:", err);
    setError(err.message);
  } finally {
    setLoading(false);
  }
}

  useEffect(() => {
    if (!authUser) {
      setLoading(false);
      return;
    }

    loadDashboardData();

    const interval = setInterval(
      loadDashboardData,
      5000
    );

    return () => clearInterval(interval);
  }, [authUser]);

  // =========================
  // DASHBOARD CALCULATIONS
  // =========================

  const onlineCameras = useMemo(() => {
    return cameras.filter(
      (camera) => camera.status === "ONLINE"
    );
  }, [cameras]);

  const fleetHealth = useMemo(() => {
  const summary = cameraHealthSummary || {};

  const total = Number(
    summary.total ??
      summary.total_cameras ??
      cameras.length
  );

  const online = Number(
    summary.online ??
      summary.online_cameras ??
      onlineCameras.length
  );

  const offline = Number(
    summary.offline ??
      summary.offline_cameras ??
      cameras.length - onlineCameras.length
  );

  const calculatedPercent =
    total > 0
      ? (online / total) * 100
      : 0;

  const healthPercent = Number(
    summary.health_percent ??
      summary.health_percentage ??
      calculatedPercent
  );

  return {
    total,
    online,
    offline,
    healthPercent: Number.isFinite(healthPercent)
      ? Math.max(0, Math.min(100, healthPercent))
      : 0,
  };
}, [
  cameraHealthSummary,
  cameras.length,
  onlineCameras.length,
]);

  const activeEvents = useMemo(() => {
    return events.filter((event) =>
      [
        "NEW",
        "ACKNOWLEDGED",
        "DISPATCHED",
      ].includes(event.status)
    );
  }, [events]);

  const highSeverityEvents = useMemo(() => {
    return activeEvents.filter(
      (event) => event.severity === "HIGH"
    );
  }, [activeEvents]);

  const recentEvents = events.slice(0, 5);

  // =========================
  // FORMATTERS
  // =========================

  function formatTime(timestamp) {
    if (!timestamp) {
      return "--:--";
    }

    const date = new Date(timestamp);

    return date.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }

  function formatDate(timestamp) {
    if (!timestamp) {
      return "Unknown";
    }

    const date = new Date(timestamp);

    return date.toLocaleString([], {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }

  function getSeverityClass(severity) {
    if (severity === "HIGH") {
      return "high";
    }

    if (severity === "MEDIUM") {
      return "medium";
    }

    return "low";
  }

  // =========================
  // EVENT MODAL
  // =========================

  const openEvent = (event) => {
    setSelectedEvent(event);
    setEvidenceUrl(null);
    setEvidenceError(null);
    setEvidenceLoading(false);
    loadEventAuditLogs(event.id);
  };

  const closeEvent = () => {
    setSelectedEvent(null);
    setEvidenceUrl(null);
    setEvidenceError(null);
    setEvidenceLoading(false);
    setAuditLogs([]);
  };

  // =========================
  // EVENT ACTIONS
  // =========================

  async function performEventAction(
    action,
    eventId
  ) {
    try {
      setActionLoading(`${action}-${eventId}`);
      setError(null);

      let response;

      if (action === "acknowledge") {
        response = await acknowledgeEvent(eventId);
      }

      if (action === "dispatch") {
        response = await dispatchEvent(eventId);
      }

      if (action === "resolve") {
        const resolution = window.prompt(
          "Enter resolution details:",
          "Security team verified and resolved the event."
        );

        if (resolution === null) {
          return;
        }

        response = await resolveEvent(
          eventId,
          resolution
        );
      }

      if (action === "false-positive") {
        const resolution = window.prompt(
          "Why is this a false positive?",
          "Operator verified that the person was authorized to enter the area."
        );

        if (resolution === null) {
          return;
        }

        response = await markFalsePositive(
          eventId,
          resolution
        );
      }

      if (!response?.event) {
        throw new Error(
          "API did not return the updated event."
        );
      }

      const updatedEvent = response.event;

      setEvents((currentEvents) =>
        currentEvents.map((event) =>
          event.id === updatedEvent.id
            ? updatedEvent
            : event
        )
      );

      setSelectedEvent(updatedEvent);

      await loadEventAuditLogs(eventId);
    } catch (err) {
      console.error(
        "Operator action failed:",
        err
      );

      setError(err.message);
    } finally {
      setActionLoading(null);
    }
  }

  // =========================
  // LOGIN SCREEN
  // =========================

  if (!authUser) {
    return (
      <div className="login-page">
        <div className="login-card">

          <div className="login-brand">

            <div className="login-brand-icon">
              🛡️
            </div>

            <div>
              <h1>Hotel AI</h1>
              <span>SECURITY CENTER</span>
            </div>

          </div>

          <div className="login-heading">

            <p className="login-eyebrow">
              SECURE ACCESS
            </p>

            <h2>
              Security Operations Login
            </h2>

            <p>
              Sign in to access the hotel security
              monitoring console.
            </p>

          </div>

          {loginError && (
            <div className="login-error">

              <strong>
                Authentication failed
              </strong>

              <span>
                {loginError}
              </span>

            </div>
          )}

          <form
            className="login-form"
            onSubmit={handleLogin}
          >

            <label>
              Username

              <input
                type="text"
                value={loginUsername}
                onChange={(event) =>
                  setLoginUsername(
                    event.target.value
                  )
                }
                placeholder="Enter username"
                autoComplete="username"
                required
              />
            </label>

            <label>
              Password

              <input
                type="password"
                value={loginPassword}
                onChange={(event) =>
                  setLoginPassword(
                    event.target.value
                  )
                }
                placeholder="Enter password"
                autoComplete="current-password"
                required
              />
            </label>

            <button
              type="submit"
              className="login-button"
              disabled={loginLoading}
            >
              {loginLoading
                ? "Signing in..."
                : "Sign In"}
            </button>

          </form>

          <div className="login-notice">
            Authorized hotel security personnel only.
          </div>

          <div className="login-footer">
            Hotel AI Security System
          </div>

        </div>
      </div>
    );
  }

  // =========================
  // MAIN DASHBOARD
  // =========================

  return (
    <div className="app">
  {selectedCamera && (
    <div className="camera-detail-modal-overlay" onClick={closeCamera}>
      <div
        className="camera-detail-modal"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="camera-detail-title"
      >
        <div className="camera-detail-header">
          <div>
            <h2 id="camera-detail-title">Camera Health Details</h2>
            <p className="camera-detail-location">
              {selectedCamera.name || "Unnamed Camera"}
              {selectedCamera.location ? " - " + selectedCamera.location : ""}
            </p>
          </div>

          <button
            type="button"
            className="camera-detail-close"
            onClick={closeCamera}
            aria-label="Close camera health details"
          >
            X
          </button>
        </div>

        {selectedCamera.health?.error ? (
          <div className="camera-detail-error">
            Failed to load camera health: {selectedCamera.health.error}
          </div>
        ) : (
          <>
            <div className="camera-detail-status-row">
              <span className="camera-detail-status">
                {selectedCamera.health?.status || selectedCamera.status || "UNKNOWN"}
              </span>
            </div>

            <div className="camera-detail-grid">
              <div className="camera-detail-item">
                <span>Camera ID</span>
                <strong>{selectedCamera.camera_id || "--"}</strong>
              </div>

              <div className="camera-detail-item">
                <span>Status</span>
                <strong>
                  {selectedCamera.health?.status || selectedCamera.status || "--"}
                </strong>
              </div>

              <div className="camera-detail-item">
                <span>FPS</span>
                <strong>
                  {selectedCamera.health?.fps ?? selectedCamera.fps ?? "--"}
                </strong>
              </div>

              <div className="camera-detail-item">
                <span>Resolution</span>
                <strong>
                  {selectedCamera.health?.width && selectedCamera.health?.height
                    ? `${selectedCamera.health.width} x ${selectedCamera.health.height}`
                    : selectedCamera.width && selectedCamera.height
                    ? `${selectedCamera.width} x ${selectedCamera.height}`
                    : "--"}
                </strong>
              </div>

              <div className="camera-detail-item">
                <span>Consecutive Failures</span>
                <strong>
                  {selectedCamera.health?.consecutive_failures ??
                    selectedCamera.consecutive_failures ??
                    0}
                </strong>
              </div>

              <div className="camera-detail-item">
                <span>Last Seen</span>
                <strong>
                  {selectedCamera.health?.last_seen ||
                    selectedCamera.last_seen ||
                    "--"}
                </strong>
              </div>
            </div>

            <div className="camera-detail-events">
              <h3>Camera Information</h3>

              <div className="camera-detail-event">
                <span>Last Error</span>
                <strong>
                  {selectedCamera.health?.last_error ||
                    selectedCamera.last_error ||
                    "None"}
                </strong>
              </div>
            </div>
          </>
        )}

        <div className="camera-detail-footer">
          <button type="button" onClick={closeCamera}>
            Close
          </button>
        </div>
      </div>
    </div>
  )}


      {/* =========================
          SIDEBAR
      ========================= */}

      <aside className="sidebar">

        <div className="brand">

          <div className="brand-icon">
            🛡️
          </div>

          <div>
            <h1>Hotel AI</h1>
            <span>SECURITY CENTER</span>
          </div>

        </div>

        <nav className="navigation">

          <button className="nav-item active">
            <span>▣</span>
            Dashboard
          </button>

          <button className="nav-item">
            <span>◉</span>
            Cameras
          </button>

          <button className="nav-item">
            <span>⚠</span>
            Security Events
          </button>

          <button className="nav-item">
            <span>◷</span>
            Event History
          </button>

          <button className="nav-item">
            <span>⚙</span>
            Settings
          </button>

        </nav>

        <div className="sidebar-bottom">

          <div className="system-status">

            <span
              className={
                systemHealth
                  ? "status-dot"
                  : "status-dot offline"
              }
            />

            <div>

              <strong>
                {systemHealth
                  ? "System Online"
                  : "System Offline"}
              </strong>

              <small>
                {systemHealth
                  ? "All core services operational"
                  : "Backend unavailable"}
              </small>

            </div>

          </div>

        </div>

      </aside>

      {/* =========================
          MAIN CONTENT
      ========================= */}

      <main className="main-content">

        <header className="topbar">

          <div>

            <p className="eyebrow">
              SECURITY OPERATIONS
            </p>

            <h2>
              Security Dashboard
            </h2>

          </div>

          <div className="operator">

            <div className="operator-avatar">
              SO
            </div>

            <div>

              <strong>
                {authUser.full_name}
              </strong>

              <span>
                {authUser.role.replaceAll(
                  "_",
                  " "
                )}
              </span>

            </div>

            <button
              className="logout-button"
              onClick={handleLogout}
            >
              Logout
            </button>

          </div>

        </header>

        {/* =========================
            API ERROR
        ========================= */}

        {error && (
          <div className="api-error">

            <strong>
              Backend connection error
            </strong>

            <span>
              {error}
            </span>

          </div>
        )}

        {/* =========================
            SYSTEM BANNER
        ========================= */}

        <section className="system-banner">

          <div className="system-banner-left">

            <div className="live-indicator">

              <span></span>
              LIVE

            </div>

            <div>

              <strong>
                AI CCTV Monitoring Active
              </strong>

              <p>
                AI-assisted monitoring is currently
                processing connected camera feeds.
              </p>

            </div>

          </div>

          <div className="system-time">

            <span>
              API STATUS
            </span>

            <strong>
              {loading
                ? "Connecting..."
                : systemHealth
                  ? "Connected"
                  : "Offline"}
            </strong>

          </div>

        </section>

        {/* =========================
            STATISTICS
        ========================= */}

        <section className="stats-grid">

          <div className="stat-card">

            <div className="stat-header">

              <span>
                Connected Cameras
              </span>

              <span className="stat-icon">
                ◉
              </span>

            </div>

            <strong className="stat-number">
              {onlineCameras.length}
            </strong>

            <div className="stat-footer success">

              <span>●</span>

              {onlineCameras.length} camera
              {onlineCameras.length !== 1
                ? "s"
                : ""}{" "}
              online

            </div>

          </div>

          <div className="stat-card">

            <div className="stat-header">

              <span>
                Active Alerts
              </span>

              <span className="stat-icon warning">
                ⚠
              </span>

            </div>

            <strong className="stat-number">
              {activeEvents.length}
            </strong>

            <div className="stat-footer">

              {activeEvents.length === 0
                ? "No active alerts"
                : "Requires operator attention"}

            </div>

          </div>

          <div className="stat-card">

            <div className="stat-header">

              <span>
                High Severity
              </span>

              <span className="stat-icon danger">
                !
              </span>

            </div>

            <strong className="stat-number">
              {highSeverityEvents.length}
            </strong>

            <div className="stat-footer danger-text">
              Requires immediate attention
            </div>

          </div>

          <div className="stat-card">

            <div className="stat-header">

              <span>
                Total Events
              </span>

              <span className="stat-icon purple">
                ◈
              </span>

            </div>

            <strong className="stat-number">
              {events.length}
            </strong>

            <div className="stat-footer">
              Events stored in database
            </div>

          </div>

        </section>

        {/* =========================
            CAMERA FLEET HEALTH
        ========================= */}

        <section className="fleet-health-section">

          <div className="panel fleet-health-panel">

            <div className="panel-header">

              <div>
                <p className="panel-label">
                  RELIABILITY
                </p>

                <h3>
                  Camera Fleet Health
                </h3>
              </div>

              <div className="fleet-health-badge">
                <span></span>
                {fleetHealth.healthPercent.toFixed(0)}% Healthy
              </div>

            </div>

            <div className="fleet-health-summary">

              <div className="fleet-health-stat">
                <span>Total Cameras</span>
                <strong>{fleetHealth.total}</strong>
              </div>

              <div className="fleet-health-stat online">
                <span>Online</span>
                <strong>{fleetHealth.online}</strong>
              </div>

              <div className="fleet-health-stat offline">
                <span>Offline</span>
                <strong>{fleetHealth.offline}</strong>
              </div>

              <div className="fleet-health-stat health-percent">
                <span>Fleet Health</span>
                <strong>
                  {fleetHealth.healthPercent.toFixed(0)}%
                </strong>
              </div>

            </div>

            <div className="fleet-camera-list">

              {cameras.length === 0 ? (
                <div className="fleet-health-empty">
                  No cameras registered.
                </div>
              ) : (
                cameras.map((camera) => {
                  const isOnline = camera.status === "ONLINE";

                  const resolution =
                    camera.width && camera.height
                      ? `${camera.width} × ${camera.height}`
                      : "--";

                  return (
                    <div
                      className={`fleet-camera-row ${
                        isOnline ? "" : "offline"
                      }`}
                      key={camera.camera_id}
                      onClick={() => openCamera(camera)}
                      onKeyDown={(event) => {
                        if (
                          event.key === "Enter" ||
                          event.key === " "
                        ) {
                          event.preventDefault();
                          openCamera(camera);
                        }
                      }}
                      role="button"
                      tabIndex={0}
                      aria-label={`View health details for ${camera.name}`}
                    >

                      <div className="fleet-camera-main">

                        <div
                          className={
                            isOnline
                              ? "fleet-camera-status online"
                              : "fleet-camera-status offline"
                          }
                        >
                          <span></span>
                          {camera.status}
                        </div>

                        <div>

                          <strong>
                            {camera.name}
                          </strong>

                          <span>
                            {camera.camera_id} • {camera.location}
                          </span>

                        </div>

                      </div>

                      <div className="fleet-camera-metrics">

                        <div>
                          <span>FPS</span>
                          <strong>
                            {camera.fps != null
                              ? Number(camera.fps).toFixed(1)
                              : "--"}
                          </strong>
                        </div>

                        <div>
                          <span>Resolution</span>
                          <strong>
                            {resolution}
                          </strong>
                        </div>

                        <div>
                          <span>Failures</span>
                          <strong>
                            {camera.consecutive_failures ?? 0}
                          </strong>
                        </div>

                        <div>
                          <span>Last Seen</span>
                          <strong>
                            {camera.last_seen
                              ? formatTime(camera.last_seen)
                              : "Never"}
                          </strong>
                        </div>

                      </div>

                    </div>
                  );
                })
              )}

            </div>

          </div>

        </section>
        {/* =========================
            MAIN GRID
        ========================= */}

        <section className="dashboard-grid">

          {/* CAMERA PANEL */}

          <div className="panel camera-panel">

            <div className="panel-header">

              <div>

                <p className="panel-label">
                  MONITORING
                </p>

                <h3>
                  Camera Feeds
                </h3>

              </div>

              <button className="view-button">
                View All
              </button>

            </div>

            {cameras.length === 0 ? (

              <div className="empty-state">
                No cameras registered.
              </div>

            ) : (

              <div className="camera-card">

                <div className="camera-preview">

                  <div className="camera-overlay">

                    <div className="camera-live">

                      <span></span>
                      LIVE

                    </div>

                    <span className="camera-id">
                      {cameras[0].camera_id}
                    </span>

                  </div>

                  <div className="camera-placeholder">

                    <div className="camera-placeholder-icon">
                      ◉
                    </div>

                    <strong>
                      Camera Feed
                    </strong>

                    <span>
                      Live stream integration coming next
                    </span>

                  </div>

                </div>

                <div className="camera-info">

                  <div>

                    <strong>
                      {cameras[0].name}
                    </strong>

                    <span>
                      {cameras[0].location}
                    </span>

                  </div>

                  <div
                    className={
                      cameras[0].status ===
                      "ONLINE"
                        ? "camera-health"
                        : "camera-health offline"
                    }
                  >

                    <span></span>

                    {cameras[0].status}

                  </div>

                </div>

              </div>

            )}

          </div>

          {/* EVENTS PANEL */}

          <div className="panel events-panel">

            <div className="panel-header">

              <div>

                <p className="panel-label">
                  SECURITY ACTIVITY
                </p>

                <h3>
                  Recent Events
                </h3>

              </div>

              <button className="view-button">
                View All
              </button>

            </div>

            <div className="event-list">

              {recentEvents.length === 0 ? (

                <div className="empty-state">
                  No security events found.
                </div>

              ) : (

                recentEvents.map((event) => (

                  <button
                    className="event-item event-clickable"
                    key={event.id}
                    onClick={() =>
                      openEvent(event)
                    }
                  >

                    <div
                      className={`event-severity ${getSeverityClass(
                        event.severity
                      )}`}
                    >

                      {event.severity === "HIGH"
                        ? "!"
                        : "•"}

                    </div>

                    <div className="event-content">

                      <div className="event-title-row">

                        <strong>
                          {event.event_type}
                        </strong>

                        <span
                          className={
                            event.status ===
                              "RESOLVED" ||
                            event.status ===
                              "FALSE_POSITIVE"
                              ? "event-status resolved-status"
                              : "event-status"
                          }
                        >
                          {event.status}
                        </span>

                      </div>

                      <p>
                        {event.message}
                      </p>

                      <div className="event-meta">

                        <span>
                          {event.camera_id}
                        </span>

                        <span>
                          •
                        </span>

                        <span>
                          {event.zone_name ||
                            "No zone"}
                        </span>

                      </div>

                    </div>

                    <span className="event-time">
                      {formatTime(
                        event.timestamp
                      )}
                    </span>

                  </button>

                ))

              )}

            </div>

          </div>

        </section>

        {/* =========================
            BOTTOM GRID
        ========================= */}

        <section className="bottom-grid">

          <div className="panel health-panel">

            <div className="panel-header">

              <div>

                <p className="panel-label">
                  INFRASTRUCTURE
                </p>

                <h3>
                  System Health
                </h3>

              </div>

            </div>

            <div className="health-list">

              <div className="health-row">

                <div>

                  <strong>
                    FastAPI Backend
                  </strong>

                  <span>
                    REST API service
                  </span>

                </div>

                <div className="health-value">

                  <span></span>

                  {systemHealth
                    ? "Operational"
                    : "Offline"}

                </div>

              </div>

              <div className="health-row">

                <div>

                  <strong>
                    Event Database
                  </strong>

                  <span>
                    SQLite storage
                  </span>

                </div>

                <div className="health-value">

                  <span></span>
                  Operational

                </div>

              </div>

              <div className="health-row">

                <div>

                  <strong>
                    Evidence Recorder
                  </strong>

                  <span>
                    Event video capture
                  </span>

                </div>

                <div className="health-value">

                  <span></span>
                  Operational

                </div>

              </div>

            </div>

          </div>

          <div className="panel response-panel">

            <div className="panel-header">

              <div>

                <p className="panel-label">
                  RESPONSE
                </p>

                <h3>
                  Operator Actions
                </h3>

              </div>

            </div>

            <div className="operator-message">

              <div className="message-icon">
                ✓
              </div>

              <div>

                <strong>

                  {activeEvents.length === 0
                    ? "No immediate action required"
                    : `${activeEvents.length} active event${
                        activeEvents.length !== 1
                          ? "s"
                          : ""
                      } require attention`}

                </strong>

                <p>

                  AI detection results should be
                  reviewed and verified by authorized
                  hotel security personnel.

                </p>

              </div>

            </div>

          </div>

        </section>

        <footer className="footer">

          <span>
            Hotel AI Security System
          </span>

          <span>
            Prototype v0.3.0
          </span>

        </footer>

      </main>

      {/* =========================
          EVENT DETAILS MODAL
      ========================= */}

      {selectedEvent && (

        <div
          className="modal-backdrop"
          onClick={closeEvent}
        >

          <div
            className="event-modal"
            onClick={(event) =>
              event.stopPropagation()
            }
          >

            <div className="modal-header">

              <div>

                <p className="panel-label">
                  SECURITY EVENT
                </p>

                <h3>
                  Event #{selectedEvent.id}
                </h3>

              </div>

              <button
                className="modal-close"
                onClick={closeEvent}
                aria-label="Close event details"
              >
                ×
              </button>

            </div>

            {/* =========================
                EVIDENCE
            ========================= */}

            <div className="evidence-section">

              <div className="evidence-header">

                <div>

                  <strong>
                    Evidence Recording
                  </strong>

                  <span>
                    {selectedEvent.evidence_path
                      ? "Recorded event clip"
                      : "No evidence available"}
                  </span>

                </div>

                {selectedEvent.evidence_path && (
                  <span className="evidence-badge">
                    VIDEO
                  </span>
                )}

              </div>

              {selectedEvent.evidence_path ? (

                evidenceLoading ? (

                  <div className="no-evidence">

                    <div className="no-evidence-icon">
                      ◌
                    </div>

                    <strong>
                      Loading evidence...
                    </strong>

                    <span>
                      Securely retrieving the recorded
                      event clip.
                    </span>

                  </div>

                ) : evidenceError ? (

                  <div className="no-evidence">

                    <div className="no-evidence-icon">
                      !
                    </div>

                    <strong>
                      Evidence could not be loaded
                    </strong>

                    <span>
                      {evidenceError}
                    </span>

                  </div>

                ) : evidenceUrl ? (

                  <video
                    className="evidence-video"
                    controls
                    preload="metadata"
                    src={evidenceUrl}
                  >
                    Your browser does not support
                    video playback.
                  </video>

                ) : (

                  <div className="no-evidence">

                    <div className="no-evidence-icon">
                      ◌
                    </div>

                    <strong>
                      Evidence unavailable
                    </strong>

                    <span>
                      The recorded evidence clip
                      could not be loaded.
                    </span>

                  </div>

                )

              ) : (

                <div className="no-evidence">

                  <div className="no-evidence-icon">
                    ◌
                  </div>

                  <strong>
                    Evidence unavailable
                  </strong>

                  <span>
                    This event does not have a
                    recorded evidence clip.
                  </span>

                </div>

              )}

            </div>

            {/* =========================
                EVENT INFORMATION
            ========================= */}

            <div className="event-details-grid">

              <div className="detail-item">

                <span>
                  Event Type
                </span>

                <strong>
                  {selectedEvent.event_type}
                </strong>

              </div>

              <div className="detail-item">

                <span>
                  Severity
                </span>

                <strong
                  className={`severity-text ${getSeverityClass(
                    selectedEvent.severity
                  )}`}
                >
                  {selectedEvent.severity}
                </strong>

              </div>

              <div className="detail-item">

                <span>
                  Status
                </span>

                <strong>
                  {selectedEvent.status}
                </strong>

              </div>

              <div className="detail-item">

                <span>
                  Camera
                </span>

                <strong>
                  {selectedEvent.camera_id}
                </strong>

              </div>

              <div className="detail-item">

                <span>
                  Zone
                </span>

                <strong>
                  {selectedEvent.zone_name ||
                    "Not specified"}
                </strong>

              </div>

              <div className="detail-item">

                <span>
                  Track ID
                </span>

                <strong>
                  {selectedEvent.track_id ??
                    "Not available"}
                </strong>

              </div>

              <div className="detail-item detail-wide">

                <span>
                  Detection Time
                </span>

                <strong>
                  {formatDate(
                    selectedEvent.timestamp
                  )}
                </strong>

              </div>

              <div className="detail-item detail-wide">

                <span>
                  AI Message
                </span>

                <strong>
                  {selectedEvent.message}
                </strong>

              </div>

              <div className="detail-item detail-wide">

                <span>
                  Model Version
                </span>

                <strong>
                  {selectedEvent.model_version ||
                    "Not specified"}
                </strong>

              </div>

              {selectedEvent.resolution && (

                <div className="detail-item detail-wide">

                  <span>
                    Resolution
                  </span>

                  <strong>
                    {selectedEvent.resolution}
                  </strong>

                </div>

              )}

            </div>

            {/* =========================
                AUDIT HISTORY
            ========================= */}

            <div className="audit-history">

              <div className="audit-history-header">

                <span className="audit-history-label">
                  AUDIT HISTORY
                </span>

                <span className="audit-history-count">
                  {auditLogs.length}{" "}
                  {auditLogs.length === 1
                    ? "entry"
                    : "entries"}
                </span>

              </div>

              {auditLoading ? (

                <div className="audit-history-empty">
                  Loading audit history...
                </div>

              ) : auditLogs.length === 0 ? (

                <div className="audit-history-empty">
                  No audit history available.
                </div>

              ) : (

                <div className="audit-history-list">

                  {auditLogs.map((log) => (

                    <div
                      className="audit-history-item"
                      key={log.id}
                    >

                      <div className="audit-history-action">

                        {log.action
                          .replaceAll("_", " ")
                          .replace(
                            "EVENT ",
                            ""
                          )}

                      </div>

                      <div className="audit-history-details">

                        <span>
                          {log.actor}
                        </span>

                        <span>
                          {new Date(
                            log.timestamp
                          ).toLocaleString()}
                        </span>

                      </div>

                      {log.details && (

                        <div className="audit-history-description">
                          {log.details}
                        </div>

                      )}

                    </div>

                  ))}

                </div>

              )}

            </div>

            {/* =========================
                MODAL FOOTER
            ========================= */}

            <div className="modal-footer">

              <div className="modal-notice">
                AI-assisted detection requires
                human verification.
              </div>

              <div className="modal-actions">

                {selectedEvent.status === "NEW" && (
                  <>

                    <button
                      className="modal-action false-positive"
                      disabled={
                        actionLoading ===
                        `false-positive-${selectedEvent.id}`
                      }
                      onClick={() =>
                        performEventAction(
                          "false-positive",
                          selectedEvent.id
                        )
                      }
                    >

                      {actionLoading ===
                      `false-positive-${selectedEvent.id}`
                        ? "Processing..."
                        : "False Positive"}

                    </button>

                    <button
                      className="modal-action acknowledge"
                      disabled={
                        actionLoading ===
                        `acknowledge-${selectedEvent.id}`
                      }
                      onClick={() =>
                        performEventAction(
                          "acknowledge",
                          selectedEvent.id
                        )
                      }
                    >

                      {actionLoading ===
                      `acknowledge-${selectedEvent.id}`
                        ? "Processing..."
                        : "Acknowledge"}

                    </button>

                  </>
                )}

                {selectedEvent.status ===
                  "ACKNOWLEDGED" && (
                  <>

                    <button
                      className="modal-action false-positive"
                      disabled={
                        actionLoading ===
                        `false-positive-${selectedEvent.id}`
                      }
                      onClick={() =>
                        performEventAction(
                          "false-positive",
                          selectedEvent.id
                        )
                      }
                    >

                      {actionLoading ===
                      `false-positive-${selectedEvent.id}`
                        ? "Processing..."
                        : "False Positive"}

                    </button>

                    <button
                      className="modal-action dispatch"
                      disabled={
                        actionLoading ===
                        `dispatch-${selectedEvent.id}`
                      }
                      onClick={() =>
                        performEventAction(
                          "dispatch",
                          selectedEvent.id
                        )
                      }
                    >

                      {actionLoading ===
                      `dispatch-${selectedEvent.id}`
                        ? "Processing..."
                        : "Dispatch"}

                    </button>

                  </>
                )}

                {selectedEvent.status ===
                  "DISPATCHED" && (

                  <button
                    className="modal-action resolve"
                    disabled={
                      actionLoading ===
                      `resolve-${selectedEvent.id}`
                    }
                    onClick={() =>
                      performEventAction(
                        "resolve",
                        selectedEvent.id
                      )
                    }
                  >

                    {actionLoading ===
                    `resolve-${selectedEvent.id}`
                      ? "Processing..."
                      : "Resolve Event"}

                  </button>

                )}

                <button
                  className="close-button"
                  onClick={closeEvent}
                >
                  Close
                </button>

              </div>

            </div>

          </div>

        </div>

      )}

    </div>
  );
}

export default App;
