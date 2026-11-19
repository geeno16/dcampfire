package ru.dcampfire

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.viewmodel.compose.viewModel
import ru.dcampfire.ui.*

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent { CampfireApp() }
    }
}

@Composable
fun CampfireApp(vm: CampfireViewModel = viewModel()) {
    val state = vm.state
    val lifecycle = LocalLifecycleOwner.current
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, event -> if (event == Lifecycle.Event.ON_START) vm.refresh() }
        lifecycle.lifecycle.addObserver(observer)
        onDispose { lifecycle.lifecycle.removeObserver(observer) }
    }
    BackHandler(state.screen !in setOf(Screen.LOGIN, Screen.REGISTER, Screen.HOME)) { vm.back() }
    CampfireTheme {
        NightBackground {
            Column(Modifier.fillMaxSize().safeDrawingPadding()) {
                if (state.busy || state.refreshing) LinearProgressIndicator(Modifier.fillMaxWidth())
                if (state.offline) {
                    Surface(color = Panel) {
                        Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                            Text("Нет связи. Показаны сохранённые данные.", Modifier.weight(1f), color = Cream, style = MaterialTheme.typography.bodySmall)
                            TextButton(onClick = vm::refresh) { Text("Повторить") }
                        }
                    }
                }
                val announcement = state.error ?: state.notice
                if (announcement != null) {
                    Surface(color = Panel) {
                        Row(Modifier.fillMaxWidth().padding(start = 16.dp), verticalAlignment = Alignment.CenterVertically) {
                            Text(announcement, Modifier.weight(1f), color = if (state.error != null) ErrorColor else Cream, style = MaterialTheme.typography.bodySmall)
                            TextButton(onClick = vm::clearError) { Text("ОК") }
                        }
                    }
                }
                Box(Modifier.weight(1f)) {
                    when (state.screen) {
                        Screen.LOGIN -> LoginScreen(vm)
                        Screen.REGISTER -> RegisterScreen(vm)
                        Screen.VERIFY -> VerifyScreen(vm)
                        Screen.TOPICS -> TopicScreen(vm)
                        Screen.HOME -> HomeScreen(vm)
                        Screen.CHAT -> ChatScreen(vm)
                        Screen.MEMBERS -> MembersScreen(vm)
                        Screen.EDIT -> EditScreen(vm)
                        Screen.PROFILE -> ProfileScreen(vm)
                    }
                }
            }
        }
    }
}
