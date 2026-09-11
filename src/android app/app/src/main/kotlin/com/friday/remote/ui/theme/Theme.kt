package com.friday.remote.ui.theme

import android.app.Activity
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

// Friday Theme Colors
val FridayDark = Color(0xFF0A0E1A)
val FridayAccent = Color(0xFF06B8D8)
val FridayGrey = Color(0xFF1A1A2E)
val White = Color(0xFFFFFFFF)
val LightGray = Color(0xFFCCCCCC)

private val DarkColorScheme = darkColorScheme(
    primary = FridayAccent,
    secondary = FridayGrey,
    tertiary = FridayAccent,
    background = FridayDark,
    surface = FridayDark,
    onPrimary = FridayDark,
    onSecondary = White,
    onTertiary = White,
    onBackground = White,
    onSurface = White
)

@Composable
fun FridayTheme(
    content: @Composable () -> Unit
) {
    val colorScheme = DarkColorScheme
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = FridayDark.toArgb()
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = false
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content
    )
}
