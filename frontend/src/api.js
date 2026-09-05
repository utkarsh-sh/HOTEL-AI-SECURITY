const API_BASE_URL = "http://127.0.0.1:8000";


async function request(endpoint) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`);

  if (!response.ok) {
    throw new Error(
      `API request failed: ${response.status} ${response.statusText}`
    );
  }

  return response.json();
}


async function postRequest(endpoint, body = {}) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;

    try {
      const errorData = await response.json();

      if (errorData.detail) {
        message = errorData.detail;
      }
    } catch {
      // Keep the default HTTP error message.
    }

    throw new Error(`API request failed: ${message}`);
  }

  return response.json();
}


export async function getCameras() {
  return request("/cameras");
}


export async function getEvents() {
  return request("/events");
}


export async function getHealth() {
  return request("/health");
}


export async function getCameraHealth(cameraId) {
  return request(`/cameras/${cameraId}/health`);
}


export async function getEvent(eventId) {
  return request(`/events/${eventId}`);
}


// ==========================================
// EVENT OPERATOR ACTIONS
// ==========================================

export async function acknowledgeEvent(eventId) {
  return postRequest(`/events/${eventId}/acknowledge`);
}


export async function dispatchEvent(eventId) {
  return postRequest(`/events/${eventId}/dispatch`);
}


export async function resolveEvent(eventId, resolution = null) {
  return postRequest(`/events/${eventId}/resolve`, {
    resolution,
  });
}


export async function markFalsePositive(eventId, resolution = null) {
  return postRequest(`/events/${eventId}/false-positive`, {
    resolution,
  });
}

export async function getAuditLogs() {
  return request("/audit-logs");
}

export async function getEventAuditLogs(eventId) {
  const result = await getAuditLogs();

  return {
    total: result.logs.filter(
      (log) =>
        log.entity_type === "event" &&
        String(log.entity_id) === String(eventId)
    ).length,

    logs: result.logs.filter(
      (log) =>
        log.entity_type === "event" &&
        String(log.entity_id) === String(eventId)
    ),
  };
}