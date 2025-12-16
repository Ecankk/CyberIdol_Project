// =========================================
//        Cyber-Idol 前端交互逻辑
// =========================================

// --- UI 元素引用 ---
const wsDot = document.getElementById("ws-dot");
const recordBtn = document.getElementById("record-btn");
const chatHistory = document.getElementById("chat-history");
const characterSelect = document.getElementById("character-select");
const textInput = document.getElementById("text-input");
const sendBtn = document.getElementById("send-btn");
const micStatus = document.getElementById("mic-status");
const hintText = document.getElementById("hint-text");
const live2dContainer = document.getElementById("live2d-view");
const personaInput = document.getElementById("persona-input");
const updatePersonaBtn = document.getElementById("update-persona-btn");

// --- 全局变量 ---
let ws = null;
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let spacePressing = false;

// --- Live2D & Pixi 变量 ---
const LIVE2D_DEFAULT = "/static/live2d/Taoist/Taoist.model3.json";
let live2dMap = {}; // { model_id: live2d_path }
let availableModels = []; // 后端返回的模型列表
let app = null;
let currentModel = null;
let audioContext = null;
let audioAnalyser = null;
let isSpeaking = false;
let isDragging = false;
let dragData = null;
let modelLoading = null;

// =========================================
//    1. 模型路径映射 (从后端动态加载)
// =========================================

// =========================================
//    2. Live2D 初始化
// =========================================

async function initPixiApp() {
    if (!window.PIXI) return console.error("❌ PIXI 未加载");
    const Live2DModel = PIXI.live2d?.Live2DModel || window.PixiLive2dDisplay?.Live2DModel;
    if (!Live2DModel) {
        live2dContainer.innerHTML = `<div style="color:red;padding:20px;">Live2D 插件未加载</div>`;
        return;
    }

    try { Live2DModel.registerTicker(PIXI.Ticker); } catch (e) {}

    if (!app) {
        app = new PIXI.Application({
            view: document.createElement("canvas"),
            autoStart: true,
            resizeTo: live2dContainer,
            backgroundAlpha: 0, 
        });
        live2dContainer.innerHTML = "";
        live2dContainer.appendChild(app.view);
        
        app.view.addEventListener('pointerdown', onDragStart);
        window.addEventListener('pointermove', onDragMove);
        window.addEventListener('pointerup', onDragEnd);
        app.view.addEventListener('wheel', onWheelZoom, { passive: false });
        app.ticker.add(updateLipSync);
    }
}

async function loadModel(characterId) {
    if (modelLoading) await modelLoading;
    if (!app) return;
    const modelPath = live2dMap[characterId] || LIVE2D_DEFAULT;
    console.log("加载 Live2D 模型：", characterId, modelPath);
    
    if (currentModel && currentModel._path === modelPath) return;

    modelLoading = (async () => {
        // 先清空舞台，确保不会残留旧模型
        app.stage.removeChildren();
        if (currentModel) { 
            currentModel.destroy({ children: true, texture: true, baseTexture: true }); 
            currentModel = null; 
        }

        try {
            const Live2DModel = PIXI.live2d?.Live2DModel || window.PixiLive2dDisplay?.Live2DModel;
            currentModel = await Live2DModel.from(modelPath);
            currentModel._path = modelPath;
            app.stage.addChild(currentModel);

            const containerW = live2dContainer.clientWidth;
            const containerH = live2dContainer.clientHeight;
            const scale = Math.min((containerW * 1.2)/currentModel.width, (containerH * 1.2)/currentModel.height);
            
            currentModel.scale.set(scale);
            currentModel.anchor.set(0.5, 0.5);
            currentModel.x = containerW / 2;
            currentModel.y = containerH / 2 + 100;

            currentModel.interactive = true;
            currentModel.on("hit", (hitAreas) => {
                if (hitAreas.includes("Head")) {
                    currentModel.expression("surprised");
                    currentModel.motion("TapHead");
                } else {
                    currentModel.motion("Tap");
                }
            });
            console.log("✅ 模型加载成功");
        } catch (err) {
            console.error("❌ 模型加载失败:", err);
        }
    })();
    try {
        await modelLoading;
    } finally {
        modelLoading = null;
    }
}

// =========================================
//    3. 交互逻辑 (拖拽 + 滚轮)
// =========================================
let dragStartPoint = { x: 0, y: 0 };
let modelStartPos = { x: 0, y: 0 };

