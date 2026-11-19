package ru.dcampfire

import android.app.Application
import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import java.io.IOException
import java.time.OffsetDateTime
import java.util.concurrent.atomic.AtomicReference
import kotlinx.coroutines.*
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.serialization.json.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import ru.dcampfire.api.models.*
import ru.dcampfire.client.*
import ru.dcampfire.data.*

enum class Screen { LOGIN, REGISTER, VERIFY, TOPICS, HOME, CHAT, MEMBERS, EDIT, PROFILE }

data class AppState(
    val data: LocalSnapshot = LocalSnapshot(),
    val screen: Screen = Screen.LOGIN,
    val selectedId: Long? = null,
    val creating: Boolean = true,
    val busy: Boolean = false,
    val refreshing: Boolean = false,
    val offline: Boolean = false,
    val realtimeConnected: Boolean = false,
    val email: String = "",
    val resendAt: Long = 0,
    val nextMessageAt: Long = 0,
    val error: String? = null,
    val notice: String? = null,
    val fields: Map<String, String> = emptyMap(),
    val albumPreview: String? = null,
    val canLoadOlder: Boolean = true,
    val sentRevision: Int = 0,
) {
    val selected: BonfireDetail? get() = data.details[selectedId]
    val messages: List<MessageRead> get() = data.messages[selectedId].orEmpty()
    val limits: LimitsRead? get() = data.config?.limits
}

class CampfireViewModel(application: Application) : AndroidViewModel(application) {
    var state by mutableStateOf(AppState())
        private set
    private val storage = SecureStore(application)
    private val token = AtomicReference<String?>(null)
    val api = CampfireClient(BackendUrl.value) { token.get() }
    private var realtimeJob: Job? = null
    private var actionJob: Job? = null
    private var refreshJob: Job? = null
    private var refreshAgain = false
    private val syncLock = Mutex()
    private val storageLock = Mutex()

    @Volatile private var generation = 0

    init {
        viewModelScope.launch { restore() }
    }

    private suspend fun restore() {
        val saved = withContext(Dispatchers.IO) {
            val snapshot = storage.read("cache")?.let {
                runCatching { api.json.decodeFromString<LocalSnapshot>(it) }.getOrNull()
            }
            Triple(storage.read("token"), snapshot, storage.read("pending").orEmpty())
        }
        val snapshot = saved.second
        if (!saved.first.isNullOrBlank() && snapshot?.profile != null) {
            token.set(saved.first)
            state = state.copy(data = snapshot, screen = Screen.HOME)
            connectRealtime()
            refresh()
        } else {
            state = state.copy(email = saved.third, screen = if (saved.third.isNotBlank()) Screen.VERIFY else Screen.LOGIN)
            loadPublicConfig()
        }
    }

    fun navigate(screen: Screen) {
        state = state.copy(screen = screen, error = null, notice = null, fields = emptyMap())
    }
    fun back() {
        when (state.screen) {
            Screen.REGISTER -> navigate(Screen.LOGIN)

            Screen.VERIFY -> navigate(Screen.REGISTER)

            Screen.PROFILE, Screen.TOPICS -> navigate(Screen.HOME)

            Screen.EDIT -> navigate(if (state.creating) Screen.HOME else Screen.CHAT)

            Screen.MEMBERS -> navigate(Screen.CHAT)

            Screen.CHAT -> {
                navigate(Screen.HOME)
                refresh()
            }

            else -> Unit
        }
    }
    fun clearError() {
        state = state.copy(error = null, notice = null, fields = emptyMap())
    }
    fun validation(fields: Map<String, String>) {
        state = state.copy(fields = fields, error = "Проверьте заполненные поля.")
    }

