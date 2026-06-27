/* ============================================================
   ScreenFlow – Application Logic
   Browser Screen Recorder with Automation & Scheduling
   ============================================================ */

(() => {
    'use strict';

    // ---- DOM References ----
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    const dom = {
        // Tabs
        tabRecorder: $('#tab-recorder'),
        tabLibrary: $('#tab-library'),
        recorderView: $('#recorder-view'),
        libraryView: $('#library-view'),

        // Status
        statusBanner: $('#status-banner'),
        statusText: $('#status-text'),

        // Preview
        previewIdle: $('#preview-idle'),
        previewVideo: $('#preview-video'),
        recordingOverlay: $('#recording-overlay'),
        timerDisplay: $('#timer-display'),

        // Controls
        btnRecord: $('#btn-record'),
        iconRecord: $('#icon-record'),
        iconStop: $('#icon-stop'),
        btnPause: $('#btn-pause'),
        iconPause: $('#icon-pause'),
        iconResume: $('#icon-resume'),
        btnScreenshot: $('#btn-screenshot'),

        // Settings
        selectQuality: $('#select-quality'),
        selectFps: $('#select-fps'),
        selectFormat: $('#select-format'),
        toggleAudio: $('#toggle-audio'),
        toggleMic: $('#toggle-mic'),

        // Automation
        autoDelay: $('#auto-delay'),
        autoTimerMin: $('#auto-timer-min'),
        autoTimerSec: $('#auto-timer-sec'),
        autoSchedule: $('#auto-schedule'),
        autoStopAt: $('#auto-stop-at'),
        btnSelectTab: $('#btn-select-tab'),
        btnSchedule: $('#btn-schedule'),
        scheduledList: $('#scheduled-list'),
        preselectedTabInfo: $('#preselected-tab-info'),
        preselectedTabLabel: $('#preselected-tab-label'),
        btnClearTab: $('#btn-clear-tab'),
        btnEnableNotifications: $('#btn-enable-notifications'),

        // Library
        libraryGrid: $('#library-grid'),
        libraryEmpty: $('#library-empty'),
        libraryCount: $('#library-count'),

        // Modal
        settingsBtn: $('#settings-btn'),
        settingsModal: $('#settings-modal'),
        closeSettings: $('#close-settings'),
        settingFilename: $('#setting-filename'),
        settingCountdown: $('#setting-countdown'),
        settingCursor: $('#setting-cursor'),
        settingSound: $('#setting-sound'),

        // Countdown
        countdownOverlay: $('#countdown-overlay'),
        countdownNumber: $('#countdown-number'),

        // Toast
        toastContainer: $('#toast-container'),

        // Finished Overlay
        finishedOverlay: $('#finished-overlay'),
        finishedFilename: $('#finished-filename'),
        btnDismissFinished: $('#btn-dismiss-finished'),
        btnViewLibrary: $('#btn-view-library'),

        // Additional notification settings
        btnTestNotification: $('#btn-test-notification'),
        settingPersistentNote: $('#setting-persistent-note')
    };

    // ---- State ----
    const state = {
        isRecording: false,
        isPaused: false,
        mediaRecorder: null,
        recordedChunks: [],
        stream: null,
        micStream: null,
        timerInterval: null,
        timerSeconds: 0,
        timerTarget: 0, // custom timer target in seconds (0 = unlimited)
        recordings: [], // { id, name, blob, url, duration, date, size, format, isDeleted }
        scheduledTimers: [],
        autoStopTimer: null,
        preselectedStream: null, // pre-selected stream for scheduled recording
        notificationsEnabled: false,
        libraryFilter: 'active' // 'active' or 'trash'
    };

    // ---- IndexedDB Helper ----
    const DB_NAME = 'ScreenFlowDB';
    const STORE_NAME = 'recordings';
    let dbInstance = null;

    function initDB() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(DB_NAME, 1);
            request.onerror = (e) => reject(e);
            request.onsuccess = (e) => {
                dbInstance = e.target.result;
                resolve(dbInstance);
            };
            request.onupgradeneeded = (e) => {
                const db = e.target.result;
                if (!db.objectStoreNames.contains(STORE_NAME)) {
                    db.createObjectStore(STORE_NAME, { keyPath: 'id' });
                }
            };
        });
    }

    function saveRecordingDB(recording) {
        if (!dbInstance) return Promise.resolve();
        return new Promise((resolve, reject) => {
            const tx = dbInstance.transaction(STORE_NAME, 'readwrite');
            const store = tx.objectStore(STORE_NAME);
            // Don't save the ephemeral URL to DB
            const recCopy = { ...recording };
            delete recCopy.url;
            const req = store.put(recCopy);
            req.onsuccess = () => resolve();
            req.onerror = (e) => reject(e);
        });
    }

    function getRecordingsDB() {
        if (!dbInstance) return Promise.resolve([]);
        return new Promise((resolve, reject) => {
            const tx = dbInstance.transaction(STORE_NAME, 'readonly');
            const store = tx.objectStore(STORE_NAME);
            const req = store.getAll();
            req.onsuccess = () => resolve(req.result);
            req.onerror = (e) => reject(e);
        });
    }

    function deleteRecordingDB(id) {
        if (!dbInstance) return Promise.resolve();
        return new Promise((resolve, reject) => {
            const tx = dbInstance.transaction(STORE_NAME, 'readwrite');
            const store = tx.objectStore(STORE_NAME);
            const req = store.delete(id);
            req.onsuccess = () => resolve();
            req.onerror = (e) => reject(e);
        });
    }

    // ---- Utilities ----
    function formatTime(sec) {
        const h = String(Math.floor(sec / 3600)).padStart(2, '0');
        const m = String(Math.floor((sec % 3600) / 60)).padStart(2, '0');
        const s = String(sec % 60).padStart(2, '0');
        return `${h}:${m}:${s}`;
    }

    function formatBytes(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / 1048576).toFixed(1) + ' MB';
    }

    function generateId() {
        return Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
    }

    function formatDate(d) {
        return new Date(d).toLocaleString(undefined, {
            month: 'short', day: 'numeric', year: 'numeric',
            hour: '2-digit', minute: '2-digit'
        });
    }

    // ---- Page Title Blinking (Discord style) ----
    let originalTitle = document.title;
    let blinkInterval = null;

    function startTabBlink(message) {
        if (!document.hidden) return; // Only blink if in background
        if (blinkInterval) clearInterval(blinkInterval);
        
        // Start alternating title
        let showMessage = true;
        blinkInterval = setInterval(() => {
            document.title = showMessage ? `(1) ${message}` : originalTitle;
            showMessage = !showMessage;
        }, 1000);
    }

    function stopTabBlink() {
        if (blinkInterval) {
            clearInterval(blinkInterval);
            blinkInterval = null;
        }
        document.title = originalTitle;
    }

    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
            stopTabBlink();
        }
    });

    // ---- Browser Push Notifications ----
    async function requestNotificationPermission() {
        if (!('Notification' in window)) {
            showToast('Your browser does not support notifications', 'error');
            return false;
        }
        if (Notification.permission === 'granted') {
            state.notificationsEnabled = true;
            updateNotificationButton();
            return true;
        }
        if (Notification.permission === 'denied') {
            showToast('Notifications are blocked. Please enable them in browser settings.', 'error');
            return false;
        }
        const result = await Notification.requestPermission();
        state.notificationsEnabled = result === 'granted';
        updateNotificationButton();
        if (state.notificationsEnabled) {
            showToast('Notifications enabled!', 'success');
            sendNotification('ScreenFlow', 'Notifications are now active. You\'ll be notified of recording events.');
        } else {
            showToast('Notification permission denied', 'error');
        }
        return state.notificationsEnabled;
    }

    function updateNotificationButton() {
        if (!dom.btnEnableNotifications) return;
        if (state.notificationsEnabled) {
            dom.btnEnableNotifications.textContent = '✓ Enabled';
            dom.btnEnableNotifications.style.background = 'rgba(34, 197, 94, 0.2)';
            dom.btnEnableNotifications.style.borderColor = 'rgba(34, 197, 94, 0.4)';
            dom.btnEnableNotifications.style.color = '#22c55e';
        }
    }

    let swRegistration = null;

    function sendNotification(title, body, tag = 'screenflow') {
        // Broadcast the notification to the Chrome Extension Content Script
        // This makes sure our custom Discord-style pop-ups inject into every open tab!
        window.postMessage({
            type: 'SCREENFLOW_GLOBAL_NOTIFY',
            payload: { title, body }
        }, '*');

        // Always attempt to blink the tab title when firing a notification
        startTabBlink(title);

        if (!state.notificationsEnabled || Notification.permission !== 'granted') return;
        
        const isPersistent = dom.settingPersistentNote && dom.settingPersistentNote.checked;
        
        try {
            const options = {
                body,
                tag,
            };
            
            // Note: SVG data URIs in the 'icon' parameter often cause native 
            // OS push notifications (Windows/macOS) to silently fail.
            // We omit the icon so it securely falls back to the browser's default icon.
            
            if (isPersistent) {
                options.requireInteraction = true;
            }

            // Bulletproof Native OS Notifications via Service Worker
            if (swRegistration && 'showNotification' in swRegistration) {
                swRegistration.showNotification(title, options);
            } else {
                // Fallback for browsers without proper SW support
                const n = new Notification(title, options);
                if (!isPersistent) setTimeout(() => n.close(), 5000);
                n.onclick = () => { 
                    window.focus(); 
                    stopTabBlink();
                    n.close(); 
                };
            }
        } catch (e) {
            console.warn('Notification failed:', e);
        }
    }

    // ---- Toast Notifications ----
    function showToast(message, type = 'info', duration = 4000) {
        const icons = {
            success: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
            error: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
            info: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
        };

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <span class="toast-icon">${icons[type] || icons.info}</span>
            <span>${message}</span>
            <button class="toast-dismiss" aria-label="Dismiss">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
        `;

        toast.querySelector('.toast-dismiss').addEventListener('click', () => removeToast(toast));
        dom.toastContainer.appendChild(toast);

        setTimeout(() => removeToast(toast), duration);
    }

    function removeToast(toast) {
        if (!toast.parentNode) return;
        toast.classList.add('removing');
        setTimeout(() => toast.remove(), 250);
    }

    // ---- Sound Effects ----
    function playSound(type) {
        if (!dom.settingSound.checked) return;
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        
        if (type === 'start') {
            // Ascending "Pop Pop" (Discord connection tone style)
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            
            // Step 1: Low pop
            osc.frequency.setValueAtTime(400, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(600, ctx.currentTime + 0.1);
            
            // Step 2: High pop
            osc.frequency.setValueAtTime(600, ctx.currentTime + 0.1);
            osc.frequency.exponentialRampToValueAtTime(900, ctx.currentTime + 0.2);
            
            osc.type = 'sine';
            
            gain.gain.setValueAtTime(0, ctx.currentTime);
            gain.gain.linearRampToValueAtTime(0.2, ctx.currentTime + 0.02);
            gain.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.1);
            gain.gain.linearRampToValueAtTime(0.2, ctx.currentTime + 0.12);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
            
            osc.start(ctx.currentTime);
            osc.stop(ctx.currentTime + 0.3);
            
        } else if (type === 'stop') {
            // Crisp, pleasant notification pop (Discord message style)
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            
            osc.connect(gain);
            gain.connect(ctx.destination);
            
            osc.type = 'sine';
            osc.frequency.setValueAtTime(600, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(300, ctx.currentTime + 0.15);
            
            gain.gain.setValueAtTime(0, ctx.currentTime);
            gain.gain.linearRampToValueAtTime(0.25, ctx.currentTime + 0.02);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.2);
            
            osc.start(ctx.currentTime);
            osc.stop(ctx.currentTime + 0.2);
        }
    }

    // ---- Tab Navigation ----
    function switchTab(tab) {
        $$('.nav-tab').forEach(t => t.classList.remove('active'));
        $$('.view').forEach(v => v.classList.remove('active'));

        if (tab === 'recorder') {
            dom.tabRecorder.classList.add('active');
            dom.recorderView.classList.add('active');
        } else {
            dom.tabLibrary.classList.add('active');
            dom.libraryView.classList.add('active');
        }
    }

    dom.tabRecorder.addEventListener('click', () => switchTab('recorder'));
    dom.tabLibrary.addEventListener('click', () => switchTab('library'));

    // ---- Settings Modal ----
    dom.settingsBtn.addEventListener('click', () => {
        dom.settingsModal.classList.remove('hidden');
    });

    dom.closeSettings.addEventListener('click', () => {
        dom.settingsModal.classList.add('hidden');
    });

    dom.settingsModal.querySelector('.modal-backdrop').addEventListener('click', () => {
        dom.settingsModal.classList.add('hidden');
    });

    // ---- Status Update ----
    function setStatus(statusClass, text) {
        dom.statusBanner.className = 'status-banner ' + statusClass;
        dom.statusText.textContent = text;
    }

    // ---- Timer ----
    function getCustomTimerSeconds() {
        const min = parseInt(dom.autoTimerMin.value) || 0;
        const sec = parseInt(dom.autoTimerSec.value) || 0;
        return (min * 60) + sec;
    }

    function startTimer() {
        state.timerSeconds = 0;
        state.timerTarget = getCustomTimerSeconds();

        // If custom timer is set, show countdown format
        if (state.timerTarget > 0) {
            dom.timerDisplay.textContent = `00:00:00 / ${formatTime(state.timerTarget)}`;
        } else {
            dom.timerDisplay.textContent = '00:00:00';
        }

        state.timerInterval = setInterval(() => {
            state.timerSeconds++;

            if (state.timerTarget > 0) {
                dom.timerDisplay.textContent = `${formatTime(state.timerSeconds)} / ${formatTime(state.timerTarget)}`;

                // Auto-stop when timer target is reached
                if (state.timerSeconds >= state.timerTarget) {
                    showToast(`Timer reached ${formatTime(state.timerTarget)} — recording stopped`, 'info');
                    sendNotification('Recording Complete', `Timer reached ${formatTime(state.timerTarget)}. Your recording has been saved.`);
                    stopRecording();
                    return;
                }
            } else {
                dom.timerDisplay.textContent = formatTime(state.timerSeconds);
            }
        }, 1000);
    }

    function stopTimer() {
        clearInterval(state.timerInterval);
        state.timerInterval = null;
    }

    function pauseTimer() {
        clearInterval(state.timerInterval);
    }

    function resumeTimer() {
        state.timerInterval = setInterval(() => {
            state.timerSeconds++;

            if (state.timerTarget > 0) {
                dom.timerDisplay.textContent = `${formatTime(state.timerSeconds)} / ${formatTime(state.timerTarget)}`;

                if (state.timerSeconds >= state.timerTarget) {
                    showToast(`Timer reached ${formatTime(state.timerTarget)} — recording stopped`, 'info');
                    sendNotification('Recording Complete', `Timer reached ${formatTime(state.timerTarget)}. Your recording has been saved.`);
                    stopRecording();
                    return;
                }
            } else {
                dom.timerDisplay.textContent = formatTime(state.timerSeconds);
            }
        }, 1000);
    }

    // ---- Countdown ----
    function showCountdown(count) {
        return new Promise((resolve) => {
            if (count === 0) {
                resolve();
                return;
            }
            setStatus('countdown', `Starting in ${count}...`);
            dom.countdownOverlay.classList.remove('hidden');
            dom.countdownNumber.textContent = count;
            dom.countdownNumber.style.animation = 'none';
            void dom.countdownNumber.offsetHeight; // force reflow
            dom.countdownNumber.style.animation = 'countdownPop 1s ease-in-out';

            let current = count;
            const interval = setInterval(() => {
                current--;
                if (current <= 0) {
                    clearInterval(interval);
                    dom.countdownOverlay.classList.add('hidden');
                    resolve();
                } else {
                    dom.countdownNumber.textContent = current;
                    dom.countdownNumber.style.animation = 'none';
                    void dom.countdownNumber.offsetHeight;
                    dom.countdownNumber.style.animation = 'countdownPop 1s ease-in-out';
                    setStatus('countdown', `Starting in ${current}...`);
                }
            }, 1000);
        });
    }

    // ---- Get Media Constraints ----
    function getQualityConstraints() {
        const q = dom.selectQuality.value;
        const fps = parseInt(dom.selectFps.value);
        const map = {
            high: { width: { ideal: 1920 }, height: { ideal: 1080 }, frameRate: { ideal: fps } },
            medium: { width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: fps } },
            low: { width: { ideal: 854 }, height: { ideal: 480 }, frameRate: { ideal: fps } },
        };
        return map[q] || map.medium;
    }

    function getMimeType() {
        const format = dom.selectFormat.value;
        const candidates = format === 'mp4'
            ? ['video/mp4;codecs=avc1', 'video/mp4', 'video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm']
            : ['video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm'];

        for (const mime of candidates) {
            if (MediaRecorder.isTypeSupported(mime)) return mime;
        }
        return '';
    }

    // ---- Core: Start Recording ----
    // usePreselected: if true, use the pre-selected stream instead of prompting
    async function startRecording(usePreselected = false) {
        try {
            // Use pre-selected stream or prompt for new one
            if (usePreselected && state.preselectedStream) {
                // Check if the pre-selected stream is still active
                const tracks = state.preselectedStream.getVideoTracks();
                if (tracks.length === 0 || tracks[0].readyState === 'ended') {
                    showToast('Pre-selected tab is no longer available. Please select again.', 'error');
                    sendNotification('Schedule Failed', 'The pre-selected tab is no longer available.');
                    clearPreselectedTab();
                    return;
                }
                state.stream = state.preselectedStream;
                state.preselectedStream = null; // consume it
                clearPreselectedTab();
            } else {
                const constraints = getQualityConstraints();
                const displayMediaOpts = {
                    video: {
                        ...constraints,
                        cursor: dom.settingCursor.checked ? 'always' : 'never',
                    },
                    audio: dom.toggleAudio.checked,
                };
                state.stream = await navigator.mediaDevices.getDisplayMedia(displayMediaOpts);
            }

            // Optionally add microphone
            let combinedStream = state.stream;
            if (dom.toggleMic.checked) {
                try {
                    state.micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    const ctx = new AudioContext();
                    const dest = ctx.createMediaStreamDestination();

                    // Add all audio tracks from display
                    state.stream.getAudioTracks().forEach(t => {
                        const source = ctx.createMediaStreamSource(new MediaStream([t]));
                        source.connect(dest);
                    });

                    // Add mic audio
                    state.micStream.getAudioTracks().forEach(t => {
                        const source = ctx.createMediaStreamSource(new MediaStream([t]));
                        source.connect(dest);
                    });

                    combinedStream = new MediaStream([
                        ...state.stream.getVideoTracks(),
                        ...dest.stream.getAudioTracks(),
                    ]);
                } catch (micErr) {
                    console.warn('Microphone access denied:', micErr);
                    showToast('Microphone access denied, recording without mic', 'error');
                }
            }

            // Show preview
            dom.previewIdle.style.display = 'none';
            dom.previewVideo.classList.add('active');
            dom.previewVideo.srcObject = state.stream;

            // Countdown (skip for pre-selected/scheduled starts)
            if (!usePreselected) {
                const countdownSec = parseInt(dom.settingCountdown.value);
                await showCountdown(countdownSec);
            }

            // Configure MediaRecorder
            const mimeType = getMimeType();
            const options = { mimeType };
            if (mimeType) {
                state.mediaRecorder = new MediaRecorder(combinedStream, options);
            } else {
                state.mediaRecorder = new MediaRecorder(combinedStream);
            }

            state.recordedChunks = [];

            state.mediaRecorder.ondataavailable = (e) => {
                if (e.data && e.data.size > 0) {
                    state.recordedChunks.push(e.data);
                }
            };

            state.mediaRecorder.onstop = () => {
                finishRecording();
            };

            // Handle user stopping via browser UI or target tab closing/refreshing
            state.stream.getVideoTracks()[0].onended = () => {
                if (state.isRecording) {
                    stopRecording();
                }
            };

            // Start with no timeslice — produces one continuous WebM stream.
            // All data arrives in a single dataavailable event when stop() is called.
            state.mediaRecorder.start();
            state.isRecording = true;
            state.isPaused = false;

            // UI updates
            playSound('start');
            setStatus('recording', 'Recording in progress...');
            dom.btnRecord.classList.add('recording');
            dom.iconRecord.classList.add('hidden');
            dom.iconStop.classList.remove('hidden');
            dom.btnPause.disabled = false;
            dom.btnScreenshot.disabled = false;
            dom.recordingOverlay.classList.remove('hidden');
            startTimer();

            showToast('Recording started', 'success');
            sendNotification('Recording Started', 'ScreenFlow is now recording your screen.');

        } catch (err) {
            console.error('Failed to start recording:', err);
            if (err.name === 'NotAllowedError') {
                showToast('Screen sharing was cancelled', 'error');
            } else {
                showToast('Failed to start recording: ' + err.message, 'error');
            }
            cleanupStreams();
        }
    }

    // ---- Core: Stop Recording ----
    function stopRecording() {
        if (!state.isRecording) return;

        state.isRecording = false;
        state.isPaused = false;

        if (state.mediaRecorder && state.mediaRecorder.state !== 'inactive') {
            state.mediaRecorder.stop();
        }

        cleanupStreams();
        stopTimer();
        playSound('stop');

        if (state.autoStopTimer) {
            clearTimeout(state.autoStopTimer);
            state.autoStopTimer = null;
        }

        // UI
        setStatus('idle', 'Ready to Record');
        dom.btnRecord.classList.remove('recording');
        dom.iconRecord.classList.remove('hidden');
        dom.iconStop.classList.add('hidden');
        dom.btnPause.disabled = true;
        dom.btnScreenshot.disabled = true;
        dom.iconPause.classList.remove('hidden');
        dom.iconResume.classList.add('hidden');
        dom.recordingOverlay.classList.add('hidden');

        sendNotification('Recording Stopped', 'Your recording has been saved to the library.');
    }

    function cleanupStreams() {
        if (state.stream) {
            state.stream.getTracks().forEach(t => t.stop());
            state.stream = null;
        }
        if (state.micStream) {
            state.micStream.getTracks().forEach(t => t.stop());
            state.micStream = null;
        }
        dom.previewVideo.srcObject = null;
        dom.previewVideo.classList.remove('active');
        dom.previewIdle.style.display = '';
    }

    // ---- Core: Finish Recording (save blob) ----
    function finishRecording() {
        const mimeType = getMimeType() || 'video/webm';
        const blob = new Blob(state.recordedChunks, { type: mimeType });
        const durationMs = Math.max(state.timerSeconds * 1000, 100);

        // Fix the missing duration in WebM so the seek bar works
        if (window.ysFixWebmDuration) {
            window.ysFixWebmDuration(blob, durationMs, (fixedBlob) => {
                 finalizeRecordingSetup(fixedBlob);
            });
        } else {
             finalizeRecordingSetup(blob); // fallback
        }
    }

    function finalizeRecordingSetup(blob) {
        const url = URL.createObjectURL(blob);
        const prefix = dom.settingFilename.value || 'ScreenFlow';
        const dateStr = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
        const ext = 'webm'; // Enforce WebM due to MP4 audio incompatibility

        const recording = {
            id: generateId(),
            name: `${prefix}_${dateStr}.${ext}`,
            blob,
            url,
            duration: state.timerSeconds,
            date: Date.now(),
            size: blob.size,
            format: ext,
            isDeleted: false
        };

        state.recordings.unshift(recording);
        saveRecordingDB(recording);
        renderLibrary();

        showToast(`Recording saved (${formatBytes(blob.size)})`, 'success');
        showFinishedOverlay(recording);
    }

    // ---- Finished Overlay ----
    function showFinishedOverlay(recording) {
        dom.finishedFilename.textContent = `"${recording.name}" has been saved.`;
        dom.finishedOverlay.classList.remove('hidden');
    }

    dom.btnDismissFinished.addEventListener('click', () => {
        dom.finishedOverlay.classList.add('hidden');
    });

    dom.btnViewLibrary.addEventListener('click', () => {
        dom.finishedOverlay.classList.add('hidden');
        switchTab('library');
    });

    // ---- Pause / Resume ----
    dom.btnPause.addEventListener('click', () => {
        if (!state.isRecording) return;

        if (state.isPaused) {
            // Resume
            state.mediaRecorder.resume();
            state.isPaused = false;
            setStatus('recording', 'Recording in progress...');
            dom.iconPause.classList.remove('hidden');
            dom.iconResume.classList.add('hidden');
            dom.recordingOverlay.querySelector('.rec-indicator').style.opacity = '1';
            resumeTimer();
        } else {
            // Pause
            state.mediaRecorder.pause();
            state.isPaused = true;
            setStatus('paused', 'Recording paused');
            dom.iconPause.classList.add('hidden');
            dom.iconResume.classList.remove('hidden');
            dom.recordingOverlay.querySelector('.rec-indicator').style.opacity = '0.4';
            pauseTimer();
        }
    });

    // ---- Record Button ----
    dom.btnRecord.addEventListener('click', async () => {
        if (state.isRecording) {
            stopRecording();
        } else {
            // Check for delay
            const delay = parseInt(dom.autoDelay.value) || 0;
            if (delay > 0) {
                setStatus('countdown', `Starting in ${delay} seconds...`);
                showToast(`Recording will start in ${delay} seconds`, 'info');
                await new Promise(resolve => setTimeout(resolve, delay * 1000));
            }
            startRecording();
        }
    });

    // ---- Screenshot ----
    dom.btnScreenshot.addEventListener('click', () => {
        if (!state.stream) return;
        const video = dom.previewVideo;
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0);

        canvas.toBlob((blob) => {
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            const prefix = dom.settingFilename.value || 'ScreenFlow';
            a.href = url;
            a.download = `${prefix}_screenshot_${Date.now()}.png`;
            a.click();
            URL.revokeObjectURL(url);
            showToast('Screenshot saved!', 'success');
        }, 'image/png');
    });

    // ---- Tab Pre-selection ----
    dom.btnSelectTab.addEventListener('click', async () => {
        try {
            // If already have a pre-selected stream, clear it first
            if (state.preselectedStream) {
                state.preselectedStream.getTracks().forEach(t => t.stop());
                state.preselectedStream = null;
            }

            const constraints = getQualityConstraints();
            const displayMediaOpts = {
                video: {
                    ...constraints,
                    cursor: dom.settingCursor.checked ? 'always' : 'never',
                },
                audio: dom.toggleAudio.checked,
            };

            state.preselectedStream = await navigator.mediaDevices.getDisplayMedia(displayMediaOpts);

            // Get stream label for display
            const label = state.preselectedStream.getVideoTracks()[0]?.label || 'Selected source';

            // Handle stream ending before scheduled time
            state.preselectedStream.getVideoTracks()[0].onended = () => {
                if (state.preselectedStream) {
                    clearPreselectedTab();
                    showToast('Pre-selected tab was closed', 'error');
                    sendNotification('Tab Closed', 'The pre-selected recording source was closed.');
                }
            };

            // Show indicator
            dom.preselectedTabLabel.textContent = label;
            dom.preselectedTabInfo.classList.remove('hidden');
            dom.btnSelectTab.classList.add('selected');

            showToast(`Source selected: ${label}`, 'success');
        } catch (err) {
            if (err.name !== 'NotAllowedError') {
                showToast('Failed to select source: ' + err.message, 'error');
            }
        }
    });

    function clearPreselectedTab() {
        if (state.preselectedStream) {
            state.preselectedStream.getTracks().forEach(t => t.stop());
            state.preselectedStream = null;
        }
        dom.preselectedTabInfo.classList.add('hidden');
        dom.btnSelectTab.classList.remove('selected');
    }

    dom.btnClearTab.addEventListener('click', () => {
        clearPreselectedTab();
        showToast('Tab selection cleared', 'info');
    });

    // ---- Notification Permission Button ----
    dom.btnEnableNotifications.addEventListener('click', () => {
        requestNotificationPermission();
    });

    dom.btnTestNotification.addEventListener('click', () => {
        if (!state.notificationsEnabled) {
            requestNotificationPermission().then(granted => {
                if (granted) sendNotification('Test Notification', 'This is how your recording alerts will look.');
            });
        } else {
            sendNotification('Test Notification', 'This is how your recording alerts will look.');
            showToast('Test notification sent!', 'info');
        }
    });

    // ---- Scheduling ----
    dom.btnSchedule.addEventListener('click', () => {
        const scheduleTime = dom.autoSchedule.value;
        const stopAtTime = dom.autoStopAt.value;

        if (!scheduleTime) {
            showToast('Please select a Start At date and time', 'error');
            return;
        }

        const targetDate = new Date(scheduleTime);
        const now = new Date();

        if (targetDate <= now) {
            showToast('Start time must be in the future', 'error');
            return;
        }

        // Parse stop-at time
        let stopAtDate = null;
        if (stopAtTime) {
            stopAtDate = new Date(stopAtTime);
            if (stopAtDate <= targetDate) {
                showToast('Stop At time must be after Start At time', 'error');
                return;
            }
        }

        // Check custom timer
        const customTimerSec = getCustomTimerSeconds();

        const delayMs = targetDate - now;
        const hasPreselected = !!state.preselectedStream;
        const scheduleId = generateId();

        // Notify 1 minute before (if enough lead time)
        let preNotifyTimer = null;
        if (delayMs > 60000) {
            preNotifyTimer = setTimeout(() => {
                sendNotification('Recording Starting Soon', `Your scheduled recording starts in 1 minute at ${formatDate(targetDate)}`);
            }, delayMs - 60000);
        }

        const timer = setTimeout(async () => {
            if (!state.isRecording) {
                sendNotification('Scheduled Recording Starting', 'Your scheduled recording is starting now!');
                showToast('Scheduled recording starting now!', 'info');
                await startRecording(hasPreselected);

                // Set auto-stop based on Stop At time
                if (stopAtDate) {
                    const stopDelayMs = stopAtDate - Date.now();
                    if (stopDelayMs > 0) {
                        state.autoStopTimer = setTimeout(() => {
                            if (state.isRecording) {
                                stopRecording();
                                showToast(`Recording auto-stopped at ${formatDate(stopAtDate)}`, 'info');
                                sendNotification('Recording Complete', `Scheduled recording stopped at ${formatDate(stopAtDate)}.`);
                            }
                        }, stopDelayMs);
                    }
                }
            }
            // Remove from scheduled list
            removeSchedule(scheduleId);
        }, delayMs);

        state.scheduledTimers.push({
            id: scheduleId,
            timer,
            preNotifyTimer,
            time: targetDate,
            stopAt: stopAtDate,
            customTimer: customTimerSec,
            hasPreselected,
        });

        renderScheduledList();
        const parts = [`Starts: ${formatDate(targetDate)}`];
        if (stopAtDate) parts.push(`Stops: ${formatDate(stopAtDate)}`);
        if (hasPreselected) parts.push('Tab pre-selected ✓');
        const statusMsg = parts.join(' · ');
        setStatus('scheduled', statusMsg);
        showToast(statusMsg, 'success');
        sendNotification('Recording Scheduled', statusMsg);

        // Reset the inputs
        dom.autoSchedule.value = '';
        dom.autoStopAt.value = '';
    });

    function removeSchedule(id) {
        const idx = state.scheduledTimers.findIndex(s => s.id === id);
        if (idx !== -1) {
            clearTimeout(state.scheduledTimers[idx].timer);
            if (state.scheduledTimers[idx].preNotifyTimer) {
                clearTimeout(state.scheduledTimers[idx].preNotifyTimer);
            }
            state.scheduledTimers.splice(idx, 1);
            renderScheduledList();

            if (state.scheduledTimers.length === 0 && !state.isRecording) {
                setStatus('idle', 'Ready to Record');
            }
        }
    }

    function renderScheduledList() {
        dom.scheduledList.innerHTML = '';
        state.scheduledTimers.forEach(s => {
            const el = document.createElement('div');
            el.className = 'scheduled-item';

            // Build details text
            const detailParts = [];
            if (s.stopAt) {
                detailParts.push(`Stops at: ${formatDate(s.stopAt)}`);
            }
            if (s.customTimer > 0) {
                detailParts.push(`Timer: ${formatTime(s.customTimer)}`);
            }
            if (s.hasPreselected) {
                detailParts.push('Tab pre-selected ✓');
            }
            if (detailParts.length === 0) {
                detailParts.push('Manual stop');
            }

            el.innerHTML = `
                <div class="scheduled-item-info">
                    <div class="scheduled-item-time">Starts: ${formatDate(s.time)}</div>
                    <div class="scheduled-item-details">${detailParts.join(' · ')}</div>
                </div>
                <button class="btn-cancel-schedule" data-id="${s.id}">Cancel</button>
            `;
            el.querySelector('.btn-cancel-schedule').addEventListener('click', () => {
                removeSchedule(s.id);
                showToast('Scheduled recording cancelled', 'info');
            });
            dom.scheduledList.appendChild(el);
        });
    }

    // ---- Library ----
    // Library Tabs
    $$('.lib-tab').forEach(tab => {
        tab.addEventListener('click', (e) => {
            $$('.lib-tab').forEach(t => t.classList.remove('active'));
            e.target.classList.add('active');
            state.libraryFilter = e.target.dataset.filter;
            renderLibrary();
        });
    });

    function renderLibrary() {
        const trashEmpty = $('#trash-empty');
        const filter = state.libraryFilter; // 'active' or 'trash'
        
        const filteredRecordings = state.recordings.filter(r => 
            filter === 'trash' ? r.isDeleted : !r.isDeleted
        );
        
        const count = filteredRecordings.length;
        dom.libraryCount.textContent = `${count} recording${count !== 1 ? 's' : ''}`;

        // Empty states logic
        if (count === 0) {
            if (filter === 'trash') {
                dom.libraryEmpty.style.display = 'none';
                if(trashEmpty) trashEmpty.classList.remove('hidden');
                if(trashEmpty) trashEmpty.style.display = 'flex';
            } else {
                dom.libraryEmpty.style.display = '';
                if(trashEmpty) trashEmpty.style.display = 'none';
            }
        } else {
            dom.libraryEmpty.style.display = 'none';
            if(trashEmpty) trashEmpty.style.display = 'none';
        }

        // Remove only cards (keep empty state element)
        dom.libraryGrid.querySelectorAll('.library-card').forEach(c => c.remove());

        filteredRecordings.forEach(rec => {
            const card = document.createElement('div');
            card.className = `library-card ${rec.isDeleted ? 'trashed' : ''}`;
            
            // Generate Actions HTML based on whether it is trashed
            let actionsHtml = '';
            if (rec.isDeleted) {
                actionsHtml = `
                    <button class="btn-card btn-restore" data-id="${rec.id}" title="Restore">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>
                        Restore
                    </button>
                    <button class="btn-card danger btn-perm-delete" data-id="${rec.id}" title="Permanently Delete">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>
                        Delete
                    </button>
                `;
            } else {
                actionsHtml = `
                    <button class="btn-card primary btn-play" data-id="${rec.id}" title="Play">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5,3 19,12 5,21"/></svg>
                        Play
                    </button>
                    <button class="btn-card btn-download" data-id="${rec.id}" title="Download">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                        Save
                    </button>
                    <button class="btn-card danger btn-delete" data-id="${rec.id}" title="Move to Trash">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>
                    </button>
                `;
            }

            card.innerHTML = `
                <div class="library-card-thumb">
                    <video src="${rec.url}" preload="metadata" muted></video>
                    <div class="library-card-duration">${formatTime(rec.duration)}</div>
                </div>
                <div class="library-card-body">
                    <div class="library-card-name" title="${rec.name}">${rec.name}</div>
                    <div class="library-card-meta">${formatDate(rec.date)} · ${formatBytes(rec.size)}</div>
                    <div class="library-card-actions">
                        ${actionsHtml}
                    </div>
                </div>
            `;

            if (rec.isDeleted) {
                // Restore button
                card.querySelector('.btn-restore').addEventListener('click', () => {
                    rec.isDeleted = false;
                    saveRecordingDB(rec);
                    renderLibrary();
                    showToast('Recording restored', 'success');
                });
                
                // Permanent Delete button
                card.querySelector('.btn-perm-delete').addEventListener('click', () => {
                    if (confirm('Are you sure you want to permanently delete this video? This cannot be undone.')) {
                        deleteRecording(rec.id, true);
                    }
                });
            } else {
                // Play button
                card.querySelector('.btn-play').addEventListener('click', () => openPlayback(rec));
                // Download
                card.querySelector('.btn-download').addEventListener('click', () => downloadRecording(rec));
                // Soft Delete
                card.querySelector('.btn-delete').addEventListener('click', () => deleteRecording(rec.id, false));
            }

            // Load video thumbnail at 1sec
            const thumbVid = card.querySelector('video');
            thumbVid.addEventListener('loadeddata', () => {
                thumbVid.currentTime = 1;
            });

            dom.libraryGrid.appendChild(card);
        });
    }

    function downloadRecording(rec) {
        const a = document.createElement('a');
        a.href = rec.url;
        a.download = rec.name;
        a.click();
        showToast('Download started', 'success');
    }

    function deleteRecording(id, permanent = false) {
        const idx = state.recordings.findIndex(r => r.id === id);
        if (idx !== -1) {
            if (permanent) {
                URL.revokeObjectURL(state.recordings[idx].url);
                state.recordings.splice(idx, 1);
                deleteRecordingDB(id);
                showToast('Recording permanently deleted', 'info');
            } else {
                state.recordings[idx].isDeleted = true;
                saveRecordingDB(state.recordings[idx]);
                showToast('Moved to Trash', 'info');
            }
            renderLibrary();
        }
    }

    // ---- Playback Modal ----
    function openPlayback(rec) {
        // Create modal if not exists
        let modal = document.querySelector('.playback-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.className = 'playback-modal';
            modal.innerHTML = `
                <div class="playback-wrapper">
                    <button class="playback-close" aria-label="Close Playback">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                    </button>
                    <video class="playback-video" controls autoplay></video>
                </div>
            `;
            document.body.appendChild(modal);

            modal.querySelector('.playback-close').addEventListener('click', () => {
                const vid = modal.querySelector('video');
                vid.pause();
                vid.src = '';
                modal.classList.add('hidden');
            });

            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    const vid = modal.querySelector('video');
                    vid.pause();
                    vid.src = '';
                    modal.classList.add('hidden');
                }
            });
        }

        modal.querySelector('video').src = rec.url;
        modal.classList.remove('hidden');
    }

    // ---- Comet Automation Engine ----
    function setCometStatus(text, active = true) {
        dom.cometStatus.classList.remove('hidden');
        dom.cometStatusText.textContent = text;
        if (active) {
            dom.cometStatus.classList.add('active');
        } else {
            dom.cometStatus.classList.remove('active');
        }
    }

    function buildCometPrompt(url, options) {
        // We generate a Native JavaScript automation script instead of an LLM prompt
        const jsCode = `// ScreenFlow Native Automation Script
(function() {
    console.log("🎬 ScreenFlow Auto-Play initialized.");
    let currentVideo = null;
    let allowAutoplay = ${options.autoplay};
    let allowFullscreen = ${options.fullscreen};
    let allowNext = ${options.autonext};
    
    function checkVideo() {
        if (currentVideo && !currentVideo.ended && !currentVideo.paused) return;

        const video = document.querySelector('video');
        if (video && video !== currentVideo) {
            console.log("Found new video on page.");
            currentVideo = video;
            
            if (allowFullscreen) {
                try {
                    if (video.requestFullscreen) video.requestFullscreen();
                    else if (video.webkitRequestFullscreen) video.webkitRequestFullscreen();
                } catch(e) {}
            }
            
            if (allowAutoplay) {
                video.play().catch(e => {
                    console.log("Autoplay prevented by browser. Please click ANYWHERE on the page to allow playback.");
                });
            }
            
            video.addEventListener('ended', onEnded, { once: true });
        }
    }

    function onEnded() {
        console.log("Video ended.");
        if (allowFullscreen) {
            try {
                if (document.fullscreenElement) document.exitFullscreen();
                else if (document.webkitFullscreenElement) document.webkitExitFullscreen();
            } catch(e) {}
        }
        
        if (allowNext) {
            console.log("Looking for Next button...");
            setTimeout(findAndClickNext, 1500); // Wait 1.5s for UI to update
        }
    }

    function findAndClickNext() {
        const keywords = ['next', 'continue', 'forward', 'mark as complete'];
        const elements = Array.from(document.querySelectorAll('a, button, div[role="button"]'));
        
        let nextBtn = elements.find(el => {
            const text = el.textContent.trim().toLowerCase();
            return keywords.some(kw => text === kw || text.includes(kw));
        });

        if (!nextBtn) {
            nextBtn = document.querySelector('[class*="next" i], [class*="continue" i], [id*="next" i]');
        }

        if (nextBtn) {
            console.log("Clicking next button:", nextBtn);
            nextBtn.click();
            if (nextBtn.href && window.location.href !== nextBtn.href) {
                window.location.href = nextBtn.href;
            }
        } else {
            console.log("No Next button found.");
            alert("ScreenFlow Automation: Stopped. Could not find a 'Next' button.");
        }
    }

    setInterval(checkVideo, 2000);
    checkVideo();
    console.log("✅ Script running! Make sure to click anywhere on this page if the browser blocks autoplay.");
})();`;

        return jsCode;
    }

    async function copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (err) {
            // Fallback
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.select();
            try {
                document.execCommand('copy');
                document.body.removeChild(ta);
                return true;
            } catch (e) {
                document.body.removeChild(ta);
                return false;
            }
        }
    }

    async function launchCometAutomation() {
        const url = dom.cometUrl.value.trim();
        if (!url) {
            showToast('Please enter a target website URL', 'error');
            return;
        }

        // Validate URL
        try {
            new URL(url);
        } catch (e) {
            showToast('Please enter a valid URL (e.g. https://example.com)', 'error');
            return;
        }

        try {
            // Step 1: Open the target URL in a new tab
            setCometStatus('Opening target website...', true);
            showToast('Opening target website in a new tab...', 'info');
            state.cometTab = window.open(url, '_blank');

            if (!state.cometTab) {
                showToast('Pop-up blocked! Please allow pop-ups for this site and try again.', 'error');
                setCometStatus('Pop-up blocked', false);
                return;
            }

            // Step 2: Wait for the page to load
            setCometStatus('Waiting for page to load...', true);
            await new Promise(resolve => setTimeout(resolve, 3000));

            // Step 3: Prompt the user to share the tab for recording
            setCometStatus('Select the video tab to record...', true);
            showToast('Select the tab you just opened to start recording it', 'info', 6000);

            const constraints = getQualityConstraints();
            const displayMediaOpts = {
                video: {
                    ...constraints,
                    cursor: dom.settingCursor.checked ? 'always' : 'never',
                },
                audio: true, // Always capture audio for video recording
                preferCurrentTab: false,
            };

            state.stream = await navigator.mediaDevices.getDisplayMedia(displayMediaOpts);

            // Step 4: Show preview
            dom.previewIdle.style.display = 'none';
            dom.previewVideo.classList.add('active');
            dom.previewVideo.srcObject = state.stream;

            // Step 5: Start recording immediately (no countdown)
            const mimeType = getMimeType();
            const options = { mimeType };
            if (mimeType) {
                state.mediaRecorder = new MediaRecorder(state.stream, options);
            } else {
                state.mediaRecorder = new MediaRecorder(state.stream);
            }

            state.recordedChunks = [];

            state.mediaRecorder.ondataavailable = (e) => {
                if (e.data && e.data.size > 0) {
                    state.recordedChunks.push(e.data);
                }
            };

            state.mediaRecorder.onstop = () => {
                finishRecording();
            };

            state.stream.getVideoTracks()[0].onended = () => {
                if (state.isRecording) {
                    stopRecording();
                }
            };

            // Start with no timeslice — one continuous WebM stream.
            state.mediaRecorder.start();
            state.isRecording = true;
            state.isPaused = false;

            // UI updates
            playSound('start');
            setStatus('recording', 'Recording in progress...');
            dom.btnRecord.classList.add('recording');
            dom.iconRecord.classList.add('hidden');
            dom.iconStop.classList.remove('hidden');
            dom.btnPause.disabled = false;
            dom.btnScreenshot.disabled = false;
            dom.recordingOverlay.classList.remove('hidden');
            startTimer();

        } catch (err) {
            console.error('Recording failed:', err);
            if (err.name === 'NotAllowedError') {
                showToast('Screen sharing was cancelled', 'error');
            } else {
                showToast('Recording failed: ' + err.message, 'error');
            }
            setStatus('idle', 'Ready to record');
            cleanupStreams();
        }
    }
    // ---- Keyboard Shortcuts ----
    document.addEventListener('keydown', (e) => {
        // Don't intercept when typing in inputs
        if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return;

        switch (e.key.toLowerCase()) {
            case 'r':
                if (e.ctrlKey || e.metaKey) return; // don't intercept browser refresh
                dom.btnRecord.click();
                break;
            case 'p':
                if (!dom.btnPause.disabled) dom.btnPause.click();
                break;
            case 's':
                if ((e.ctrlKey || e.metaKey) && e.shiftKey) {
                    e.preventDefault();
                    if (!dom.btnScreenshot.disabled) dom.btnScreenshot.click();
                }
                break;
            case 'escape':
                // Close any open modal
                if (!dom.settingsModal.classList.contains('hidden')) {
                    dom.settingsModal.classList.add('hidden');
                }
                const playbackModal = document.querySelector('.playback-modal');
                if (playbackModal && !playbackModal.classList.contains('hidden')) {
                    playbackModal.querySelector('.playback-close').click();
                }
                break;
        }
    });

    // ---- Feature Detection ----
    function checkBrowserSupport() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia) {
            showToast('Your browser does not support screen recording. Please use Chrome, Edge, or Firefox.', 'error', 8000);
            dom.btnRecord.disabled = true;
            dom.btnRecord.style.opacity = '0.3';
            dom.btnRecord.style.cursor = 'not-allowed';
            setStatus('idle', 'Screen recording not supported in this browser');
            return false;
        }
        return true;
    }

    // ---- Protect Against ScreenFlow Refresh ----
    window.addEventListener('beforeunload', (e) => {
        if (state.isRecording) {
            e.preventDefault();
            e.returnValue = 'You have a recording in progress. If you refresh or leave, it will be lost!';
        }
    });

    // ---- Init ----
    function init() {
        checkBrowserSupport();

        // Init DB and load recordings
        initDB().then(() => {
            return getRecordingsDB();
        }).then(recs => {
            // Sort to show newest first
            recs.sort((a,b) => b.date - a.date);
            // Re-create object URLs for loaded Blobs
            recs.forEach(r => {
                if (r.blob) r.url = URL.createObjectURL(r.blob);
                if (r.isDeleted === undefined) r.isDeleted = false;
            });
            state.recordings = recs;
            renderLibrary();
        }).catch(err => {
            console.warn('Could not initialize DB:', err);
            renderLibrary(); // render empty state
        });

        // Register Service Worker for bulletproof native push notifications
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('sw.js').then((reg) => {
                swRegistration = reg;
                console.log('✅ ServiceWorker registered: Bulletproof push notifications enabled!');
            }).catch(e => {
                console.warn('ServiceWorker registration failed (Native notifications might not bypass focus assist):', e);
            });
        }

        // Set min datetime for schedule inputs
        const now = new Date();
        now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
        const minDateStr = now.toISOString().slice(0, 16);
        dom.autoSchedule.min = minDateStr;
        dom.autoStopAt.min = minDateStr;

        // Check existing notification permission
        if ('Notification' in window && Notification.permission === 'granted') {
            state.notificationsEnabled = true;
            updateNotificationButton();
        }

        showToast('ScreenFlow ready! Press R to start recording', 'info', 5000);
        sendNotification('ScreenFlow Ready', 'Your screen recorder is ready to use. Press R to start recording.');
    }

    init();
})();