function onDragStart(e) {
    if (!currentModel) return;
    isDragging = true;
    dragStartPoint = { x: e.clientX, y: e.clientY };
    modelStartPos = { x: currentModel.x, y: currentModel.y };
}

function onDragMove(e) {
    if (!isDragging || !currentModel) return;
    const dx = e.clientX - dragStartPoint.x;
    const dy = e.clientY - dragStartPoint.y;
    currentModel.x = modelStartPos.x + dx;
    currentModel.y = modelStartPos.y + dy;
}

function onDragEnd() { isDragging = false; }

function onWheelZoom(e) {
    if (!currentModel) return;
    e.preventDefault();
    const zoomSpeed = 0.0015; 
    const delta = -e.deltaY * zoomSpeed;
    let newScale = currentModel.scale.x + delta;
    if (newScale < 0.1) newScale = 0.1;
    if (newScale > 10.0) newScale = 10.0;
    currentModel.scale.set(newScale);
}

// =========================================
//    4. 真实口型 (自然抖动)
// =========================================

function initAudioContext() {
    if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        audioAnalyser = audioContext.createAnalyser();
        audioAnalyser.fftSize = 256;
    }
    if (audioContext.state === 'suspended') { audioContext.resume(); }
}

function updateLipSync() {
    if (!currentModel || !currentModel.internalModel) return;

    let volume = 0;
    if (isSpeaking && audioAnalyser) {
        const dataArray = new Uint8Array(audioAnalyser.frequencyBinCount);
        audioAnalyser.getByteFrequencyData(dataArray);
        
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
        const average = sum / dataArray.length;
        
        let rawVolume = average / 50; 
        if (rawVolume < 0.1) rawVolume = 0;

        if (rawVolume > 0) {
            const time = Date.now() / 90; 
            const flutter = (Math.sin(time) + 1) / 2;
            volume = rawVolume * (0.4 + 0.6 * flutter);
        }
        if (volume > 1.0) volume = 1.0;
    }

    try {
        currentModel.internalModel.coreModel.setParameterValueById("ParamMouthOpenY", volume);
    } catch (e) {}
}

function playAudio(blobOrUrl) {
    initAudioContext();
    isSpeaking = true;
    const playBuffer = (buffer) => {
        const source = audioContext.createBufferSource();
        source.buffer = buffer;
        source.connect(audioAnalyser);
        audioAnalyser.connect(audioContext.destination);
        source.start(0);
        if (currentModel) currentModel.motion("TapBody");
        source.onended = () => {
            isSpeaking = false;
            try { currentModel.internalModel.coreModel.setParameterValueById("ParamMouthOpenY", 0); } catch(e){}
        };
    };
    if (blobOrUrl instanceof Blob) {
        const reader = new FileReader();
        reader.onload = function() { audioContext.decodeAudioData(this.result, playBuffer); };
        reader.readAsArrayBuffer(blobOrUrl);
    } else if (typeof blobOrUrl === 'string') {
        fetch(blobOrUrl).then(res => res.arrayBuffer()).then(buf => audioContext.decodeAudioData(buf)).then(playBuffer).catch(console.error);
    }
}

// =========================================
//    5. WebSocket 与 消息 (含人设更新修复)
// =========================================

