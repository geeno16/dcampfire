package ru.dcampfire.client

import java.io.IOException
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import java.util.concurrent.TimeUnit
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import retrofit2.Response
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import retrofit2.http.Body
import retrofit2.http.PATCH
import retrofit2.http.Path
import ru.dcampfire.api.apis.*
import ru.dcampfire.api.infrastructure.Serializer
import ru.dcampfire.api.models.BonfireDetail

@Serializable
data class FieldProblem(val field: String = "", val message: String = "")

@Serializable
data class ApiProblem(
    val code: String = "UNKNOWN",
    val errors: List<FieldProblem> = emptyList(),
    @SerialName("retry_after") val retryAfter: Int? = null,
    @SerialName("attempts_left") val attemptsLeft: Int? = null,
    @SerialName("next_message_at") val nextMessageAt: String? = null,
)

class ApiFailure(val status: Int, val problem: ApiProblem) : IOException(problem.code)
class InvalidResponse : IOException("Invalid server response")

/** Unlike the generated nullable DTO, this preserves omitted fields versus explicit null. */
interface BonfirePatchApi {
    @PATCH("api/v1/bonfires/{id}")
    suspend fun update(@Path("id") id: Long, @Body changes: JsonObject): Response<BonfireDetail>
}

class CampfireClient(baseUrl: String, token: () -> String?) {
    val json = Json(Serializer.kotlinxSerializationJson) {
        isLenient = false
        ignoreUnknownKeys = true
        encodeDefaults = true
    }
    val base = baseUrl.trimEnd('/').plus("/").toHttpUrl()

    @Volatile private var clockOffset = 0L
    fun localTimestamp(serverMillis: Long): Long = serverMillis - clockOffset
    val http = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .callTimeout(20, TimeUnit.SECONDS)
        .pingInterval(20, TimeUnit.SECONDS)
        .retryOnConnectionFailure(false)
        .followRedirects(false)
        .addInterceptor { chain ->
            val request = chain.request()
            val sameOrigin = request.url.scheme == base.scheme && request.url.host == base.host && request.url.port == base.port
            val builder = request.newBuilder().header("Accept", "application/json")
            if (sameOrigin) token()?.takeIf { it.isNotBlank() }?.let { builder.header("Authorization", "Bearer $it") }
            val response = chain.proceed(builder.build())
            if (sameOrigin) {
                response.header("Date")?.let { date ->
                    runCatching { ZonedDateTime.parse(date, DateTimeFormatter.RFC_1123_DATE_TIME).toInstant().toEpochMilli() }
                        .getOrNull()?.let { clockOffset = it - System.currentTimeMillis() }
                }
            }
            response
        }.build()
    private val retrofit = Retrofit.Builder().baseUrl(base).client(http)
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType())).build()
    val auth: AuthApi = retrofit.create(AuthApi::class.java)
    val profile: ProfileApi = retrofit.create(ProfileApi::class.java)
    val reference: ReferenceApi = retrofit.create(ReferenceApi::class.java)
    val bonfires: BonfireApi = retrofit.create(BonfireApi::class.java)
    val membership: MembershipApi = retrofit.create(MembershipApi::class.java)
    val messages: MessageApi = retrofit.create(MessageApi::class.java)
    val albums: AlbumApi = retrofit.create(AlbumApi::class.java)
    val patch: BonfirePatchApi = retrofit.create(BonfirePatchApi::class.java)

    fun <T> body(response: Response<T>): T {
        check(response)
        return response.body() ?: throw InvalidResponse()
    }
    fun done(response: Response<Unit>) {
        check(response)
    }
    private fun check(response: Response<*>) {
        if (response.isSuccessful) return
        val problem = response.errorBody()?.use { body ->
            runCatching { json.decodeFromString<ApiProblem>(body.string()) }.getOrNull()
        } ?: ApiProblem(if (response.code() == 401) "UNAUTHORIZED" else "UNKNOWN")
        throw ApiFailure(response.code(), problem)
    }
    fun websocketRequest(): Request = Request.Builder().url(base.newBuilder().addPathSegments("api/v1/ws").build()).build()
    fun avatarRequest(path: String): Request {
        val url = requireNotNull(base.resolve(path))
        require(url.host == base.host && url.port == base.port && url.scheme == base.scheme)
        return Request.Builder().url(url).build()
    }
}
