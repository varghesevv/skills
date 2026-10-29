plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "com.example.skills.skills_app"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // Placeholder until Q-A1 (app name and application ID) is answered; it cannot change after
        // the first store upload. See docs/android/understanding.md.
        applicationId = "com.example.skills.dev"
        minSdk = maxOf(26, flutter.minSdkVersion)
        targetSdk = flutter.targetSdkVersion
        // Uses the version code from pubspec.yaml. When using split APKs, 1000 * ABI_VERSION
        // is added automatically by Flutter. (https://developer.android.com/studio/build/configure-apk-splits#configure-APK-versions)
        // You can force using the value of versionCode by specifying the `-P force-version-code-ignoring-abi=true`
        // flag during build.
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    // `demo` points at the demo server and installs next to `prod`. The server address is a build
    // setting (--dart-define=API_BASE_URL=...), not part of the flavor.
    buildFeatures {
        resValues = true
    }

    flavorDimensions += "env"
    productFlavors {
        create("demo") {
            dimension = "env"
            applicationIdSuffix = ".demo"
            resValue("string", "app_name", "Skills Demo")
        }
        create("prod") {
            dimension = "env"
            resValue("string", "app_name", "Skills")
        }
    }

    // Release signing is injected by CI from environment secrets in the release workflow; nothing
    // secret is committed, so a local release build is unsigned.
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
