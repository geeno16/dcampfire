package ru.dcampfire.ui

import android.graphics.BitmapFactory
import androidx.compose.animation.core.*
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.*
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.*
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import ru.dcampfire.api.models.TopicRead
import ru.dcampfire.client.CampfireClient

val Cream = Color(0xFFEAD6B5)
val Muted = Color(0xFFC4B8AD)
val Panel = Color(0xFF211D22)
val Orange = Color(0xFFF7A061)
val ErrorColor = Color(0xFFFFB4AB)

@Composable
fun CampfireTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = darkColorScheme(
            primary = Cream,
            onPrimary = Color(0xFF241B13),
            secondary = Orange,
            background = Color(0xFF101018),
            onBackground = Color(0xFFF7F0E7),
            surface = Panel,
            onSurface = Color(0xFFF7F0E7),
            onSurfaceVariant = Muted,
            error = ErrorColor,
        ),
    ) {
        // MaterialTheme does not itself set LocalContentColor outside a Surface.
        // Our pages draw directly on a custom night background.
        CompositionLocalProvider(LocalContentColor provides MaterialTheme.colorScheme.onBackground) {
            content()
        }
    }
}

@Composable
fun NightBackground(content: @Composable BoxScope.() -> Unit) {
    Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(Color(0xFF171E36), Color(0xFF0B0A0B), Color(0xFF171008))))) {
        Canvas(Modifier.fillMaxSize()) {
            repeat(55) { i ->
                drawCircle(
                    Cream.copy(alpha = .12f + (i % 3) * .06f),
                    1.1f,
                    Offset(((i * 71 + 13) % 101) / 101f * size.width, ((i * 29 + 7) % 97) / 97f * size.height * .65f),
                )
            }
        }
        content()
    }
}

@Composable
fun Fire(modifier: Modifier = Modifier, color: Color = Orange) {
    val transition = rememberInfiniteTransition(label = "fire")
    val glow by transition.animateFloat(.12f, .23f, infiniteRepeatable(tween(1400), RepeatMode.Reverse), label = "glow")
    Canvas(modifier.semantics { contentDescription = "Костёр" }) {
        val unit = minOf(size.width / 12, size.height / 15)
        val origin = Offset((size.width - unit * 10) / 2, (size.height - unit * 13) / 2)
        drawCircle(Brush.radialGradient(listOf(color.copy(alpha = glow), Color.Transparent)), size.minDimension / 2, center)
        val rows = listOf(
            "    1     ", "    11    ", "   111    ", "   121    ", "  1221    ", " 112211   ",
            " 1222211  ", "112332211 ", "1223332211", "1223333221", " 12333221 ", "  122221  ",
        )
        rows.forEachIndexed { y, row ->
            row.forEachIndexed { x, ch ->
                val c = when (ch) {
                    '1' -> color
                    '2' -> Color(0xFFFFCB79)
                    '3' -> Color(0xFFFFECD2)
                    else -> null
                }
                if (c != null) drawRect(c, origin + Offset(unit * x, unit * y), Size(unit + .4f, unit + .4f))
            }
        }
        drawRect(Color(0xFF6E4635), origin + Offset(unit, unit * 12), Size(unit * 8, unit))
        drawRect(Color(0xFFAA7650), origin + Offset(unit * 2, unit * 13), Size(unit * 6, unit))
    }
}
fun fireColor(key: String): Color = when (key) {
    "red" -> Color(0xFFE5534B)
    "yellow" -> Color(0xFFF2C94C)
    "green" -> Color(0xFF5CC76A)
    "teal" -> Color(0xFF3FCFBE)
    "blue" -> Color(0xFF4F9DF0)
    "purple" -> Color(0xFFB07CF2)
    "pink" -> Color(0xFFF06FB5)
    else -> Orange
}

@Composable
fun Page(title: String, onBack: (() -> Unit)? = null, content: @Composable ColumnScope.() -> Unit) {
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).imePadding().padding(horizontal = 22.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Header(title, onBack)
        content()
        Spacer(Modifier.height(12.dp))
    }
}

