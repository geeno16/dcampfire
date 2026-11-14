package ru.dcampfire

import android.os.Build

object BackendUrl {
    private val isEmulator: Boolean
        get() = Build.HARDWARE in setOf("ranchu", "goldfish")

    val value: String
        get() = if (isEmulator) BuildConfig.EMULATOR_BASE_URL else BuildConfig.BASE_URL
}
