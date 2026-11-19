package ru.dcampfire.ui

import android.content.Intent
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.core.net.toUri
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import ru.dcampfire.CampfireViewModel
import ru.dcampfire.Screen
import ru.dcampfire.api.models.BonfireCard

@Composable
fun HomeScreen(vm: CampfireViewModel) {
    val s = vm.state
    var discovery by rememberSaveable { mutableStateOf(false) }
    val profile = s.data.profile
    val max = s.limits?.userBonfiresMax ?: 5
    LazyColumn(Modifier.fillMaxSize().padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(12.dp), contentPadding = PaddingValues(vertical = 16.dp)) {
        item {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Доброй ночи,", color = Muted, style = MaterialTheme.typography.bodySmall)
                    Text(profile?.nickname ?: "Путник", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                }
                Box(Modifier.clickable { vm.navigate(Screen.PROFILE) }) { Avatar(vm.api, profile?.nickname.orEmpty(), profile?.avatarUrl) }
            }
        }
        item {
            Row(verticalAlignment = Alignment.CenterVertically) {
                TextButton(onClick = { vm.navigate(Screen.TOPICS) }) { Text("Темы") }
                Text(profile?.topics.orEmpty().joinToString(" · ") { it.name }.ifEmpty { "Выберите свои интересы" }, color = Muted, style = MaterialTheme.typography.bodySmall)
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(!discovery, { discovery = false }, label = { Text("Мои костры") }, modifier = Modifier.weight(1f))
                FilterChip(discovery, { discovery = true }, label = { Text("Найти костёр") }, modifier = Modifier.weight(1f))
            }
        }
        if (!discovery) {
            items(s.data.invitations, key = { "invite-${it.bonfire.id}" }) { invitation ->
                Card(colors = CardDefaults.cardColors(containerColor = Cream)) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text("${invitation.owner.nickname} зовёт вас в «${invitation.bonfire.name}»", color = Color(0xFF241B13), fontWeight = FontWeight.Bold)
                        Text(invitation.bonfire.topics.joinToString(" · ") { it.name }, color = Color(0xFF4D4033), style = MaterialTheme.typography.bodySmall)
                        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            Button(onClick = { vm.join(invitation.bonfire.id) }, enabled = !s.busy, colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF251B13), contentColor = Cream)) { Text("Принять") }
                            TextButton(onClick = { vm.decline(invitation.bonfire.id) }, enabled = !s.busy) { Text("Отклонить", color = Color(0xFF241B13)) }
                        }
                    }
                }
            }
            items(s.data.mine, key = { "mine-${it.id}" }) { card ->
                BonfireTile(card, if (card.ownerId == profile?.id) "ХОЗЯИН" else "УЧАСТНИК", s.limits?.bonfireCapacity ?: 5, { vm.openBonfire(card.id) })
            }
            if (s.data.mine.isEmpty()) item { Text("Здесь появятся ваши костры. Создайте свой или найдите компанию по интересам.", color = Muted) }
            item {
                Primary("+ Разжечь костёр", s.data.mine.size < max && !s.busy) { vm.editBonfire(true) }
                Text(
                    if (s.data.mine.size >= max) "Вы уже в $max кострах. Сначала покиньте один из них." else "${s.data.mine.size} из $max костров",
                    Modifier.padding(top = 8.dp),
                    color = Muted,
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        } else {
            item { Text("Открытые костры со свободными местами. Больше общих тем — выше в списке.", color = Muted) }
            items(s.data.recommended, key = { "find-${it.id}" }) { card ->
                val common = card.topics.count { topic -> profile?.topics?.any { it.id == topic.id } == true }
                BonfireTile(card, "$common общих тем", s.limits?.bonfireCapacity ?: 5, {}, join = { vm.join(card.id) }, enabled = !s.busy && s.data.mine.size < max)
            }
            if (s.data.recommended.isEmpty()) item { Text("Пока нет доступных костров. Попробуйте позже или создайте свой.", color = Muted) }
        }
        item { TextButton(onClick = vm::refresh, enabled = !s.refreshing) { Text("Обновить список") } }
    }
}

