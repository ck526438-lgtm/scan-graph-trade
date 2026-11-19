plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

// Version lue dans le paquet Python (une seule source de vérité)
val sgtVersion: String = file("../../src/scan_graph_trade/__init__.py").readLines()
    .first { it.startsWith("__version__") }.substringAfter("\"").substringBefore("\"")

android {
    namespace = "com.ck526438.scangraphtrade"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.ck526438.scangraphtrade"
        minSdk = 24
        targetSdk = 34
        versionCode = sgtVersion.split(".").fold(0) { acc, p -> acc * 100 + (p.toIntOrNull() ?: 0) }
        versionName = sgtVersion
        ndk {
            // OpenCV pour Python 3.10 existe pour ces architectures (téléphones 64 et 32 bits + émulateur)
            abiFilters += listOf("arm64-v8a", "armeabi-v7a", "x86_64")
        }
    }

    signingConfigs {
        // Signature stable si les secrets GitHub sont fournis, sinon clé de debug
        val ks = System.getenv("SGT_KEYSTORE")
        if (ks != null && file(ks).exists()) {
            create("release") {
                storeFile = file(ks)
                storePassword = System.getenv("SGT_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("SGT_KEY_ALIAS")
                keyPassword = System.getenv("SGT_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.findByName("release") ?: signingConfigs.getByName("debug")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

chaquopy {
    defaultConfig {
        version = "3.10"  // seule version de Python avec OpenCV précompilé pour Android
        System.getenv("SGT_BUILD_PYTHON")?.let { buildPython(it) }
        pip {
            install("numpy==1.23.3")
            install("opencv-python==4.5.1.48")
        }
        pyc {
            src = true
        }
    }
    sourceSets {
        getByName("main") {
            srcDir("src/main/python")
            srcDir("../../src")  // le moteur Scan Graph Trade lui-même
        }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.activity:activity-ktx:1.9.1")
    // OCR hors ligne (modèle latin intégré à l'APK)
    implementation("com.google.mlkit:text-recognition:16.0.1")
}
