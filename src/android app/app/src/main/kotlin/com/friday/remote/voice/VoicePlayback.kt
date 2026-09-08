package com.friday.remote.voice

import android.media.AudioFormat
import android.media.AudioPlayback
import android.media.MediaRecorder

/**
 * Minimal PCM (S16LE, mono, 44.1 kHz) playback sink for the `audio_data` frames
 * Friday streams from the home server. android.media.AudioPlayback (Android 27+)
 * is the counterpart of AudioRecord and mirrors its constructor/API; if your SDK
 * exposes a different signature, fix only this file.
 */
object VoicePlayback {
    private var playback: AudioPlayback? = null

    fun play(bytes: List<Int>) {
        if (bytes.size < 2) return
        try {
            if (playback == null) {
                val format = AudioFormat.CHANNEL_IN_MONO
                playback = AudioPlayback(
                    MediaRecorder.AudioSource.SPEAKER,
                    44100,
                    format,
                    AudioFormat.ENCODING_PCM_16BIT,
                    AudioPlayback.getMinBufferSize(44100, format, AudioFormat.ENCODING_PCM_16BIT)
                ).also { it.start() }
            }
            val sampleCount = bytes.size / 2
            val samples = ShortArray(sampleCount)
            for (i in 0 until sampleCount) {
                val lo = bytes[i * 2] and 0xff
                val hi = bytes[i * 2 + 1] and 0xff
                samples[i] = (hi.shl(8) or lo).toShort()
            }
            playback?.write(samples, 0, sampleCount)
        } catch (e: Exception) {
            // Degrade silently: chat/transcription still works without audio.
        }
    }

    fun stop() {
        try { playback?.stop() } catch (e: Exception) { }
        try { playback?.release() } catch (e: Exception) { }
        playback = null
    }
}