    private fun action(block: suspend () -> Unit) {
        if (state.busy) return
        state = state.copy(busy = true, error = null, notice = null, fields = emptyMap())
        actionJob = viewModelScope.launch {
            try {
                block()
                persist()
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                handle(e)
            } finally {
                state = state.copy(busy = false)
            }
        }
    }
    private suspend fun persist() {
        val epoch = generation
        val snapshot = state.data.copy(messages = state.data.messages.mapValues { it.value.takeLast(1000) })
        storageLock.withLock {
            withContext(Dispatchers.IO) {
                val currentToken = token.get()
                if (generation == epoch && currentToken != null) {
                    storage.write("cache", api.json.encodeToString(snapshot))
                    storage.write("token", currentToken)
                }
            }
        }
    }
    private suspend fun loadPublicConfig() {
        try {
            val config = api.body(api.reference.getConfig())
            state = state.copy(data = state.data.copy(config = config), offline = false)
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            handle(e)
        }
    }
    fun register(nickname: String, email: String, password: String) = action {
        val response = api.body(api.auth.register(RegisterRequest(nickname.trim(), email.trim(), password, true)))
        state = state.copy(
            email = response.email,
            screen = Screen.VERIFY,
            offline = false,
            resendAt = System.currentTimeMillis() + (state.limits?.emailCodeResendCooldownSeconds ?: 60) * 1000L,
        )
        withContext(Dispatchers.IO) { storage.write("pending", response.email) }
    }
    fun verify(code: String) = action { establish(api.body(api.auth.verifyEmail(VerifyEmailRequest(state.email, code))), true) }
    fun resend() = action {
        api.done(api.auth.resendCode(ResendCodeRequest(state.email)))
        state = state.copy(
            resendAt = System.currentTimeMillis() + (state.limits?.emailCodeResendCooldownSeconds ?: 60) * 1000L,
            notice = "Новый код отправлен.",
        )
    }
    fun login(email: String, password: String) = action {
        state = state.copy(email = email.trim())
        establish(api.body(api.auth.login(LoginRequest(email.trim(), password))), false)
    }
    private suspend fun establish(response: AuthResponse, onboarding: Boolean) {
        generation++
        realtimeJob?.cancel()
        refreshJob?.cancel()
        storageLock.withLock { withContext(Dispatchers.IO) { storage.clear() } }
        token.set(response.accessToken)
        state = state.copy(
            data = LocalSnapshot(profile = response.profile, config = state.data.config),
            screen = if (onboarding) Screen.TOPICS else Screen.HOME,
            selectedId = null,
            offline = false,
            nextMessageAt = 0,
        )
        persist()
        connectRealtime()
        refresh()
    }
    fun refresh() {
        if (refreshJob?.isActive == true) {
            refreshAgain = true
            return
        }
        refreshJob = viewModelScope.launch {
            state = state.copy(refreshing = true)
            try {
                do {
                    refreshAgain = false
                    if (token.get() == null) loadPublicConfig() else synchronize()
                } while (refreshAgain)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                handle(e)
            } finally {
                state = state.copy(refreshing = false)
            }
        }
    }
    private suspend fun synchronize() = syncLock.withLock {
        coroutineScope {
            val configTask = async { api.body(api.reference.getConfig()) }
            val profileTask = async { api.body(api.profile.getProfile()) }
            val topicsTask = async { api.body(api.reference.listTopics()) }
            val mineTask = async { api.body(api.bonfires.listMyBonfires()) }
            val recommendationsTask = async {
                try {
                    api.body(api.bonfires.listRecommended(limit = 50))
                } catch (e: CancellationException) {
                    throw e
                } catch (_: Exception) {
                    // Recommendations are optional; a failure must not hide the user's own bonfires.
                    null
                }
            }
            val invitationsTask = async { api.body(api.membership.listInvitations()) }
            val config = configTask.await()
            val profile = profileTask.await()
            val topics = topicsTask.await()
            val mine = mineTask.await()
            val recommended = recommendationsTask.await() ?: state.data.recommended
            val invitations = invitationsTask.await()
            val ids = mine.map { it.id }.toSet()
            state = state.copy(
                data = state.data.copy(
                    config = config, profile = profile, topics = topics, mine = mine,
                    recommended = recommended, invitations = invitations, details = state.data.details.filterKeys { it in ids },
                    messages = state.data.messages.filterKeys { it in ids }, cursors = state.data.cursors.filterKeys { it in ids },
                ),
                offline = false,
            )
            val id = state.selectedId
            if (id != null && id !in ids && state.screen in setOf(Screen.CHAT, Screen.MEMBERS, Screen.EDIT)) {
                state = state.copy(screen = Screen.HOME, selectedId = null, notice = "Этот костёр больше недоступен.")
            } else if (id != null && id in ids) {
                loadBonfire(id)
            }
            persist()
        }
    }
    fun openBonfire(id: Long) {
        state = state.copy(selectedId = id, screen = Screen.CHAT, error = null, canLoadOlder = true)
        action { loadBonfire(id) }
    }
    private suspend fun loadBonfire(id: Long) {
        val detail = api.body(api.bonfires.getBonfire(id))
        var messages = state.data.messages[id].orEmpty()
        var cursor = state.data.cursors[id]
        if (cursor != null && cursor > 0) {
            do {
                val page = api.body(api.messages.listMessages(id, afterId = cursor, limit = 100))
                messages = mergeMessages(messages, page)
                if (page.isNotEmpty()) cursor = page.maxOf { it.id }
            } while (page.size == 100)
        } else {
            val page = api.body(api.messages.listMessages(id))
            messages = mergeMessages(messages, page)
            cursor = page.maxOfOrNull { it.id } ?: 0L
        }
        // Events arriving during REST are merged without advancing the REST cursor.
        messages = mergeMessages(messages, state.data.messages[id].orEmpty())
        state = state.copy(
            data = state.data.copy(
                details = state.data.details + (id to detail),
                messages = state.data.messages + (id to messages),
                cursors = state.data.cursors + (id to requireNotNull(cursor)),
            ),
            offline = false,
            nextMessageAt = maxOf(
                state.nextMessageAt,
                detail.nextMessageAt?.let {
                    api.localTimestamp(it.toInstant().toEpochMilli())
                } ?: 0,
            ),
        )
    }
    fun loadOlder() = action {
        val id = state.selectedId ?: return@action
        val page = api.body(api.messages.listMessages(id, beforeId = state.messages.firstOrNull()?.id))
        state = state.copy(data = state.data.copy(messages = state.data.messages + (id to mergeMessages(page, state.messages))), canLoadOlder = page.size == 50)
    }
    fun sendMessage(body: String) = action {
        val id = state.selectedId ?: return@action
        val sent = api.body(api.messages.sendMessage(id, SendMessageRequest(body.trim())))
        state = state.copy(
            data = state.data.copy(messages = state.data.messages + (id to mergeMessages(state.messages, listOf(sent.message)))),
            nextMessageAt = api.localTimestamp(sent.nextMessageAt.toInstant().toEpochMilli()),
            sentRevision = state.sentRevision + 1,
            offline = false,
        )
    }
    fun join(id: Long) = action {
        val detail = api.body(api.membership.joinBonfire(id))
        state = state.copy(data = state.data.copy(details = state.data.details + (id to detail)), selectedId = id, screen = Screen.CHAT)
        synchronize()
    }
    fun decline(id: Long) = action {
        api.done(api.membership.declineInvitation(id))
        synchronize()
    }
    fun editBonfire(create: Boolean) {
        state = state.copy(
            creating = create,
            albumPreview = if (create) null else state.selected?.album?.title,
            screen = Screen.EDIT,
            fields = emptyMap(),
            error = null,
        )
    }
    fun lookupAlbum(url: String) = action { state = state.copy(albumPreview = api.body(api.albums.lookupAlbum(url.trim())).title) }
    fun saveBonfire(name: String, color: String, topics: List<Int>, url: String, isOpen: Boolean) = action {
        val album = url.trim().takeIf { it.isNotEmpty() }
        val detail = if (state.creating) {
            api.body(api.bonfires.createBonfire(BonfireCreateRequest(name.trim(), color, topics, album, isOpen)))
        } else {
            api.body(
                api.patch.update(
                    requireNotNull(state.selectedId),
                    buildJsonObject {
                        put("name", name.trim())
                        put("color", color)
                        put("is_open", isOpen)
                        put("topic_ids", JsonArray(topics.map { JsonPrimitive(it) }))
                        put("album_url", album?.let { JsonPrimitive(it) } ?: JsonNull)
                    },
                ),
            )
        }
        state = state.copy(
            data = state.data.copy(details = state.data.details + (detail.id to detail)),
            selectedId = detail.id,
            creating = false,
            screen = Screen.CHAT,
        )
        synchronize()
    }
    fun deleteBonfire() = action {
        api.done(api.bonfires.deleteBonfire(requireNotNull(state.selectedId)))
        state = state.copy(screen = Screen.HOME, selectedId = null)
        synchronize()
    }
    fun removeMember(id: Long) = action {
        api.done(api.membership.removeMember(requireNotNull(state.selectedId), id))
        if (id == state.data.profile?.id) state = state.copy(screen = Screen.HOME, selectedId = null)
        synchronize()
    }
    fun invite(nickname: String) = action {
        val id = requireNotNull(state.selectedId)
        api.done(api.membership.invite(id, InviteRequest(nickname.trim())))
        loadBonfire(id)
        state = state.copy(notice = "Приглашение отправлено.")
    }
    fun cancelInvitation(userId: Long) = action {
        val id = requireNotNull(state.selectedId)
        api.done(api.membership.cancelInvitation(id, userId))
        loadBonfire(id)
    }
    fun setTopics(topics: List<Int>, returnHome: Boolean = true) = action {
        val profile = api.body(api.profile.setTopics(SetTopicsRequest(topics)))
        state = state.copy(data = state.data.copy(profile = profile), screen = if (returnHome) Screen.HOME else state.screen, notice = "Интересы сохранены.")
        synchronize()
    }
    fun updateNickname(nickname: String) = action {
        val profile = api.body(api.profile.updateProfile(UpdateProfileRequest(nickname.trim())))
        state = state.copy(data = state.data.copy(profile = profile), notice = "Псевдоним сохранён.")
    }
    fun changePassword(current: String, new: String) = action {
        api.done(api.profile.changePassword(ChangePasswordRequest(current, new)))
        state = state.copy(notice = "Пароль изменён.")
    }
    fun uploadAvatar(uri: Uri) = action {
        val max = state.limits?.avatarMaxBytes ?: 5 * 1024 * 1024
        val (bytes, type) = withContext(Dispatchers.IO) {
            val resolver = getApplication<Application>().contentResolver
            val data = resolver.openInputStream(uri)?.use { stream ->
                val output = java.io.ByteArrayOutputStream()
                val buffer = ByteArray(8192)
                var read: Int
                while (stream.read(buffer).also { read = it } != -1) {
                    if (output.size() + read > max) throw ApiFailure(422, ApiProblem("VALIDATION_FAILED", listOf(FieldProblem("file"))))
                    output.write(buffer, 0, read)
                }
                output.toByteArray()
            } ?: throw IOException("Cannot read image")
            data to (resolver.getType(uri) ?: "application/octet-stream")
        }
        val part = MultipartBody.Part.createFormData("file", "avatar", bytes.toRequestBody(type.toMediaType()))
        val profile = api.body(api.profile.uploadAvatar(part))
        state = state.copy(data = state.data.copy(profile = profile))
    }
    fun deleteAvatar() = action {
        api.done(api.profile.deleteAvatar())
        val profile = api.body(api.profile.getProfile())
        state = state.copy(data = state.data.copy(profile = profile))
    }
    fun deleteAccount(password: String) = action {
        api.done(api.profile.deleteAccount(DeleteAccountRequest(password)))
        clearSession()
    }
    fun logout() {
        actionJob?.cancel()
        refreshJob?.cancel()
        realtimeJob?.cancel()
        viewModelScope.launch { clearSession() }
    }
    private suspend fun clearSession() {
        generation++
        token.set(null)
        realtimeJob?.cancel()
        refreshJob?.cancel()
        refreshAgain = false
        state = AppState(data = LocalSnapshot(config = state.data.config))
        storageLock.withLock { withContext(Dispatchers.IO) { storage.clear() } }
    }
    private fun connectRealtime() {
        realtimeJob?.cancel()
        realtimeJob = viewModelScope.launch {
            RealtimeClient(api).events().collect { signal ->
                when (signal) {
                    RealtimeSignal.Connected -> {
                        state = state.copy(realtimeConnected = true)
                        refresh()
                    }

                    RealtimeSignal.Disconnected -> state = state.copy(realtimeConnected = false)

                    RealtimeSignal.SignedOut -> logout()

                    is RealtimeSignal.Event -> applyEvent(signal.value)
                }
            }
        }
    }
    private suspend fun applyEvent(event: ServerEvent) {
        val id = event.data["bonfire_id"]?.jsonPrimitive?.longOrNull ?: return
        when (event.type) {
            "message.created" -> {
                val message = runCatching { api.json.decodeFromJsonElement<MessageRead>(event.data.getValue("message")) }.getOrNull() ?: return
                state = state.copy(data = state.data.copy(messages = state.data.messages + (id to mergeMessages(state.data.messages[id].orEmpty(), listOf(message)))))
                if (message.author?.id == state.data.profile?.id) {
                    state = state.copy(nextMessageAt = api.localTimestamp(message.createdAt.plusSeconds((state.limits?.messagePauseSeconds ?: 10).toLong()).toInstant().toEpochMilli()))
                }
                persist()
            }

            "bonfire.removed" -> {
                state = state.copy(
                    data = state.data.copy(
                        details = state.data.details - id,
                        messages = state.data.messages - id,
                        cursors = state.data.cursors - id,
                        mine = state.data.mine.filterNot { it.id == id },
                    ),
                    screen = if (state.selectedId == id) Screen.HOME else state.screen,
                    selectedId = if (state.selectedId == id) null else state.selectedId,
                    notice = "Состав ваших костров изменился.",
                )
                refresh()
                persist()
            }

            "bonfire.updated", "invitation.created", "invitation.removed" -> refresh()
        }
    }
    private fun handle(e: Exception) {
        when (e) {
            is ApiFailure -> {
                if (e.problem.code == "UNAUTHORIZED") {
                    logout()
                    return
                }
                if (e.problem.code == "EMAIL_NOT_VERIFIED") state = state.copy(screen = Screen.VERIFY)
                val fields = e.problem.errors.associate { it.field.substringBefore('.') to fieldText(it.field) }.toMutableMap()
                when (e.problem.code) {
                    "NICKNAME_TAKEN" -> fields["nickname"] = errorText(e.problem)

                    "EMAIL_TAKEN" -> fields["email"] = errorText(e.problem)

                    "PAUSE_ACTIVE" -> state = state.copy(nextMessageAt = System.currentTimeMillis() + (e.problem.retryAfter ?: 10) * 1000L)

                    "RESEND_TOO_EARLY" -> state = state.copy(resendAt = System.currentTimeMillis() + (e.problem.retryAfter ?: 60) * 1000L)

                    "BONFIRE_NOT_FOUND" -> {
                        val id = state.selectedId
                        if (id != null) {
                            state = state.copy(
                                data = state.data.copy(
                                    details = state.data.details - id,
                                    messages = state.data.messages - id,
                                    cursors = state.data.cursors - id,
                                ),
                                selectedId = null,
                                screen = Screen.HOME,
                            )
                        }
                    }
                }
                state = state.copy(error = errorText(e.problem), fields = fields, offline = false)
            }

            is InvalidResponse -> state = state.copy(error = "Не удалось обработать ответ сервера. Обновите экран.")

            is IOException -> state = state.copy(offline = true, error = "Нет связи с сервером. Сохранённые данные доступны; проверьте сеть и повторите действие.")

            else -> state = state.copy(error = "Не удалось обработать ответ сервера. Попробуйте обновить экран.")
        }
    }
}

fun mergeMessages(first: List<MessageRead>, second: List<MessageRead>): List<MessageRead> = (first + second).associateBy { it.id }.values.sortedBy { it.id }
