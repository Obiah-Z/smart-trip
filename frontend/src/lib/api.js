export const API_BASE = import.meta.env.VITE_API_BASE || ''

function buildUrl(path) {
  try {
    return new URL(path, API_BASE).toString()
  } catch (error) {
    return `${API_BASE}${path}`
  }
}

export function resolveAssetUrl(path) {
  if (!path) return ''
  return buildUrl(path)
}

async function request(path, options = {}) {
  const response = await fetch(buildUrl(path), {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  })

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || 'Request failed')
  }

  return response.json()
}

export function createDemoPlan(payload) {
  return request('/api/demo/plan', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function listMemory(userId) {
  return request(`/api/memory/${encodeURIComponent(userId)}`)
}

export function upsertMemory(userId, payload) {
  return request(`/api/memory/${encodeURIComponent(userId)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function listSkills() {
  return request('/api/skills')
}

export function listSessions(params = {}) {
  const query = new URLSearchParams()
  if (params.userId) query.set('user_id', params.userId)
  if (params.limit) query.set('limit', String(params.limit))
  const suffix = query.toString() ? `?${query.toString()}` : ''
  return request(`/api/demo/sessions${suffix}`)
}

export function getSession(sessionId) {
  return request(`/api/demo/session/${encodeURIComponent(sessionId)}`)
}

export function deleteSession(sessionId) {
  return request(`/api/demo/session/${encodeURIComponent(sessionId)}`, {
    method: 'DELETE',
  })
}
