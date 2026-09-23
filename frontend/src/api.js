const API_BASE_URL = "http://127.0.0.1:8000";

const TOKEN_KEY = "hotel_security_access_token";
const USER_KEY = "hotel_security_user";

function getAccessToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser() {
  const user = localStorage.getItem(USER_KEY);

  if (!user) {
    return null;
  }

  try {
    return JSON.parse(user);
  } catch {
    localStorage.removeItem(USER_KEY);
    return null;
  }
}

export function isAuthenticated() {
  return Boolean(getAccessToken());
}

export function logout() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

async function request(endpoint) {
  const token = getAccessToken();

  const headers = {};

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(
    `${API_BASE_URL}${endpoint}`,
    {
      headers,
    }
  );

  if (!response.ok) {
    let message =
      `${response.status} ${response.statusText}`;

    try {
      const errorData =
        await response.json();

      if (errorData.detail) {
        message = errorData.detail;
      }
    } catch {
      // Ignore JSON parsing errors.
    }

    throw new Error(
      `API request failed: ${message}`
    );
  }

  return response.json();
}

async function postRequest(
  endpoint,
  body = {}
) {
  const token = getAccessToken();

  const headers = {
    "Content-Type": "application/json",
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(
    `${API_BASE_URL}${endpoint}`,
    {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    }
  );

  if (!response.ok) {
    let message =
      `${response.status} ${response.statusText}`;

    try {
      const errorData =
        await response.json();

      if (errorData.detail) {
        message = errorData.detail;
      }
    } catch {
      // Ignore JSON parsing errors.
    }

    throw new Error(
      `API request failed: ${message}`
    );
  }

  return response.json();
}

export async function login(
  username,
  password
) {
  const formData =
    new URLSearchParams();

  formData.append(
    "username",
    username
  );

  formData.append(
    "password",
    password
  );

  const response = await fetch(
    `${API_BASE_URL}/login`,
    {
      method: "POST",
      headers: {
        "Content-Type":
          "application/x-www-form-urlencoded",
      },
      body: formData.toString(),
    }
  );

  if (!response.ok) {
    let message =
      `${response.status} ${response.statusText}`;

    try {
      const errorData =
        await response.json();

      if (errorData.detail) {
        message = errorData.detail;
      }
    } catch {
      // Ignore JSON parsing errors.
    }

    throw new Error(
      `Login failed: ${message}`
    );
  }

  const data =
    await response.json();

  localStorage.setItem(
    TOKEN_KEY,
    data.access_token
  );

  localStorage.setItem(
    USER_KEY,
    JSON.stringify(data.user)
  );

  return data;
}

export async function getCameras() {
  return request("/cameras");
}

export async function getEventQuality() {
  return request("/event-quality");
}

export async function getEvents() {
  return request("/events");
}

export async function getHealth() {
  return request("/health");
}

export async function getCameraHealth(
  cameraId
) {
  return request(
    `/cameras/${cameraId}/health`
  );
}

/*
 * Camera fleet health summary.
 *
 * Returns aggregate health information
 * for all registered cameras.
 */
export async function getCameraHealthSummary() {
  return request(
    "/cameras/health/summary"
  );
}

export async function getEvent(
  eventId
) {
  return request(
    `/events/${eventId}`
  );
}

export async function acknowledgeEvent(
  eventId
) {
  return postRequest(
    `/events/${eventId}/acknowledge`
  );
}

export async function dispatchEvent(
  eventId
) {
  return postRequest(
    `/events/${eventId}/dispatch`
  );
}

export async function resolveEvent(
  eventId,
  resolution = null
) {
  return postRequest(
    `/events/${eventId}/resolve`,
    {
      resolution,
    }
  );
}

export async function markFalsePositive(
  eventId,
  resolution = null
) {
  return postRequest(
    `/events/${eventId}/false-positive`,
    {
      resolution,
    }
  );
}

export async function getAuditLogs() {
  return request(
    "/audit-logs"
  );
}

export async function getEventAuditLogs(
  eventId
) {
  const result =
    await getAuditLogs();

  const logs =
    result.logs.filter(
      (log) =>
        log.entity_type === "event" &&
        String(log.entity_id) ===
          String(eventId)
    );

  return {
    total: logs.length,
    logs,
  };
}

export async function getEventEvidence(
  eventId
) {
  const token =
    getAccessToken();

  const headers = {};

  if (token) {
    headers.Authorization =
      `Bearer ${token}`;
  }

  const response =
    await fetch(
      `${API_BASE_URL}/events/${eventId}/evidence`,
      {
        method: "GET",
        headers,
      }
    );

  if (!response.ok) {
    let message =
      `${response.status} ${response.statusText}`;

    try {
      const errorData =
        await response.json();

      if (errorData.detail) {
        message =
          errorData.detail;
      }
    } catch {
      // Ignore JSON parsing errors.
    }

    throw new Error(
      `Evidence request failed: ${message}`
    );
  }

  return response.blob();
}


// =========================
// NOTIFICATION HISTORY
// =========================

export async function getEventNotifications(
  eventId
) {
  return request(
    `/notifications/event/${eventId}`
  );
}