function connectWs() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}/ws/chat`;
    ws = new WebSocket(wsUrl);
    ws.binaryType = "arraybuffer";
    ws.onopen = () => {
        setWsState(true);
        if (characterSelect.value) ws.send(JSON.stringify({ character_id: characterSelect.value }));
    };
    ws.onclose = () => { setWsState(false); setTimeout(connectWs, 3000); };
    
    ws.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer || event.data instanceof Blob) {
            const blob = new Blob([event.data], { type: 'audio/wav' });
            const audioUrl = URL.createObjectURL(blob);
            playAudio(blob);
            return;
        }
        try {
            const msg = JSON.parse(event.data);
            if (msg.type === "transcript") addChatMessage("user", msg.text);
            if (msg.type === "tts") {
                if (msg.url) {
                    playAudio(msg.url);
                    addChatMessage("agent", msg.text, msg.url);
                } else {
                    addChatMessage("agent", msg.text);
                }
            }
            if (msg.type === "error") addSystemMessage(`❌ ${msg.message}`);
        } catch (e) {}
    };
}

// =========================================
//    6. UI 逻辑
// =========================================

function scrollToBottom() { chatHistory.scrollTop = chatHistory.scrollHeight; }
function setWsState(connected) { wsDot.classList.toggle("connected", connected); }
function addSystemMessage(text) {
    const div = document.createElement("div"); div.className = "message system";
    div.textContent = text; chatHistory.appendChild(div); scrollToBottom();
}
function addChatMessage(role, text, audioUrl = null) {
    const div = document.createElement("div"); 
    div.className = `message ${role}`;
    div.innerHTML = text.replace(/\n/g, "<br>");
    if (audioUrl) {
        div.classList.add("playable");
        div.title = "点击重播";
        div.onclick = () => playAudio(audioUrl);
    }
    chatHistory.appendChild(div); 
    scrollToBottom();
}

async function fetchCharacters() {
    try {
        const res = await fetch("/characters");
        const data = await res.json();
        characterSelect.innerHTML = "";
        data.forEach((item) => {
            const opt = document.createElement("option"); opt.value = item.id; opt.textContent = item.name || item.id; characterSelect.appendChild(opt);
        });
        if(characterSelect.value) await loadModel(characterSelect.value);
    } catch (err) {
        console.warn("Using default char"); await loadModel("default");
    }
}

async function fetchLive2DModels() {
    try {
        const resp = await fetch("/models");
        if (!resp.ok) throw new Error("获取模型清单失败");
        availableModels = await resp.json();

        live2dMap = {};
        availableModels.forEach((item) => {
            if (item.id) {
                live2dMap[item.id] = item.live2d || LIVE2D_DEFAULT;
            }
        });
        if (characterSelect.value) await loadModel(characterSelect.value);
    } catch (err) {
        console.error("加载 Live2D 模型清单失败：", err);
        live2dMap = {};
    }
}

// =========================================
//    7. 录音、输入与 人设更新 (关键修复)
// =========================================

navigator.mediaDevices.getUserMedia({ audio: true }).then(stream => {
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };
    mediaRecorder.onstart = () => { isRecording=true; recordBtn.classList.add("recording"); micStatus.innerText="REC"; micStatus.style.color="#ff2e63"; audioChunks=[]; };
    mediaRecorder.onstop = () => { isRecording=false; recordBtn.classList.remove("recording"); micStatus.innerText="Standby"; micStatus.style.color="#555"; if(ws&&ws.readyState===1) ws.send(new Blob(audioChunks, {type:"audio/webm"})); };
}).catch(console.error);

function startRecord() { if(mediaRecorder && mediaRecorder.state==="inactive") mediaRecorder.start(); }
function stopRecord() { if(mediaRecorder && mediaRecorder.state==="recording") mediaRecorder.stop(); }

recordBtn.onmousedown = startRecord; recordBtn.onmouseup = stopRecord; recordBtn.onmouseleave = stopRecord;
window.addEventListener("keydown", (e) => { if (e.code === "Space" && !spacePressing && document.activeElement !== textInput && document.activeElement !== personaInput) { spacePressing = true; e.preventDefault(); startRecord(); }});
window.addEventListener("keyup", (e) => { if (e.code === "Space") { spacePressing = false; stopRecord(); } });

sendBtn.onclick = () => { const text = textInput.value.trim(); if(text && ws) { ws.send(JSON.stringify({character_id: characterSelect.value, text_input: text})); addChatMessage("user", text); textInput.value=""; } };
textInput.onkeydown = (e) => { if(e.key==="Enter") sendBtn.click(); };
characterSelect.onchange = () => { if(ws) ws.send(JSON.stringify({character_id: characterSelect.value})); loadModel(characterSelect.value); };

// 🎯【核心修复】更新人设按钮
updatePersonaBtn.onclick = () => {
    const prompt = personaInput.value.trim();
    if (!prompt) return;

    if (ws && ws.readyState === WebSocket.OPEN) {
        // 发送标准的配置更新 JSON
        ws.send(JSON.stringify({ 
            type: "config", 
            system_prompt: prompt 
        }));
        
        // 前端反馈
        const oldText = updatePersonaBtn.innerText;
        updatePersonaBtn.innerText = "已发送 📡";
        updatePersonaBtn.style.color = "#15f5ba";
        addSystemMessage("人设已更新");
        
        setTimeout(() => { 
            updatePersonaBtn.innerText = oldText; 
            updatePersonaBtn.style.color = ""; 
        }, 1500);
    } else {
        addSystemMessage("❌ 未连接服务器");
    }
};

window.onload = async () => {
    initPixiApp();
    await fetchCharacters();
    await fetchLive2DModels();
    connectWs();
    document.body.addEventListener('click', initAudioContext, { once: true });
};