@Composable
fun Header(title: String, onBack: (() -> Unit)? = null) {
    Row(Modifier.fillMaxWidth().heightIn(min = 48.dp), verticalAlignment = Alignment.CenterVertically) {
        if (onBack != null) {
            TextButton(onClick = onBack, contentPadding = PaddingValues(0.dp), modifier = Modifier.size(48.dp)) {
                Text("‹", style = MaterialTheme.typography.headlineMedium, modifier = Modifier.semantics { contentDescription = "Назад" })
            }
        }
        Text(title, Modifier.weight(1f), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
    }
}

@Composable
fun Primary(label: String, enabled: Boolean = true, onClick: () -> Unit) {
    Button(onClick, Modifier.fillMaxWidth().heightIn(min = 50.dp), enabled = enabled, shape = RoundedCornerShape(28.dp)) {
        Text(label, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
fun Field(value: String, onValue: (String) -> Unit, label: String, error: String? = null, password: Boolean = false, keyboard: KeyboardType = KeyboardType.Text, enabled: Boolean = true) {
    var showPassword by remember { mutableStateOf(false) }
    OutlinedTextField(
        value, onValue, Modifier.fillMaxWidth(), enabled = enabled, singleLine = true, label = { Text(label) },
        shape = RoundedCornerShape(16.dp), isError = error != null,
        supportingText = if (error != null) ({ Text(error, color = ErrorColor) }) else null,
        keyboardOptions = KeyboardOptions(keyboardType = if (password) KeyboardType.Password else keyboard),
        visualTransformation = if (password && !showPassword) PasswordVisualTransformation() else VisualTransformation.None,
        trailingIcon = if (password) {
            (
                {
                    TextButton(onClick = { showPassword = !showPassword }) {
                        Text(if (showPassword) "Скрыть" else "Показать", style = MaterialTheme.typography.labelSmall)
                    }
                }
                )
        } else {
            null
        },
        colors = OutlinedTextFieldDefaults.colors(
            unfocusedContainerColor = Panel.copy(alpha = .75f),
            focusedContainerColor = Panel,
            unfocusedBorderColor = Color(0xFF6F656A),
        ),
    )
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun Topics(topics: List<TopicRead>, selected: List<Int>, max: Int, onChange: (List<Int>) -> Unit) {
    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
        topics.forEach { topic ->
            FilterChip(selected = topic.id in selected, onClick = {
                onChange(if (topic.id in selected) selected - topic.id else (selected + topic.id).take(max))
            }, enabled = topic.id in selected || selected.size < max, label = { Text(topic.name) })
        }
    }
    Text("Выбрано тем: ${selected.size} / $max", color = Muted, style = MaterialTheme.typography.bodySmall)
}

@Composable
fun Avatar(api: CampfireClient, nickname: String, path: String?, modifier: Modifier = Modifier) {
    val bitmap by produceState<ImageBitmap?>(null, path) {
        value = null
        if (path != null) {
            value = withContext(Dispatchers.IO) {
                runCatching {
                    api.http.newCall(api.avatarRequest(path)).execute().use { response ->
                        if (!response.isSuccessful) return@use null
                        val bytes = response.body.bytes()
                        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
                        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
                        val options = BitmapFactory.Options().apply { inSampleSize = maxOf(1, maxOf(bounds.outWidth, bounds.outHeight) / 256) }
                        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, options)?.asImageBitmap()
                    }
                }.getOrNull()
            }
        }
    }
    Box(modifier.size(48.dp).clip(CircleShape).background(Panel).border(1.dp, Orange.copy(alpha = .65f), CircleShape), contentAlignment = Alignment.Center) {
        val image = bitmap
        if (image != null) {
            Image(image, "Аватар $nickname", Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
        } else {
            Text(nickname.take(2).uppercase(), fontWeight = FontWeight.Bold, color = Cream)
        }
    }
}

@Composable
fun Confirm(title: String, text: String, onDismiss: () -> Unit, onConfirm: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = { Text(text) },
        confirmButton = { TextButton(onClick = onConfirm) { Text("Подтвердить", color = ErrorColor) } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Отмена") } },
    )
}
