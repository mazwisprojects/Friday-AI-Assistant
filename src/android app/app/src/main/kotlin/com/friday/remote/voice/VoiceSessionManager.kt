package com.friday.remote.voice

import com.friday.remote.network.FridaySocketManager
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Aligned to Friday's real architecture: emitting `start_audio` makes the HOME
 * SERVER start its own listening session (PC mic) and stream `audio_data` back
 * to the phone. The phone no longer records its own mic and uploads it.
 */
@Singleton
class VoiceSessionManager @Inject constructor(
    private val socketManager: FridaySocketManager
) : FridaySocketManager.AudioSink {

    init {
        socketManager.setAudioSink(this)
    }

    fun toggleSession() = socketManager.toggleAudioSession()

    override fun onAudioData(bytes: List<Int>) {
        VoicePlayback.play(bytes)
    }
}
