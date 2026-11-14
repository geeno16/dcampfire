import java.net.URI
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.time.Duration
import org.openapitools.generator.gradle.plugin.tasks.GenerateTask

plugins {
    alias(libs.plugins.kotlin.jvm)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.openapi.generator)
}

kotlin {
    jvmToolchain(17)
}

abstract class FetchOpenApi : DefaultTask() {
    @get:Input
    abstract val url: Property<String>

    @get:OutputFile
    abstract val schema: RegularFileProperty

    @TaskAction
    fun fetch() {
        val target = schema.get().asFile
        val body = try {
            val client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build()
            val request = HttpRequest
                .newBuilder(URI(url.get()))
                .timeout(Duration.ofSeconds(10))
                .build()
            val response = client.send(request, HttpResponse.BodyHandlers.ofString())
            check(response.statusCode() == 200) { "HTTP ${response.statusCode()}" }
            response.body()
        } catch (e: Exception) {
            val reason = e.message ?: e.javaClass.simpleName
            if (target.exists()) {
                logger.warn(
                    "OpenAPI schema unavailable at ${url.get()} ($reason), using cached ${target.name}",
                )
                return
            }
            throw GradleException(
                "OpenAPI schema unavailable at ${url.get()} ($reason). " +
                    "Start the backend: docker compose up -d --build app-prod",
            )
        }
        if (!target.exists() || target.readText() != body) {
            target.parentFile.mkdirs()
            target.writeText(body)
        }
    }
}

val fetchOpenApi = tasks.register<FetchOpenApi>("fetchOpenApi") {
    group = "openapi"
    url.set(
        providers
            .gradleProperty("dcampfire.openapiUrl")
            .orElse("http://localhost:8001/openapi.json"),
    )
    schema.set(layout.buildDirectory.file("openapi/openapi.json"))
    outputs.upToDateWhen { false }
}

val openApiGenerate = tasks.named<GenerateTask>("openApiGenerate") {
    generatorName.set("kotlin")
    library.set("jvm-retrofit2")
    inputSpec.set(fetchOpenApi.flatMap { it.schema })
    outputDir.set(layout.buildDirectory.dir("generated/openapi"))
    packageName.set("ru.dcampfire.api")
    cleanupOutput.set(true)
    generateApiTests.set(false)
    generateModelTests.set(false)
    generateApiDocumentation.set(false)
    generateModelDocumentation.set(false)
    openapiNormalizer.set(mapOf("SIMPLIFY_ONEOF_ANYOF" to "true"))
    configOptions.set(
        mapOf(
            "serializationLibrary" to "kotlinx_serialization",
            "useCoroutines" to "true",
            "dateLibrary" to "java8",
            "enumPropertyNaming" to "UPPERCASE",
            "omitGradleWrapper" to "true",
            "omitGradlePluginVersions" to "true",
        ),
    )
}

sourceSets {
    main {
        kotlin.srcDir(openApiGenerate.flatMap { it.outputDir.dir("src/main/kotlin") })
    }
}

dependencies {
    api(libs.retrofit)
    api(libs.okhttp)
    api(libs.kotlinx.serialization.json)
    api(libs.kotlinx.coroutines.core)
    implementation(libs.retrofit.kotlinx.serialization)
    implementation(libs.retrofit.scalars)
    implementation(libs.okhttp.logging)
}
