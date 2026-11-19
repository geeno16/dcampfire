package ru.dcampfire.client

import java.util.concurrent.atomic.AtomicReference
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import ru.dcampfire.api.models.LoginRequest

class CampfireClientTest {
    private fun profile(id: Long = 5_000_000_001L) = """{"id":$id,"nickname":"test_user","email":"test@example.test","avatar_url":null,"topics":[]}"""

    @Test
    fun `reads current token for each call and decodes 64 bit ids`() = runBlocking {
        MockWebServer().use { server ->
            val token = AtomicReference<String?>(null)
            val client = CampfireClient(server.url("/").toString()) { token.get() }
            server.enqueue(
                MockResponse().setBody("""{"access_token":"secret","profile":${profile()}}"""),
            )
            val login = client.body(
                client.auth.login(LoginRequest("test@example.test", "password123")),
            )
            assertEquals(5_000_000_001L, login.profile.id)
            assertNull(server.takeRequest().getHeader("Authorization"))

            token.set(login.accessToken)
            server.enqueue(MockResponse().setBody(profile()))
            assertEquals(5_000_000_001L, client.body(client.profile.getProfile()).id)
            assertEquals("Bearer secret", server.takeRequest().getHeader("Authorization"))
        }
    }

    @Test
    fun `does not send bearer token to another origin`() {
        MockWebServer().use { server ->
            MockWebServer().use { other ->
                val client = CampfireClient(server.url("/").toString()) { "private-token" }
                other.enqueue(MockResponse().setBody("ok"))
                client.http.newCall(okhttp3.Request.Builder().url(other.url("/image")).build())
                    .execute().use { assertTrue(it.isSuccessful) }
                assertNull(other.takeRequest().getHeader("Authorization"))
            }
        }
    }

    @Test
    fun `patch sends explicit album null while omitting other fields`() = runBlocking {
        MockWebServer().use { server ->
            val client = CampfireClient(server.url("/").toString()) { "token" }
            server.enqueue(
                MockResponse().setBody(
                    """{"id":5000000001,"name":"Night","color":"orange","is_open":true,"owner_id":5000000001,"members_count":1,"topics":[],"album":null,"members":[],"invitations":[],"next_message_at":null}""",
                ),
            )
            client.body(
                client.patch.update(
                    5_000_000_001L,
                    buildJsonObject {
                        put("album_url", JsonNull)
                    },
                ),
            )
            val request = server.takeRequest()
            assertEquals("PATCH", request.method)
            assertTrue(request.path!!.endsWith("/5000000001"))
            assertEquals("{\"album_url\":null}", request.body.readUtf8())
        }
    }

    @Test
    fun `returns structured cooldown error`() = runBlocking {
        MockWebServer().use { server ->
            val client = CampfireClient(server.url("/").toString()) { "token" }
            server.enqueue(
                MockResponse().setResponseCode(
                    429,
                ).setBody("""{"code":"PAUSE_ACTIVE","retry_after":7}"""),
            )
            val failure = runCatching { client.body(client.profile.getProfile()) }.exceptionOrNull()
            assertTrue(failure is ApiFailure)
            assertEquals(429, (failure as ApiFailure).status)
            assertEquals("PAUSE_ACTIVE", failure.problem.code)
            assertEquals(7, failure.problem.retryAfter)
        }
    }

    @Test
    fun `message history parses nullable author and long cursor`() = runBlocking {
        MockWebServer().use { server ->
            val client = CampfireClient(server.url("/").toString()) { "token" }
            server.enqueue(
                MockResponse().setBody(
                    """[{"id":5000000002,"bonfire_id":5000000001,"author":null,"body":"Привет","created_at":"2026-11-18T07:00:00.123456+00:00"}]""",
                ),
            )
            val messages = client.body(
                client.messages.listMessages(5_000_000_001L, afterId = 5_000_000_000L),
            )
            assertEquals(5_000_000_002L, messages.single().id)
            assertNull(messages.single().author)
            assertEquals(123_456_000, messages.single().createdAt.nano)
            assertTrue(server.takeRequest().path!!.contains("after_id=5000000000"))
        }
    }

    @Test
    fun `accepts empty successful response`() = runBlocking {
        MockWebServer().use { server ->
            val client = CampfireClient(server.url("/").toString()) { "token" }
            server.enqueue(MockResponse().setResponseCode(204))
            client.done(client.profile.deleteAvatar())
            assertEquals("DELETE", server.takeRequest().method)
        }
    }

    @Test
    fun `websocket request has the same authenticated origin`() {
        MockWebServer().use { server ->
            val client = CampfireClient(server.url("/").toString()) { "token" }
            val request = client.websocketRequest()
            assertEquals(server.url("/").host, request.url.host)
            assertTrue(request.url.encodedPath.endsWith("/api/v1/ws"))
            assertFalse(request.url.isHttps)
            assertNotNull(client.http)
        }
    }
}
