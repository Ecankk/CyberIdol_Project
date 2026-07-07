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
const connectionLabel = document.getElementById("connection-label");
const characterName = document.getElementById("character-name");
const characterSummary = document.getElementById("character-summary");
const stageStatus = document.getElementById("stage-status");
const stageStateValue = document.getElementById("stage-state-value");
const stageRoleValue = document.getElementById("stage-role-value");

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
let roleConfigs = {}; // { model_id: full config }
let app = null;
let currentModel = null;
let audioContext = null;
let audioAnalyser = null;
let isSpeaking = false;
let isDragging = false;
let dragData = null;
let modelLoading = null;

function getRoleConfig(characterId = characterSelect.value) {
    return roleConfigs[characterId] || null;
}

function getLive2DConfig(characterId = characterSelect.value) {
    return getRoleConfig(characterId)?.live2d_config || {};
}

function summarizeText(text, maxLength = 44) {
    if (!text) return "";
    return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
}

function setInteractionState(label, detail = label) {
    if (stageStateValue) stageStateValue.textContent = label;
    if (stageStatus) stageStatus.textContent = detail;
}

function setRecordingState(enabled) {
    document.body.classList.toggle("state-recording", enabled);
}

function setSpeakingState(enabled) {
    document.body.classList.toggle("state-speaking", enabled);
}

function updateCharacterPresentation(characterId = characterSelect.value) {
    const role = getRoleConfig(characterId);
    const selectedName = characterSelect?.selectedOptions?.[0]?.textContent;
    const displayName = role?.name || selectedName || characterId || "Cyber Idol";
    const modelPath = resolveModelPath(role) || LIVE2D_DEFAULT;
    const motions = role?.motions?.length ? `${role.motions.length} motion(s)` : "motion config pending";
    const summary = role?.preview || role?.description || `Model source: ${modelPath}`;

    if (characterName) characterName.textContent = displayName;
    if (characterSummary) characterSummary.textContent = `${summary} | ${motions}`;
    if (stageRoleValue) stageRoleValue.textContent = displayName;
}

function resolveModelPath(item) {
    if (!item) return "";
    if (typeof item.live2d === "string" && item.live2d) return item.live2d;
    if (item.live2d && typeof item.live2d === "object" && item.live2d.model) return item.live2d.model;
    if (item.live2d_config?.model) return item.live2d_config.model;
    return "";
}

function playModelMotion(motionName) {
    if (!currentModel || !motionName) return;
    try {
        currentModel.motion(motionName);
    } catch (e) {
        console.warn("Live2D motion failed:", motionName, e);
    }
}