@Composable
private fun BonfireTile(card: BonfireCard, role: String, capacity: Int, onClick: () -> Unit, join: (() -> Unit)? = null, enabled: Boolean = true) {
    Card(
        modifier = Modifier.fillMaxWidth().then(if (join == null) Modifier.clickable(onClick = onClick) else Modifier),
        shape = RoundedCornerShape(22.dp),
        colors = CardDefaults.cardColors(containerColor = Panel.copy(alpha = .9f)),
    ) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Fire(Modifier.size(58.dp), fireColor(card.color))
                Column(Modifier.weight(1f).padding(start = 12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(card.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Text(card.topics.joinToString(" · ") { it.name }, color = Muted, style = MaterialTheme.typography.bodySmall)
                    Text("${card.membersCount} из $capacity · ${if (card.isOpen) "Открытый" else "Закрытый"}", color = Muted, style = MaterialTheme.typography.bodySmall)
                }
            }
            Text(role, color = Cream, style = MaterialTheme.typography.labelSmall)
            if (join != null) Primary("Подсесть к костру", enabled, join)
        }
    }
}

@Composable
fun ChatScreen(vm: CampfireViewModel) {
    val s = vm.state
    val detail = s.selected
    val context = LocalContext.current
    val owner = detail?.ownerId == s.data.profile?.id
    var body by rememberSaveable(s.selectedId) { mutableStateOf("") }
    val list = rememberLazyListState()
    val remaining = secondsUntil(s.nextMessageAt)
    var lastSentRevision by remember { mutableIntStateOf(s.sentRevision) }
    LaunchedEffect(s.sentRevision) {
        if (s.sentRevision != lastSentRevision) {
            body = ""
            lastSentRevision = s.sentRevision
        }
    }
    var lastCount by remember(s.selectedId) { mutableIntStateOf(0) }
    LaunchedEffect(s.messages.lastOrNull()?.id, s.selectedId) {
        if (s.messages.isNotEmpty() && (lastCount == 0 || list.firstVisibleItemIndex >= (lastCount - 6).coerceAtLeast(0))) {
            list.animateScrollToItem(s.messages.size)
        }
        lastCount = s.messages.size
    }
    Box(Modifier.fillMaxSize()) {
        Fire(Modifier.size(280.dp).align(Alignment.Center), detail?.color?.let(::fireColor) ?: Orange)
        Column(Modifier.fillMaxSize().imePadding().background(Color(0xA608080C))) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                TextButton(onClick = vm::back) { Text("‹", style = MaterialTheme.typography.headlineSmall) }
                Column(Modifier.weight(1f).clickable(enabled = owner) { vm.editBonfire(false) }) {
                    Text(detail?.name ?: "Загружаем костёр…", maxLines = 1, overflow = TextOverflow.Ellipsis, fontWeight = FontWeight.Bold)
                    Text(detail?.topics.orEmpty().joinToString(" · ") { it.name }, color = Muted, style = MaterialTheme.typography.labelSmall)
                }
                TextButton(onClick = { vm.navigate(Screen.MEMBERS) }, enabled = detail != null) { Text("Люди ${detail?.membersCount ?: ""}") }
            }
            if (detail != null) {
                Row(Modifier.fillMaxWidth().padding(horizontal = 18.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(if (detail.isOpen) "Открытый" else "Закрытый", color = Muted, style = MaterialTheme.typography.labelSmall)
                    Spacer(Modifier.width(12.dp))
                    detail.album?.let { album ->
                        TextButton(onClick = {
                            if (owner) vm.editBonfire(false) else runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, album.url.toUri())) }
                        }, modifier = Modifier.weight(1f)) { Text("♫ ${album.title ?: "Альбом"}", maxLines = 1, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.labelSmall) }
                    }
                    if (owner) TextButton(onClick = { vm.editBonfire(false) }) { Text("Изменить", style = MaterialTheme.typography.labelSmall) }
                }
            }
            if (!s.realtimeConnected) Text("Переподключаемся к чату…", Modifier.padding(horizontal = 18.dp), color = Muted, style = MaterialTheme.typography.bodySmall)
            LazyColumn(state = list, modifier = Modifier.weight(1f).fillMaxWidth(), contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                item {
                    if (s.canLoadOlder && s.messages.isNotEmpty()) TextButton(onClick = vm::loadOlder, enabled = !s.busy) { Text("Раньше у костра") }
                    if (s.messages.isEmpty() && !s.busy) Text("Пока тихо. Расскажите что-нибудь первым.", color = Muted)
                }
                items(s.messages, key = { it.id }) { message ->
                    val own = message.author?.id == s.data.profile?.id
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = if (own) Arrangement.End else Arrangement.Start, verticalAlignment = Alignment.Bottom) {
                        if (!own) {
                            Avatar(vm.api, message.author?.nickname ?: "?", message.author?.avatarUrl, Modifier.size(32.dp))
                            Spacer(Modifier.width(8.dp))
                        }
                        Column(Modifier.widthIn(max = 280.dp).clip(RoundedCornerShape(18.dp)).background(if (own) Cream else Panel).padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(message.author?.nickname ?: "Удалённый аккаунт", style = MaterialTheme.typography.labelSmall, color = if (own) Color(0xFF594834) else Muted)
                            Text(message.body, color = if (own) Color(0xFF241B13) else Color(0xFFF7F0E7))
                            Text(
                                message.createdAt.atZoneSameInstant(ZoneId.systemDefault()).format(DateTimeFormatter.ofPattern("dd.MM HH:mm")),
                                Modifier.align(Alignment.End),
                                style = MaterialTheme.typography.labelSmall,
                                color = if (own) Color(0xFF594834) else Muted,
                            )
                        }
                    }
                }
            }
            Row(Modifier.fillMaxWidth().background(Panel).padding(10.dp), verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    body,
                    { if (it.length <= (s.limits?.messageMaxLength ?: 1000)) body = it },
                    Modifier.weight(1f),
                    placeholder = { Text("Расскажите что-нибудь…") },
                    maxLines = 5,
                    shape = RoundedCornerShape(22.dp),
                )
                Button(onClick = { vm.sendMessage(body) }, enabled = !s.busy && remaining == 0 && body.isNotBlank() && detail != null) { Text(if (remaining > 0) "$remaining с" else "↑") }
            }
            Text("${body.length} / ${s.limits?.messageMaxLength ?: 1000}", Modifier.fillMaxWidth().background(Panel).padding(start = 18.dp, bottom = 4.dp), color = Muted, style = MaterialTheme.typography.labelSmall)
        }
    }
}

