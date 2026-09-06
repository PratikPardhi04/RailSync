import { useState, useEffect, useCallback, useRef } from 'react'

export interface WSMessage {
  event: string
  data: any
}

export function useWebSocket(requestId: number | null) {
  const [messages, setMessages] = useState<WSMessage[]>([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (!requestId) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    let wsOrigin = import.meta.env.VITE_WS_URL || `${protocol}//${window.location.hostname}:8000`
    if (wsOrigin.startsWith('https://')) wsOrigin = 'wss://' + wsOrigin.slice(8)
    else if (wsOrigin.startsWith('http://')) wsOrigin = 'ws://' + wsOrigin.slice(7)
    const wsUrl = `${wsOrigin.replace(/\/+$/, '')}/ws/${requestId}`

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => setConnected(true)
    ws.onclose = () => setConnected(false)
    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data)
        setMessages(prev => [...prev, msg])
      } catch {}
    }

    return () => {
      ws.close()
    }
  }, [requestId])

  const clearMessages = useCallback(() => setMessages([]), [])

  return { messages, connected, clearMessages }
}
