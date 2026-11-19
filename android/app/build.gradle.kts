import java.io.ByteArrayOutputStream
import javax.inject.Inject

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.detekt)
}

val backendPort = providers.gradleProperty("dcampfire.backendPort").getOrElse("8001")
val debugApiUrl = providers.gradleProperty(
    "dcampfire.debugApiUrl",
).getOrElse("http://localhost:$backendPort/")
val releaseApiUrl = providers
    .gradleProperty("dcampfire.releaseApiUrl")
    .getOrElse("https://dcampfire.invalid/")

android {
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    namespace = "ru.dcampfire"
    compileSdk = 37

    defaultConfig {
        applicationId = "ru.dcampfire"
        minSdk = 26
        targetSdk = 37
        versionCode = 2
        versionName = "0.1.1"
    }

    androidResources {
        localeFilters += "ru"
    }

    buildTypes {
        debug {
            buildConfigField("String", "BASE_URL", "\"$debugApiUrl\"")
            buildConfigField("String", "EMULATOR_BASE_URL", "\"http://10.0.2.2:$backendPort/\"")
        }
        release {
            buildConfigField("String", "BASE_URL", "\"$releaseApiUrl\"")
            buildConfigField("String", "EMULATOR_BASE_URL", "\"$releaseApiUrl\"")
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"))
        }
    }

    lint {
        warningsAsErrors = true
        abortOnError = true
        checkDependencies = false
        disable += setOf(
            "GradleDependency",
            "NewerVersionAvailable",
            "AndroidGradlePluginVersion",
            "OldTargetApi",
        )
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }
}

kotlin {
    jvmToolchain(21)
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

detekt {
    buildUponDefaultConfig = true
    config.setFrom(rootProject.file("config/detekt/detekt.yml"))
    source.setFrom(
        "src/main/kotlin",
        "src/debug/kotlin",
        "src/test/kotlin",
        "src/androidTest/kotlin",
    )
}

dependencies {
    implementation(project(":api"))
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.ui.tooling.preview)
    implementation(libs.compose.material3)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.kotlinx.coroutines.android)
    debugImplementation(libs.compose.ui.tooling)
}

abstract class DevTask : DefaultTask() {
    @get:Inject
    abstract val exec: ExecOperations

    protected fun findTool(name: String): String {
        val home = System.getProperty("user.home")
        val dirs = System.getenv("PATH").orEmpty().split(File.pathSeparator) +
            listOf("/usr/local/bin", "/opt/homebrew/bin", "$home/.orbstack/bin")
        return dirs.map { File(it, name) }.firstOrNull { it.canExecute() }?.absolutePath
            ?: throw GradleException("$name not found in PATH")
    }
}

abstract class StartBackend : DevTask() {
    @get:Internal
    abstract val composeDir: DirectoryProperty

    @TaskAction
    fun start() {
        exec.exec {
            workingDir = composeDir.get().asFile
            commandLine(findTool("docker"), "compose", "up", "-d", "--build", "--wait", "app-prod")
        }
    }
}

abstract class AdbReverse : DevTask() {
    @get:Internal
    abstract val adb: RegularFileProperty

    @get:Input
    abstract val port: Property<String>

    @TaskAction
    fun reverse() {
        val adbPath = adb.get().asFile.absolutePath
        val output = ByteArrayOutputStream()
        exec.exec {
            commandLine(adbPath, "devices")
            standardOutput = output
        }
        val serials = output.toString().lines().drop(1)
            .map { it.split("\t") }
            .filter { it.size == 2 && it[1] == "device" }
            .map { it[0] }
            .filterNot { it.startsWith("emulator-") }
        if (serials.isEmpty()) {
            logger.lifecycle("No physical devices connected, adb reverse skipped")
            return
        }
        serials.forEach { serial ->
            exec.exec {
                commandLine(
                    adbPath,
                    "-s",
                    serial,
                    "reverse",
                    "tcp:${port.get()}",
                    "tcp:${port.get()}",
                )
            }
            logger.lifecycle("adb reverse tcp:${port.get()} on $serial")
        }
    }
}

val startBackend = tasks.register<StartBackend>("startBackend") {
    group = "dev"
    composeDir.set(rootProject.layout.projectDirectory.dir(".."))
    outputs.upToDateWhen { false }
}

val adbReverse = tasks.register<AdbReverse>("adbReverse") {
    group = "dev"
    adb.set(androidComponents.sdkComponents.adb)
    port.set(backendPort)
    outputs.upToDateWhen { false }
}

tasks.register("devUp") {
    group = "dev"
    dependsOn(startBackend, adbReverse)
}