@Composable
fun MembersScreen(vm: CampfireViewModel) {
    val s = vm.state
    val detail = s.selected
    val context = LocalContext.current
    var leaving by remember { mutableStateOf(false) }
    Page("У костра", vm::back) {
        Text("${detail?.membersCount ?: 0} / ${s.limits?.bonfireCapacity ?: 5}", color = Muted)
        detail?.members.orEmpty().forEach { member ->
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Avatar(vm.api, member.nickname, member.avatarUrl)
                Text(member.nickname, Modifier.weight(1f).padding(start = 12.dp))
                if (member.id == detail?.ownerId) Text("ХОЗЯИН", color = Cream, style = MaterialTheme.typography.labelSmall)
            }
        }
        detail?.album?.let { album ->
            Primary("♫ Открыть альбом в Яндекс Музыке") {
                runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, album.url.toUri())) }
            }
        }
        if (detail?.ownerId == s.data.profile?.id) {
            Primary("Настройки костра", !s.busy) { vm.editBonfire(false) }
        } else {
            OutlinedButton(onClick = { leaving = true }, modifier = Modifier.fillMaxWidth(), enabled = !s.busy) { Text("Покинуть костёр", color = ErrorColor) }
        }
    }
    if (leaving) {
        Confirm(
            "Покинуть костёр?",
            "Чат исчезнет из ваших костров. В закрытый можно вернуться только по приглашению.",
            { leaving = false },
            {
                leaving = false
                s.data.profile?.id?.let(vm::removeMember)
            },
        )
    }
}
