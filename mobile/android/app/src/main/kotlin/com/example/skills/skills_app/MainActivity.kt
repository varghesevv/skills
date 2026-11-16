package com.example.skills.skills_app

import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build
import android.os.Bundle
import io.flutter.embedding.android.FlutterActivity

class MainActivity : FlutterActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        createMessagesChannel()
    }

    /// The channel a push for a new message is shown in (the server names it "chat"). Making it
    /// again is harmless; the person can change its sound and importance in the phone's settings.
    private fun createMessagesChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = getSystemService(NotificationManager::class.java) ?: return
        manager.createNotificationChannel(
            NotificationChannel(
                "chat",
                getString(R.string.messages_channel_name),
                NotificationManager.IMPORTANCE_HIGH,
            ),
        )
    }
}
