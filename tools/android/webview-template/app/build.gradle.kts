// Kotlin vem embutido no AGP 9 (sem o plugin org.jetbrains.kotlin.android).
plugins {
    id("com.android.application")
}

android {
    namespace = "com.anastaciogames.rangewebview"
    compileSdk = 37

    defaultConfig {
        applicationId = "com.anastaciogames.rangewebview"
        // minSdk 24 e hipotese de cobertura (docs/android-export-plan.md, secao 5).
        minSdk = 24
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"
    }

    // Chave do release pelo ambiente (range_web/android.py): a senha nao fica em arquivo do projeto.
    val keystore = System.getenv("RANGE_ANDROID_KEYSTORE")
    signingConfigs {
        if (keystore != null) {
            create("range") {
                storeFile = file(keystore)
                storePassword = System.getenv("RANGE_ANDROID_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("RANGE_ANDROID_KEY_ALIAS")
                // PKCS12 (keytool padrao) usa a mesma senha para o arquivo e a chave.
                keyPassword = System.getenv("RANGE_ANDROID_KEYSTORE_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            if (keystore != null) {
                signingConfig = signingConfigs.getByName("range")
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    androidResources {
        // .wasm e .data ja sao binarios; manter sem compressao evita descompactar na carga.
        noCompress += listOf("wasm", "data")
    }
}

dependencies {
    implementation("androidx.core:core:1.19.1")
    implementation("androidx.webkit:webkit:1.17.1")
}
