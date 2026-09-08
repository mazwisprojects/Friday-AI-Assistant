# F.R.I.D.A.Y Remote Client Implementation Plan

This plan outlines the architecture and steps to build a native Android app that acts as a remote client for the F.R.I.D.A.Y home server.

## Goal
Build a robust, offline-first Android application using Jetpack Compose that interacts with a F.R.I.D.A.Y home server via Socket.IO, supporting voice sessions, text chat, live monitoring, camera uploads, and approval requests.

## User Review Required
> [!IMPORTANT]
> - **Server URL**: The app will default to `http://<HOME_PC_IP>:8000`. The user must provide the actual IP.
> - **AES Token**: The security implementation assumes an AES-encrypted token strategy. A way to input/generate this token needs to be defined (e.g., a setup screen).
> - **Permissions**: The app will require Mic, Camera, and Notification permissions.

## Open Questions
- Is there a specific REST API for `get_system_monitor` and `/user_input`, or should everything go through Socket.IO? The prompt mentions both `emit` and "REST", but Socket.IO is the primary focus.
- For "streaming audio responses back", will the server send chunks or a full URL/Base64? The plan assumes Base64 chunks for `MediaPlayer` or `AudioTrack`.

---

## Proposed Changes

### 1. Foundation & Configuration
- Setup `build.gradle` with dependencies: Socket.IO, CameraX, WorkManager, Security-Crypto, Compose, Hilt (DI).
- Define Dark Theme colors: Primary `#0A0E1A`, Accent `#06B8D8`.

### 2. Networking & Background Service
- **[NEW]** `FridaySocketService`: A Foreground Service to maintain the Socket.IO connection.
- **[NEW]** `FridaySocketManager`: A singleton to handle socket events, connection states, and event queuing for offline-first support.
- **[NEW]** `OfflineQueueWorker`: WorkManager task to replay queued events when connectivity returns.

### 3. Security & Storage
- **[NEW]** `SecurityManager`: Wrapper for `EncryptedSharedPreferences` to store Server URL and AES Token.

### 4. Features & Screens
- **Dashboard Screen**: Real-time system monitor (CPU/RAM/GPU/Network) using animated cards.
- **Chat Screen**: Text chat UI with `/user_input` support and status messages.
- **Voice/Mic**: Push-to-talk FAB with waveform animation. `AudioRecord` to Base64.
- **Camera Screen**: CameraX integration for photo capture and Base64 upload.
- **Approvals**: In-app dialog and Notification handler for `approval_request`.

---

## Verification Plan

### Automated Tests
- Unit tests for `FridaySocketManager` event queuing.
- Unit tests for `SecurityManager` encryption/decryption.

### Manual Verification
- Test Socket.IO connection stability on server disconnect/reconnect.
- Verify Mic recording and Base64 transmission.
- Verify Camera capture and upload.
- Test Foreground Service persistence.
- Verify Theme adherence.
