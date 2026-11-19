package ru.dcampfire.data

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.io.File
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Encrypt token and personal cache with a non-exportable Android Keystore key. */
class SecureStore(context: Context) {
    private val directory = File(context.noBackupFilesDir, "campfire").apply { mkdirs() }
    private val key: SecretKey by lazy {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey("campfire.local.v1", null) as? SecretKey) ?: run {
            KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
                init(
                    KeyGenParameterSpec.Builder(
                        "campfire.local.v1",
                        KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
                    )
                        .setBlockModes(
                            KeyProperties.BLOCK_MODE_GCM,
                        ).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build(),
                )
            }.generateKey()
        }
    }

    @Synchronized
    fun read(name: String): String? = runCatching {
        val data = File(directory, name).takeIf { it.isFile }?.readBytes() ?: return null
        require(data.size > 12)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(128, data.copyOfRange(0, 12)))
        String(cipher.doFinal(data.copyOfRange(12, data.size)), Charsets.UTF_8)
    }.getOrNull()

    @Synchronized
    fun write(name: String, text: String) {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key)
        val temp = File(directory, "$name.tmp")
        temp.outputStream().use {
            it.write(cipher.iv + cipher.doFinal(text.toByteArray(Charsets.UTF_8)))
        }
        check(temp.renameTo(File(directory, name)))
    }

    @Synchronized
    fun clear() {
        directory.listFiles()?.forEach { it.delete() }
    }
}
