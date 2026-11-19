package ru.dcampfire.data

import kotlinx.serialization.Serializable
import ru.dcampfire.api.models.*

@Serializable
data class LocalSnapshot(
    val profile: ProfileRead? = null,
    val config: ConfigResponse? = null,
    val topics: List<TopicRead> = emptyList(),
    val mine: List<BonfireCard> = emptyList(),
    val recommended: List<BonfireCard> = emptyList(),
    val invitations: List<InvitationRead> = emptyList(),
    val details: Map<Long, BonfireDetail> = emptyMap(),
    val messages: Map<Long, List<MessageRead>> = emptyMap(),
    // Last cursor fully reconciled via REST. WebSocket events never advance it.
    val cursors: Map<Long, Long> = emptyMap(),
)
