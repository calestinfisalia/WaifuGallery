plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
}

val releaseSigningEnvironment = mapOf(
    "WAIFU_RELEASE_KEYSTORE_PATH" to providers.environmentVariable("WAIFU_RELEASE_KEYSTORE_PATH").orNull.orEmpty(),
    "WAIFU_RELEASE_STORE_PASSWORD" to providers.environmentVariable("WAIFU_RELEASE_STORE_PASSWORD").orNull.orEmpty(),
    "WAIFU_RELEASE_KEY_PASSWORD" to providers.environmentVariable("WAIFU_RELEASE_KEY_PASSWORD").orNull.orEmpty(),
)
val releaseSigningConfigured = releaseSigningEnvironment.values.all(String::isNotBlank)

android {
    namespace = "com.fisaliaproject.waifugallery"
    compileSdk = 37

    defaultConfig {
        applicationId = "com.fisaliaproject.waifugallery"
        minSdk = 29
        targetSdk = 37
        versionCode = 31
        versionName = "0.1.33"
    }

    buildFeatures {
        compose = true
    }

    signingConfigs {
        if (releaseSigningConfigured) {
            create("release") {
                storeFile = file(releaseSigningEnvironment.getValue("WAIFU_RELEASE_KEYSTORE_PATH"))
                storeType = "PKCS12"
                storePassword = releaseSigningEnvironment.getValue("WAIFU_RELEASE_STORE_PASSWORD")
                keyAlias = "waifugallery-release"
                keyPassword = releaseSigningEnvironment.getValue("WAIFU_RELEASE_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            if (releaseSigningConfigured) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

val verifyReleaseSigning = tasks.register("verifyReleaseSigning") {
    doLast {
        val requiredVariables = listOf(
            "WAIFU_RELEASE_KEYSTORE_PATH",
            "WAIFU_RELEASE_STORE_PASSWORD",
            "WAIFU_RELEASE_KEY_PASSWORD",
        )
        val missingVariables = requiredVariables.filter {
            releaseSigningEnvironment.getValue(it).isBlank()
        }
        if (missingVariables.isNotEmpty()) {
            throw GradleException(
                "Release signing requires these environment variables: ${missingVariables.joinToString()}",
            )
        }
        if (!file(releaseSigningEnvironment.getValue("WAIFU_RELEASE_KEYSTORE_PATH")).isFile) {
            throw GradleException("The configured release keystore file does not exist.")
        }
    }
}

tasks.configureEach {
    if (name == "preReleaseBuild" || name == "assembleRelease" || name == "packageRelease") {
        dependsOn(verifyReleaseSigning)
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2026.09.00")
    implementation(composeBom)

    implementation("androidx.core:core-ktx:1.17.0")
    implementation("androidx.activity:activity-compose:1.12.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.10.0")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.10.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.10.0")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:okhttp-dnsoverhttps:4.12.0")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
    implementation("io.coil-kt:coil-compose:2.7.0")
    implementation("androidx.documentfile:documentfile:1.1.0")

    debugImplementation("androidx.compose.ui:ui-tooling")
}
