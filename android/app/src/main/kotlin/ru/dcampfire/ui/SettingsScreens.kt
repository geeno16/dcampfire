package ru.dcampfire.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import ru.dcampfire.CampfireViewModel

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun EditScreen(vm: CampfireViewModel) {
    val s = vm.state
    val detail = if (s.creating) null else s.selected
    var name by rememberSaveable(s.creating, detail?.id) { mutableStateOf(detail?.name.orEmpty()) }
    var color by rememberSaveable(s.creating, detail?.id) { mutableStateOf(detail?.color ?: "orange") }
    var topics by remember(s.creating, detail?.id) { mutableStateOf(detail?.topics.orEmpty().map { it.id }) }
    var url by rememberSaveable(s.creating, detail?.id) { mutableStateOf(detail?.album?.url.orEmpty()) }
    var isOpen by rememberSaveable(s.creating, detail?.id) { mutableStateOf(detail?.isOpen ?: true) }
    var invitee by rememberSaveable { mutableStateOf("") }
    var lookupUrl by remember { mutableStateOf(detail?.album?.url.orEmpty()) }
    var deleting by remember { mutableStateOf(false) }
    var kicking by remember { mutableStateOf<Long?>(null) }
    val colors = s.data.config?.colors?.map { it.key } ?: listOf("orange", "red", "yellow", "green", "teal", "blue", "purple", "pink")
    Page(if (s.creating) "Ваш новый костёр" else "Настройки костра", vm::back) {
        Field(name, { name = it }, "Название", s.fields["name"])
        Text("Цвет костра", fontWeight = FontWeight.Bold)
        Fire(Modifier.size(100.dp).align(Alignment.CenterHorizontally), fireColor(color))
        FlowRow(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            colors.forEach { key ->
                Box(
                    Modifier.size(48.dp).padding(5.dp).clip(CircleShape).background(fireColor(key))
                        .border(if (color == key) 3.dp else 0.dp, Cream, CircleShape).clickable { color = key }
                        .semantics { contentDescription = "Цвет костра $key" },
                    contentAlignment = Alignment.Center,
                ) {
                    if (color == key) Text("✓", color = Color.Black)
                }
            }
        }
        Text("Темы", fontWeight = FontWeight.Bold)
        Topics(s.data.topics, topics, s.limits?.bonfireTopicsMax ?: 5, { topics = it })
        s.fields["topic_ids"]?.let { Text(it, color = ErrorColor) }
        Field(url, { url = it }, "Ссылка на альбом Яндекс Музыки", s.fields["album_url"] ?: s.fields["url"])
        TextButton(onClick = {
            lookupUrl = url
            vm.lookupAlbum(url)
        }, enabled = url.isNotBlank() && !s.busy) { Text("Проверить альбом") }
        if (url == lookupUrl && s.albumPreview != null) Text("♫ ${s.albumPreview}", color = Cream)
        Text("Ссылка необязательна. Музыка открывается отдельно и не включается автоматически.", color = Muted, style = MaterialTheme.typography.bodySmall)
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(if (isOpen) "Открытый костёр" else "Закрытый костёр", fontWeight = FontWeight.Bold)
                Text(if (isOpen) "Можно найти и присоединиться" else "Вход только по приглашению", color = Muted, style = MaterialTheme.typography.bodySmall)
            }
            Switch(isOpen, { isOpen = it })
        }
        Primary("Сохранить", !s.busy) {
            val errors = buildMap {
                if (name.trim().length !in (s.limits?.bonfireNameMinLength ?: 3)..(s.limits?.bonfireNameMaxLength ?: 40)) put("name", "Название: от 3 до 40 символов.")
                if (url.isNotBlank() && !Regex("https?://music\\.yandex\\.(ru|com|by|kz|uz)/album/[0-9]+.*").matches(url.trim())) {
                    put("album_url", "Нужна ссылка вида https://music.yandex.ru/album/123.")
                }
            }
            if (errors.isEmpty()) vm.saveBonfire(name, color, topics, url, isOpen) else vm.validation(errors)
        }
        OutlinedButton(onClick = vm::back, modifier = Modifier.fillMaxWidth(), enabled = !s.busy) { Text("Отмена") }
        if (detail != null) {
            HorizontalDivider()
            Text("Участники · ${detail.membersCount} / ${s.limits?.bonfireCapacity ?: 5}", fontWeight = FontWeight.Bold)
            detail.members.forEach { member ->
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Avatar(vm.api, member.nickname, member.avatarUrl, Modifier.size(40.dp))
                    Text(member.nickname, Modifier.weight(1f).padding(start = 10.dp))
                    if (member.id == detail.ownerId) {
                        Text("ХОЗЯИН", color = Muted, style = MaterialTheme.typography.labelSmall)
                    } else {
                        TextButton(onClick = { kicking = member.id }, enabled = !s.busy) { Text("Удалить", color = ErrorColor) }
                    }
                }
            }
            Field(invitee, { invitee = it }, "Пригласить по псевдониму", s.fields["nickname"])
            Primary("Позвать к костру", !s.busy && invitee.trim().length >= 3 && detail.membersCount < (s.limits?.bonfireCapacity ?: 5)) { vm.invite(invitee) }
            detail.invitations.orEmpty().forEach { invitation ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("Ждём ${invitation.user.nickname}", Modifier.weight(1f), color = Muted)
                    TextButton(onClick = { vm.cancelInvitation(invitation.user.id) }, enabled = !s.busy) { Text("Отменить") }
                }
            }
            OutlinedButton(onClick = { deleting = true }, modifier = Modifier.fillMaxWidth(), enabled = !s.busy) { Text("Удалить костёр", color = ErrorColor) }
        }
    }
    if (deleting) {
        Confirm(
            "Удалить костёр?",
            "Костёр и вся его переписка будут удалены для всех участников.",
            { deleting = false },
            {
                deleting = false
                vm.deleteBonfire()
            },
        )
    }
    kicking?.let { id ->
        Confirm(
            "Удалить участника?",
            "Участник потеряет доступ к этому чату.",
            { kicking = null },
            {
                kicking = null
                vm.removeMember(id)
            },
        )
    }
}

