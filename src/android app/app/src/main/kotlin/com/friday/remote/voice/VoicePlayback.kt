package com.friday.remote.voice

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack

/**
 * Minimal PCM (S16LE, mono, 44.1 kHz) playback sink for the `audio_data` frames
 * Friday streams from the home server. Uses android.media.AudioTrack (available
 * on every API level) so it never blocks the build on an experimental API.
 */
object VoicePlayback {
    private var track: AudioTrack? = null

    fun play(bytes: List<Int>) {
        if (bytes.size < 2) return
        try {
            if (track == null) {
                val minBuf = AudioTrack.getMinBufferSize(
                    44100,
                    AudioFormat.CHANNEL_OUT_MONO,
                    AudioFormat.ENCODING_PCM_16BIT
                )
                track = AudioTrack.Builder()
                    .setAudioAttributes(
                        AudioAttributes.Builder()
                            .setUsage(AudioAttributes.USAGE_MEDIA)
                            .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                            .build()
                    )
                    .setAudioFormat(
                        AudioFormat.Builder()
                            .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                            .setSampleRate(44100)
                            .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                            .build()
                    )
                    .setBufferSizeInBytes(minBuf)
                    .setTransferMode(AudioTrack.MODE_STREAM)
                    .build()
                track?.play()
            }
            val sampleCount = bytes.size / 2
            val samples = ShortArray(sampleCount)
            for (i in 0 until sampleCount) {
                val lo = bytes[i * 2] and 0xff
                val hi = bytes[i * 2 + 1] and 0xff
                samples[i] = (hi.shl(8) or lo).toShort()
            }
            track?.write(samples, 0, sampleCount)
        } catch (e: Exception) {
            // Degrade silently: chat/transcription still works without audio.
        }
    }

    fun stop() {
        try { track?.stop() } catch (e: Exception) { }
        try { track?.release() } catch (e: Exception) { }
        track = null
    }
}
