import { Room, RoomEvent, Track, ParticipantEvent } from 'https://unpkg.com/livekit-client@2.7.3/dist/livekit-client.esm.mjs';

const room = new Room({
    adaptiveStream: true,
    dynacast: true,
    autoSubscribe: true,
  });

  const stateCircle = document.getElementById('stateCircle');
  const stateLabel = document.getElementById('stateLabel');
  const voiceToggle = document.getElementById('voiceToggle');
  const statusEl = document.getElementById('status');

  const STATE = { IDLE: 'idle', CONNECTED: 'connected', LISTENING: 'listening', SPEAKING: 'speaking', OFF: 'off' };
  let voiceOn = false;
  let currentState = STATE.IDLE;

  function setState(s) {
    currentState = s;
    stateCircle.className = 'state-circle ' + s;
    const labels = {
      idle: '接続していません',
      connected: '接続中（音声OFF）',
      listening: '聞いています',
      speaking: '話しています',
      off: '音声OFF'
    };
    stateLabel.textContent = labels[s] || s;
  }

  function setStatus(msg) {
    statusEl.textContent = msg || '';
  }

  voiceToggle.addEventListener('click', function () {
    voiceOn = !voiceOn;
    voiceToggle.classList.toggle('on', voiceOn);
    if (!room || room.state !== 'connected') return;
    room.localParticipant.setMicrophoneEnabled(voiceOn).then(function () {
      setState(voiceOn ? (currentState === STATE.SPEAKING ? STATE.SPEAKING : STATE.LISTENING) : STATE.CONNECTED);
    }).catch(function (e) {
      setStatus('マイク切替失敗: ' + (e && e.message));
    });
  });

  function updateSpeakingState() {
    if (!voiceOn) return;
    let anySpeaking = false;
    room.remoteParticipants.forEach(function (p) {
      if (p.isSpeaking) anySpeaking = true;
    });
    setState(anySpeaking ? STATE.SPEAKING : STATE.LISTENING);
  }

  room.on(RoomEvent.Connected, function () {
    setStatus('接続しました');
    voiceOn = false;
    voiceToggle.classList.remove('on');
    room.localParticipant.setMicrophoneEnabled(false).then(function () {
      setState(STATE.CONNECTED);
    });
  });

  room.on(RoomEvent.Disconnected, function () {
    setState(STATE.IDLE);
    setStatus('切断しました');
  });

  room.on(RoomEvent.ParticipantConnected, function (participant) {
    participant.on(ParticipantEvent.IsSpeakingChanged, updateSpeakingState);
    updateSpeakingState();
  });

  room.on(RoomEvent.TrackSubscribed, function (track, publication, participant) {
    if (track.kind === Track.Kind.Audio) {
      var el = track.attach();
      var container = document.getElementById('audioContainer');
      if (container) container.appendChild(el); else document.body.appendChild(el);
      participant.on(ParticipantEvent.IsSpeakingChanged, updateSpeakingState);
      updateSpeakingState();
    }
  });

  room.on(RoomEvent.Reconnecting, function () {
    setStatus('再接続中…');
  });

  room.on(RoomEvent.Reconnected, function () {
    setStatus('再接続しました');
    setState(voiceOn ? STATE.LISTENING : STATE.CONNECTED);
  });

  function connect() {
    setStatus('接続中…');
    fetch('/token?room=simple-mode')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.token || !data.url) throw new Error('token または url がありません');
        return room.connect(data.url, data.token);
      })
      .then(function () {
        setStatus('');
      })
      .catch(function (e) {
        setState(STATE.IDLE);
        setStatus('接続失敗: ' + (e && (e.message || e)));
      });
  }

  connect();
