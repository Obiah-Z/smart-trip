let amapLoaderPromise = null

export async function loadAmap() {
  const mapKey = import.meta.env.VITE_AMAP_JS_KEY
  const securityJsCode = import.meta.env.VITE_AMAP_SECURITY_JSCODE

  if (!mapKey) {
    throw new Error('AMap JS key is not configured')
  }

  if (window.AMap) {
    return window.AMap
  }

  if (securityJsCode) {
    window._AMapSecurityConfig = {
      securityJsCode,
    }
  }

  if (!amapLoaderPromise) {
    amapLoaderPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script')
      script.src = `https://webapi.amap.com/maps?v=2.0&key=${encodeURIComponent(mapKey)}&plugin=AMap.Scale,AMap.ToolBar`
      script.async = true
      script.setAttribute('data-amap-loader', 'true')
      script.onload = () => {
        if (window.AMap) {
          resolve(window.AMap)
          return
        }
        amapLoaderPromise = null
        script.remove()
        reject(new Error('AMap JS API loaded, but window.AMap is unavailable'))
      }
      script.onerror = () => {
        amapLoaderPromise = null
        script.remove()
        reject(new Error('Failed to load AMap JS API script'))
      }
      document.head.appendChild(script)
    })
  }

  return amapLoaderPromise
}

export function resetAmapLoader() {
  amapLoaderPromise = null
  document
    .querySelectorAll('script[data-amap-loader="true"]')
    .forEach((node) => node.parentNode?.removeChild(node))
  if (window.AMap) {
    try {
      delete window.AMap
    } catch (error) {
      window.AMap = undefined
    }
  }
}