function applyModelExpression(expressionName) {
    if (!currentModel || !expressionName) return;
    try {
        currentModel.expression(expressionName);
    } catch (e) {
        console.warn("Live2D expression failed:", expressionName, e);
    }
}

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
    const live2dConfig = getLive2DConfig(characterId);
    const modelPath = live2dConfig.model || live2dMap[characterId] || LIVE2D_DEFAULT;
    const roleName = getRoleConfig(characterId)?.name || characterSelect?.selectedOptions?.[0]?.textContent || characterId;
    console.log("加载 Live2D 模型：", characterId, modelPath);
    updateCharacterPresentation(characterId);
    
    if (currentModel && currentModel._path === modelPath) {
        setInteractionState("Ready", `${roleName} 已登场，可以开始交互。`);
        return;
    }

    modelLoading = (async () => {
        setInteractionState("Loading", `正在载入 ${roleName} 的 Live2D 模型...`);
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
            const autoScale = Math.min((containerW * 1.2)/currentModel.width, (containerH * 1.2)/currentModel.height);
            const scale = autoScale * (live2dConfig.scale ?? 1);
            
            currentModel.scale.set(scale);
            currentModel.anchor.set(0.5, 0.5);
            currentModel.x = containerW / 2 + (live2dConfig.offset_x ?? 0);
            currentModel.y = containerH / 2 + (live2dConfig.offset_y ?? 100);

            currentModel.interactive = true;
            currentModel.on("pointertap", () => {
                applyModelExpression(live2dConfig.tap_body_expression || live2dConfig.default_expression);
                playModelMotion(live2dConfig.tap_body_motion || live2dConfig.idle_motion);
            });
            currentModel.on("hit", (hitAreas) => {
                const headArea = live2dConfig.hit_areas?.head;
                if (headArea && hitAreas.includes(headArea)) {
                    applyModelExpression(live2dConfig.tap_head_expression || live2dConfig.default_expression);
                    playModelMotion(live2dConfig.tap_head_motion || live2dConfig.idle_motion);
                } else {
                    applyModelExpression(live2dConfig.tap_body_expression || live2dConfig.default_expression);
                    playModelMotion(live2dConfig.tap_body_motion || live2dConfig.idle_motion);
                }
            });
            applyModelExpression(live2dConfig.default_expression);
            playModelMotion(live2dConfig.entry_motion || live2dConfig.idle_motion);
            updateCharacterPresentation(characterId);
            setInteractionState("Ready", `${roleName} 已登场，可以开始对话。`);
            console.log("✅ 模型加载成功");
        } catch (err) {
            console.error("❌ 模型加载失败:", err);
            setInteractionState("Error", `${roleName} 模型加载失败，请检查资源路径。`);
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
    setSpeakingState(true);
    setInteractionState("Speaking", "角色正在播报回复。");
    const live2dConfig = getLive2DConfig();
    const playBuffer = (buffer) => {
        const source = audioContext.createBufferSource();
        source.buffer = buffer;
        source.connect(audioAnalyser);
        audioAnalyser.connect(audioContext.destination);
        source.start(0);
        playModelMotion(live2dConfig.talk_motion || live2dConfig.idle_motion);
        source.onended = () => {
            isSpeaking = false;
            setSpeakingState(false);
            try { currentModel.internalModel.coreModel.setParameterValueById("ParamMouthOpenY", 0); } catch(e){}
            playModelMotion(live2dConfig.idle_motion);
            if (!document.body.classList.contains("state-recording")) {
                setInteractionState("Ready", "播报完成，等待你的下一次输入。");
            }
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
        setInteractionState("Linked", "语音链路已连接，可以开始交互。");
        if (characterSelect.value) ws.send(JSON.stringify({ character_id: characterSelect.value }));
    };
    ws.onclose = () => {
        setWsState(false);
        setInteractionState("Reconnect", "连接中断，正在尝试重新连接...");
        setTimeout(connectWs, 3000);
    };
    
    ws.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer || event.data instanceof Blob) {
            const blob = new Blob([event.data], { type: 'audio/wav' });
            const audioUrl = URL.createObjectURL(blob);
            playAudio(blob);
            return;
        }
        try {
            const msg = JSON.parse(event.data);
            if (msg.type === "transcript") {
                addChatMessage("user", msg.text);
                setInteractionState("Transcript", `已识别语音：${summarizeText(msg.text, 32)}`);
            }
            if (msg.type === "tts") {
                const live2dConfig = getLive2DConfig();
                const expressionName = live2dConfig.emotion_map?.[msg.emotion] || getRoleConfig()?.emotion_to_expression?.[msg.emotion] || live2dConfig.default_expression;
                applyModelExpression(expressionName);
                setInteractionState("Responding", "角色已生成回复，正在准备播报。");
                if (msg.url) {
                    playAudio(msg.url);
                    addChatMessage("agent", msg.text, msg.url);
                } else {
                    addChatMessage("agent", msg.text);
                }
            }
            if (msg.type === "error") {
                addSystemMessage(`❌ ${msg.message}`);
                setInteractionState("Error", `服务返回错误：${msg.message}`);
            }
        } catch (e) {}
    };
}

// =========================================
//    6. UI 逻辑
// =========================================

