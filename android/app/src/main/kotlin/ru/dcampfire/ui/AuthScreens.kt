package ru.dcampfire.ui

import android.util.Patterns
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import ru.dcampfire.CampfireViewModel
import ru.dcampfire.Screen

@Composable
fun LoginScreen(vm: CampfireViewModel) {
    val s = vm.state
    var email by rememberSaveable { mutableStateOf(s.email) }
    var password by remember { mutableStateOf("") }
    Page("") {
        Fire(modifier = Modifier.size(112.dp).align(Alignment.CenterHorizontally))
        Text("КОСТЁР", Modifier.align(Alignment.CenterHorizontally), color = Orange, style = MaterialTheme.typography.labelLarge)
        Text("С возвращением", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Text("Ваши костры всё ещё горят", color = Muted)
        Spacer(Modifier.height(18.dp))
        Field(email, { email = it }, "Адрес почты", s.fields["email"], keyboard = KeyboardType.Email)
        Field(password, { password = it }, "Пароль", password = true)
        Spacer(Modifier.height(20.dp))
        Primary("Войти", !s.busy && email.isNotBlank() && password.isNotEmpty()) { vm.login(email, password) }
        TextButton(onClick = { vm.navigate(Screen.REGISTER) }, modifier = Modifier.align(Alignment.CenterHorizontally)) { Text("Нет аккаунта? Зарегистрироваться") }
    }
}

@Composable
fun RegisterScreen(vm: CampfireViewModel) {
    val s = vm.state
    var nickname by rememberSaveable { mutableStateOf("") }
    var email by rememberSaveable { mutableStateOf(s.email) }
    var password by remember { mutableStateOf("") }
    var repeat by remember { mutableStateOf("") }
    var consent by rememberSaveable { mutableStateOf(false) }
    Page("КОСТЁР") {
        Text("Разжечь свой\nпервый костёр", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Text("Истории в кругу до пяти человек. Без ленты, без чужих.", color = Muted)
        Field(nickname, { nickname = it }, "Псевдоним", s.fields["nickname"])
        Field(email, { email = it }, "Адрес почты", s.fields["email"], keyboard = KeyboardType.Email)
        Field(password, { password = it }, "Пароль", s.fields["password"], password = true)
        Field(repeat, { repeat = it }, "Повторите пароль", s.fields["repeat"], password = true)
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth().clickable { consent = !consent }) {
            Checkbox(consent, { consent = it })
            Text("Согласен на обработку персональных данных для регистрации и общения в приложении.", style = MaterialTheme.typography.bodySmall)
        }
        Text("Почта видна только вам. Данные хранятся на вашем локальном сервере; аккаунт можно удалить в профиле.", color = Muted, style = MaterialTheme.typography.bodySmall)
        Primary("Зарегистрироваться", consent && !s.busy) {
            val errors = buildMap {
                if (nickname.trim().length !in (s.limits?.nicknameMinLength ?: 3)..(s.limits?.nicknameMaxLength ?: 20)) put("nickname", "Псевдоним: от 3 до 20 символов.")
                if (!Patterns.EMAIL_ADDRESS.matcher(email.trim()).matches()) put("email", "Введите корректный адрес почты.")
                if (password.length !in (s.limits?.passwordMinLength ?: 8)..128) put("password", "Пароль: от 8 до 128 символов.")
                if (password != repeat) put("repeat", "Пароли не совпадают.")
            }
            if (errors.isEmpty()) vm.register(nickname, email, password) else vm.validation(errors)
        }
        TextButton(onClick = { vm.navigate(Screen.LOGIN) }, modifier = Modifier.align(Alignment.CenterHorizontally)) { Text("Уже есть аккаунт? Войти") }
    }
}

@Composable
fun secondsUntil(timestamp: Long): Int {
    var now by remember { mutableLongStateOf(System.currentTimeMillis()) }
    LaunchedEffect(timestamp) {
        do {
            now = System.currentTimeMillis()
            delay(200)
        } while (now < timestamp)
    }
    return ((timestamp - now + 999) / 1000).coerceAtLeast(0).toInt()
}

@Composable
fun VerifyScreen(vm: CampfireViewModel) {
    val s = vm.state
    var code by rememberSaveable { mutableStateOf("") }
    val remaining = secondsUntil(s.resendAt)
    Page("Подтверждение почты", vm::back) {
        Text("Письмо уже летит", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Text("Код из 6 цифр отправлен на ${s.email}. Он действует ${(s.limits?.emailCodeTtlSeconds ?: 600) / 60} минут.", color = Muted)
        Field(code, { code = it.filter { c -> c in '0'..'9' }.take(6) }, "Код из письма", s.fields["code"], keyboard = KeyboardType.NumberPassword)
        Primary("Подтвердить", code.length == 6 && !s.busy) { vm.verify(code) }
        TextButton(onClick = vm::resend, enabled = remaining == 0 && !s.busy) { Text(if (remaining == 0) "Отправить код повторно" else "Повторная отправка через $remaining с") }
    }
}

@Composable
fun TopicScreen(vm: CampfireViewModel) {
    val s = vm.state
    var chosen by remember(s.data.profile?.id) { mutableStateOf(s.data.profile?.topics.orEmpty().map { it.id }) }
    Page("Ваши интересы", vm::back) {
        Text("О чём хочется\nговорить у огня?", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Text("По этим темам подберём костры. До ${s.limits?.userTopicsMax ?: 10}, потом можно поменять.", color = Muted)
        Topics(s.data.topics, chosen, s.limits?.userTopicsMax ?: 10, { chosen = it })
        if (s.data.topics.isEmpty()) TextButton(onClick = vm::refresh) { Text("Загрузить темы") }
        Primary("К кострам", !s.busy) { vm.setTopics(chosen) }
    }
}
