package ru.dcampfire.client

import java.io.IOException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.*
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener

@Serializable
data class ServerEvent(val type: String, val data: JsonObject)
sealed interface RealtimeSignal {
    data object Connected : RealtimeSignal
    data object Disconnected : RealtimeSignal
    data object SignedOut : RealtimeSignal
    data class Event(val value: ServerEvent) : RealtimeSignal
}

class RealtimeClient(private val api: CampfireClient) {
    private fun connection(): Flow<RealtimeSignal> = callbackFlow {
        val socket = api.http.newWebSocket(
            api.websocketRequest(),
            object : WebSocketListener() {
                override fun onOpen(webSocket: WebSocket, response: Response) {
                    trySend(RealtimeSignal.Connected)
                }
                override fun onMessage(webSocket: WebSocket, text: String) {
                    val event = runCatching { api.json.decodeFromString<ServerEvent>(text) }.getOrNull()
                    if (event != null && trySend(RealtimeSignal.Event(event)).isFailure) {
                        close(IOException("Event buffer full"))
                        webSocket.cancel()
                    }
                }
                override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                    webSocket.close(code, reason)
                    if (code == 4401 || code == 1008) trySend(RealtimeSignal.SignedOut)
                    close()
                }
                override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                    close()
                }
                override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                    if (response?.code == 401 || response?.code == 403) {
                        trySend(RealtimeSignal.SignedOut)
                        close()
                    } else {
                        close(t)
                    }
                }
            },
        )
        awaitClose { socket.cancel() }
    }
    fun events(): Flow<RealtimeSignal> = flow {
        var delayMs = 1000L
        var signedOut = false
        while (!signedOut) {
            connection().catch { if (it is CancellationException) throw it }.collect { signal ->
                if (signal == RealtimeSignal.Connected) delayMs = 1000L
                if (signal == RealtimeSignal.SignedOut) signedOut = true
                emit(signal)
            }
            if (!signedOut) {
                emit(RealtimeSignal.Disconnected)
                delay(delayMs)
                delayMs = (delayMs * 2).coerceAtMost(30_000L)
            }
        }
    }
}