@Composable
fun ProfileScreen(vm: CampfireViewModel) {
    val s = vm.state
    val profile = s.data.profile
    var nickname by rememberSaveable(profile?.id) { mutableStateOf(profile?.nickname.orEmpty()) }
    var current by remember { mutableStateOf("") }
    var new by remember { mutableStateOf("") }
    var chosen by remember(profile?.id) { mutableStateOf(profile?.topics.orEmpty().map { it.id }) }
    var logout by remember { mutableStateOf(false) }
    var delete by remember { mutableStateOf(false) }
    var deletePassword by remember { mutableStateOf("") }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri -> uri?.let(vm::uploadAvatar) }
    LaunchedEffect(s.notice) {
        if (s.notice == "Пароль изменён.") {
            current = ""
            new = ""
        }
    }
    Page("Профиль", vm::back) {
        Avatar(vm.api, profile?.nickname.orEmpty(), profile?.avatarUrl, Modifier.size(100.dp).align(Alignment.CenterHorizontally))
        Row(Modifier.align(Alignment.CenterHorizontally)) {
            TextButton(onClick = { picker.launch("image/*") }, enabled = !s.busy) { Text("Изменить фото") }
            TextButton(onClick = vm::deleteAvatar, enabled = profile?.avatarUrl != null && !s.busy) { Text("Удалить") }
        }
        Text("JPEG или PNG до 5 МБ. Новое фото заменит прежнее.", color = Muted, style = MaterialTheme.typography.bodySmall)
        s.fields["file"]?.let { Text(it, color = ErrorColor) }
        Field(nickname, { nickname = it }, "Псевдоним", s.fields["nickname"])
        Primary("Сохранить псевдоним", !s.busy && nickname.trim() != profile?.nickname) {
            if (nickname.trim().length in (s.limits?.nicknameMinLength ?: 3)..(s.limits?.nicknameMaxLength ?: 20)) {
                vm.updateNickname(nickname)
            } else {
                vm.validation(mapOf("nickname" to "Псевдоним: от 3 до 20 символов."))
            }
        }
        Text("Адрес почты", color = Muted, style = MaterialTheme.typography.labelMedium)
        Text(profile?.email.orEmpty())
        Text("Виден только вам. Изменить адрес нельзя.", color = Muted, style = MaterialTheme.typography.bodySmall)
        HorizontalDivider()
        Text("Пароль", fontWeight = FontWeight.Bold)
        Field(current, { current = it }, "Текущий пароль", password = true)
        Field(new, { new = it }, "Новый пароль", s.fields["new_password"], password = true)
        Primary("Изменить пароль", !s.busy && current.isNotEmpty()) {
            if (new.length in (s.limits?.passwordMinLength ?: 8)..128) {
                vm.changePassword(current, new)
            } else {
                vm.validation(mapOf("new_password" to "Пароль: от 8 до 128 символов."))
            }
        }
        HorizontalDivider()
        Text("Мои темы", fontWeight = FontWeight.Bold)
        Topics(s.data.topics, chosen, s.limits?.userTopicsMax ?: 10, { chosen = it })
        Primary("Сохранить интересы", !s.busy) { vm.setTopics(chosen, returnHome = false) }
        TextButton(onClick = { logout = true }, enabled = !s.busy) { Text("Выйти из аккаунта") }
        TextButton(onClick = { delete = true }, enabled = !s.busy) { Text("Удалить аккаунт", color = ErrorColor) }
    }
    if (logout) {
        Confirm(
            "Выйти из аккаунта?",
            "Сохранённые на устройстве данные будут очищены.",
            { logout = false },
            {
                logout = false
                vm.logout()
            },
        )
    }
    if (delete) {
        AlertDialog(
            onDismissRequest = {
                if (!s.busy) {
                    delete = false
                    deletePassword = ""
                }
            },
            title = { Text("Удалить аккаунт?") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("Ваши костры будут удалены. В чужих чатах сообщения останутся без имени автора. Действие нельзя отменить.")
                    Field(deletePassword, { deletePassword = it }, "Пароль для подтверждения", password = true)
                    s.error?.let { Text(it, color = ErrorColor) }
                }
            },
            confirmButton = { TextButton(onClick = { vm.deleteAccount(deletePassword) }, enabled = deletePassword.isNotEmpty() && !s.busy) { Text("Удалить", color = ErrorColor) } },
            dismissButton = {
                TextButton(onClick = {
                    delete = false
                    deletePassword = ""
                }, enabled = !s.busy) { Text("Отмена") }
            },
        )
    }
}
