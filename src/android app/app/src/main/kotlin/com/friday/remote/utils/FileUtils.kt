package com.friday.remote.utils

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import java.io.InputStream

fun getFileName(context: Context, uri: Uri): String {
    val cursor = context.contentResolver.query(uri, null, null, null, null)
    cursor?.use {
        if (it.moveToFirst()) {
            val nameIndex = it.getColumnIndex(OpenableColumns.DISPLAY_NAME)
            if (nameIndex != -1) {
                return it.getString(nameIndex)
            }
        }
    }
    return uri.lastPathSegment ?: "unknown_file"
}

fun readFileBytes(context: Context, uri: Uri): ByteArray {
    val inputStream: InputStream = context.contentResolver.openInputStream(uri)!!
    return inputStream.use { it.readBytes() }
}
