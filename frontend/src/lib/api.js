const TOKEN_KEY = 'edu_sahaya_token'
export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (t) => (t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY))

function message(detail) {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d) => d.msg.replace('Value error, ', '')).join('. ')
  return 'Something went wrong. Please try again.'
}

export async function api(path, { method = 'GET', body } = {}) {
  const token = getToken()
  const res = await fetch(`/api${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token && { Authorization: `Bearer ${token}` }) },
    body: body && JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(message(data.detail))
  return data
}

export async function fetchBlob(path) {
  const res = await fetch(`/api${path}`, { headers: { Authorization: `Bearer ${getToken()}` } })
  if (!res.ok) throw new Error('Could not load the file')
  return res.blob()
}

// XMLHttpRequest is used because fetch cannot report upload progress.
export function uploadFile(path, file, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `/api${path}`)
    xhr.setRequestHeader('Authorization', `Bearer ${getToken()}`)
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(Math.round((e.loaded / e.total) * 100))
    xhr.onload = () => {
      const data = JSON.parse(xhr.responseText || '{}')
      xhr.status < 300 ? resolve(data) : reject(new Error(message(data.detail)))
    }
    xhr.onerror = () => reject(new Error('Network error. Check your connection and try again.'))
    const form = new FormData()
    form.append('file', file)
    xhr.send(form)
  })
}