function scrollToBottom() { chatHistory.scrollTop = chatHistory.scrollHeight; }
function setWsState(connected) {
    wsDot.classList.toggle("connected", connected);
    document.body.classList.toggle("state-connected", connected);
    if (connectionLabel) connectionLabel.textContent = connected ? "Online" : "Offline";
}
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
        const replayBadge = document.createElement("span");
        replayBadge.className = "replay-badge";
        replayBadge.textContent = "replay";
        div.appendChild(replayBadge);
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
        updateCharacterPresentation(characterSelect.value);
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
        roleConfigs = {};
        availableModels.forEach((item) => {
            if (item.id) {
                roleConfigs[item.id] = item;
                live2dMap[item.id] = resolveModelPath(item) || LIVE2D_DEFAULT;
            }
        });
        updateCharacterPresentation(characterSelect.value);
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
    mediaRecorder.onstart = () => {
        isRecording=true;
        recordBtn.classList.add("recording");
        micStatus.innerText="Listening";
        micStatus.style.color="#ff8fab";
        audioChunks=[];
        setRecordingState(true);
        setInteractionState("Listening", "正在聆听你的语音输入...");
    };
    mediaRecorder.onstop = () => {
        isRecording=false;
        recordBtn.classList.remove("recording");
        micStatus.innerText="Uploading";
        micStatus.style.color="#d4d4de";
        setRecordingState(false);
        setInteractionState("Uploading", "语音已捕获，正在发送识别...");
        if(ws&&ws.readyState===1) ws.send(new Blob(audioChunks, {type:"audio/webm"}));
        else setInteractionState("Offline", "语音已录制，但当前未连接服务器。");
    };
}).catch((error) => {
    console.error(error);
    if (micStatus) {
        micStatus.innerText = "Unavailable";
        micStatus.style.color = "#ff8fab";
    }
    setInteractionState("Mic Error", "无法访问麦克风，请检查浏览器权限。");
});

function startRecord() { if(mediaRecorder && mediaRecorder.state==="inactive") mediaRecorder.start(); }
function stopRecord() { if(mediaRecorder && mediaRecorder.state==="recording") mediaRecorder.stop(); }

recordBtn.onpointerdown = (e) => { e.preventDefault(); startRecord(); };
recordBtn.onpointerup = stopRecord;
recordBtn.onpointerleave = stopRecord;
recordBtn.onpointercancel = stopRecord;
window.addEventListener("keydown", (e) => { if (e.code === "Space" && !spacePressing && document.activeElement !== textInput && document.activeElement !== personaInput) { spacePressing = true; e.preventDefault(); startRecord(); }});
window.addEventListener("keyup", (e) => { if (e.code === "Space") { spacePressing = false; stopRecord(); } });

sendBtn.onclick = () => {
    const text = textInput.value.trim();
    if(text && ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({character_id: characterSelect.value, text_input: text}));
        addChatMessage("user", text);
        setInteractionState("Pending", `文本已发送：${summarizeText(text, 28)}`);
        textInput.value="";
    } else if (text) {
        addSystemMessage("❌ 当前未连接服务器");
        setInteractionState("Offline", "当前未连接服务器，文本消息没有发送。");
    }
};
textInput.onkeydown = (e) => { if(e.key==="Enter") sendBtn.click(); };
characterSelect.onchange = () => {
    updateCharacterPresentation(characterSelect.value);
    setInteractionState("Switching", "正在切换角色舞台...");
    if(ws) ws.send(JSON.stringify({character_id: characterSelect.value}));
    loadModel(characterSelect.value);
};

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
        updatePersonaBtn.style.color = "#ffb829";
        addSystemMessage("人设已更新");
        setInteractionState("Persona Updated", "新的人设配置已发送到后端会话。");
        
        setTimeout(() => { 
            updatePersonaBtn.innerText = oldText; 
            updatePersonaBtn.style.color = ""; 
        }, 1500);
    } else {
        addSystemMessage("❌ 未连接服务器");
        setInteractionState("Offline", "当前未连接服务器，无法更新人设。");
    }
};

window.onload = async () => {
    initPixiApp();
    setInteractionState("Booting", "正在准备舞台与模型配置...");
    await fetchCharacters();
    await fetchLive2DModels();
    connectWs();
    document.body.addEventListener('click', initAudioContext, { once: true });
};
