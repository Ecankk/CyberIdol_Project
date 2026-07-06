# Live2D Current Status Report

## 1. Overview

当前项目中的 Live2D 部分已经具备一个可运行的基础框架，核心目标是：

- 在 Web 页面左侧区域嵌入一个 Live2D 人物
- 通过前端脚本动态加载模型
- 在播放 TTS 音频时，驱动人物嘴型做简单发音模拟
- 提供最基本的模型交互能力，如拖拽、缩放、点击事件钩子

从当前实现来看，Live2D 已经可以作为页面中的“虚拟人物展示层”工作，并且已经和语音播放流程联动。但它仍然是一个偏“基础接入版”的实现，还没有完成更完整的模型资源管理、动作编排和多角色资源规范化。

---

## 2. 当前资源清单

### 2.1 Web 端加载的 Live2D 相关脚本

页面在启动时会加载以下脚本资源：

- `/static/pixi-v6.js`
- `/static/live2dcubismcore.min.js`
- `/static/core.js`
- `/static/display-v4.js`
- `/static/script.js`

其中：

- `pixi-v6.js` 提供 PixiJS 渲染能力
- `live2dcubismcore.min.js` 提供 Live2D Cubism Core
- `core.js` 和 `display-v4.js` 用于把 Live2D 模型接入 Pixi 渲染体系
- `script.js` 是当前项目自己的前端控制脚本

### 2.2 当前实际存在的本地 Live2D 模型资源

当前本地存在的模型目录为：

- `static/live2d/Taoist/`

这个目录下当前可见的关键文件包括：

- `Taoist.model3.json`
- `Taoist.moc3`
- `Taoist.physics3.json`
- `Taoist.cdi3.json`
- `Taoist.vtube.json`
- `40a8f99df3c926db32228e3d7907c04f.png`
- `fire.motion3.json`
- `fly.motion3.json`
- `idle.motion3.json`
- `items_pinned_to_model.json`
- `Taoist.8192/texture_00.png`
- `Taoist.8192/texture_01.png`
- `Taoist.8192/texture_02.png`
- `expressions/` 目录下的一组 `*.exp3.json`

### 2.3 当前资源的组织特点

当前 `Taoist` 资源包已经包含：

- 模型本体
- 贴图
- 物理配置
- 参数显示信息
- 若干表情文件
- 若干动作文件
- 一份 `vtube` 扩展元数据

也就是说，从素材角度看，这个模型包比当前网页真正使用到的内容更丰富。

---

## 3. 当前 Web 端是如何加载 Live2D 的

### 3.1 页面中的容器结构

Live2D 被放在页面左侧面板的 `live2d-wrapper` 中，真正挂载 Pixi canvas 的容器是：

- `#live2d-view`

也就是说，当前网页结构是：

1. HTML 先提供一个固定的容器
2. JavaScript 初始化 Pixi Application
3. 把 Pixi 的 canvas 插入到这个容器中
4. 再把 Live2D 模型挂到 Pixi 的舞台上

### 3.2 默认模型路径

当前前端脚本中写死的默认模型路径是：

- `/static/live2d/Taoist/Taoist.model3.json`

这意味着即使后端没有返回模型映射，页面依然会回退加载 `Taoist` 模型。

### 3.3 加载流程

当前加载流程大致如下：

1. 页面 `window.onload`
2. 执行 `initPixiApp()`
3. 拉取 `/characters`
4. 拉取 `/models`
5. 根据 `/models` 返回结果构建 `live2dMap`
6. 对当前角色调用 `loadModel(characterId)`
7. 如果该角色没有映射到具体 `live2d` 路径，则回退到默认 `Taoist.model3.json`

### 3.4 运行时模型切换逻辑

当前模型切换逻辑有这些特点：

- 如果已有模型且路径没变，则不重复加载
- 如果要切换模型，会先清空 `app.stage`
- 再销毁旧模型
- 然后重新执行 `Live2DModel.from(modelPath)`

这是一套典型的“整模型卸载再重载”的方案，简单直接，适合当前阶段。

---

## 4. 当前的渲染与摆放方式

### 4.1 Pixi 初始化方式

当前是通过 `new PIXI.Application(...)` 创建渲染上下文：

- 使用一个动态创建的 `canvas`
- `resizeTo` 绑定到 `live2dContainer`
- `backgroundAlpha: 0`

这意味着：

- Live2D 画布尺寸会跟容器同步
- 背景透明，可以融入网页布局

### 4.2 模型初始摆放方式

模型加载完成后，会做如下初始设置：

- 根据容器宽高和模型尺寸自动计算缩放比例
- 使用 `anchor.set(0.5, 0.5)`
- 放置到容器水平居中
- `y` 方向向下偏移 `100`

这说明当前人物的默认摆放逻辑是“偏舞台展示型”的，而不是严格按照模型原始原点摆放。

---

## 5. 当前已经实现的 Live2D 操作形式

## 5.1 拖拽

当前支持鼠标拖拽模型：

- `pointerdown` 记录拖拽起点
- `pointermove` 更新模型位置
- `pointerup` 结束拖拽

实现效果：

- 用户可以直接拖动人物在显示区域中的位置

### 5.2 滚轮缩放

当前支持鼠标滚轮缩放模型：

- 缩放速度固定为 `0.0015`
- 最小缩放 `0.1`
- 最大缩放 `10.0`

实现效果：

- 用户可以手动放大或缩小人物

### 5.3 点击交互钩子

当前脚本中已经写了点击命中逻辑：

- 如果命中区域包含 `Head`
  - 调用 `currentModel.expression("surprised")`
  - 调用 `currentModel.motion("TapHead")`
- 否则
  - 调用 `currentModel.motion("Tap")`

这表示当前代码层面已经预留了：

- 点头部触发表情和动作
- 点其他区域触发一般动作

但是这里有一个重要现实情况：

- 当前 `Taoist.model3.json` 中没有声明 `Motions`
- 当前 `Taoist.model3.json` 中也没有声明 `Expressions`
- 当前检索结果里也没有看到 `HitAreas` 在 `model3.json` 中被显式声明

所以目前这套点击交互更像是“预留接口”而不是完全落地的动作系统。

也就是说：

- 代码已经具备调用动作与表情的方法
- 但当前网页实际加载的 `model3.json` 并没有把这些动作和表情正式挂接进去

---

## 6. 当前的口型驱动方式

### 6.1 驱动原理

当前口型联动采用的是音频频谱驱动方案：

1. 创建 `AudioContext`
2. 创建 `AnalyserNode`
3. 在播放音频时，把音频源接到 analyser
4. 在 Pixi ticker 中持续读取频谱能量
5. 用频谱平均值估算嘴巴张开程度
6. 写入 Live2D 参数：
   - `ParamMouthOpenY`

### 6.2 当前嘴型参数

当前模型显示信息 `Taoist.cdi3.json` 中确实存在：

- `ParamMouthOpenY`

因此当前嘴型联动是和模型现有参数真正对上的，不是空调用。

### 6.3 当前效果特点

当前口型动画有这些特点：

- 不是音素级口型
- 是基于音量的连续嘴巴张合
- 还额外叠加了一个轻微的正弦波 flutter

这会让嘴型看起来比纯音量驱动更自然一点，但本质上仍然是“简单模拟发音”。

这与课程任务中“有简单动画模拟”是匹配的。

---

## 7. 当前 Live2D 与语音功能的结合方式

### 7.1 TTS 到 Live2D 的联动

当前 TTS 音频播放流程是：

1. 后端返回一个音频 URL
2. 前端 `playAudio(...)`
3. 音频送入 `AudioContext`
4. `updateLipSync()` 在 ticker 中驱动嘴型
5. 音频播放结束时嘴型归零

附带行为：

- 音频开始播放时会尝试调用 `currentModel.motion("TapBody")`

但同样需要注意：

- 当前 `TapBody` 是否真的有效，取决于模型加载库和模型资源是否存在对应动作映射
- 现有 `model3.json` 本身没有把动作声明进去

因此当前真正稳定生效的是：

- 嘴型开合联动

而不是复杂动作联动。

### 7.2 录音到页面显示的联动

当前用户语音输入流程是：

1. 浏览器 `getUserMedia({ audio: true })`
2. `MediaRecorder` 录制
3. 将录到的 `audio/webm` 通过 WebSocket 发给后端
4. 后端转 `wav`
5. 后端调用 ASR
6. 前端收到 `transcript`
7. 文本显示到聊天区

这里 Live2D 并没有在“用户说话时”专门做独立动作驱动，当前更明显的联动仍然是：

- 机器人说话时的人物嘴型模拟

---

## 8. 后端在 Live2D 这件事上扮演的角色

后端当前主要负责两件和 Live2D 间接相关的事：

### 8.1 提供静态资源访问

FastAPI 将整个 `static/` 目录挂载到：

- `/static`

因此：

- `Taoist.model3.json`
- `moc3`
- `textures`
- `physics3`
- `cdi3`
- 其他前端脚本

都依赖这个静态服务能力。

### 8.2 提供角色与模型映射接口

后端提供：

- `/characters`
- `/models`

当前逻辑是：

- 如果 `static/models/manifest.json` 存在，则 `/models` 返回 manifest
- 如果不存在，则根据 `settings.character_presets` 构造简表
- 如果 `settings.character_presets` 也为空，则回退成一个默认角色：
  - `default`

这意味着当前 Live2D 模型映射机制实际上还没有完全依赖到一个正式的角色资源仓库，而是：

- 有完整接口设计
- 但当前实际运行时主要依靠前端默认路径回退

---

## 9. 当前 `static/models` 的实际情况

当前项目里：

- 没有 `static/models/` 目录

所以目前和角色模型切换相关的真实运行状态是：

- `/characters` 返回默认角色 `default`
- `/models` 返回默认模型信息
- `live2dMap[item.id] = item.live2d || LIVE2D_DEFAULT`
- 因为没有 `item.live2d`
- 所以最终还是加载 `LIVE2D_DEFAULT`

换句话说：

- 当前网页并没有真正完成多角色 Live2D 资源切换
- 当前只有一个稳定默认入口：`Taoist`

---

## 10. 当前模型资源中的“已存在但未完全接入”部分

当前 `Taoist` 资源包内存在一些值得注意的内容：

### 10.1 表情文件

`expressions/` 下有大量 `*.exp3.json`，例如：

- `QAQ.exp3.json`
- `Q.exp3.json`
- `star.exp3.json`
- `black.exp3.json`
- `coat.exp3.json`
- `sword.exp3.json`

这说明模型资源本身有一定表情系统基础。

### 10.2 动作文件

目录中还存在：

- `idle.motion3.json`
- `fire.motion3.json`
- `fly.motion3.json`

### 10.3 VTube Studio 扩展元数据

`Taoist.vtube.json` 中还能看到：

- `IdleAnimation: idle.motion3.json`
- 若干热键触发的动画定义，例如：
  - `fire.motion3.json`
  - `fly.motion3.json`

这说明模型原始包其实带有一套偏 VTube Studio 风格的附加动作配置。

但是当前网页端的实际加载入口是：

- `Taoist.model3.json`

而不是：

- `Taoist.vtube.json`

因此这些额外动作信息并没有被网页直接利用。

---

## 11. 当前实现的优点

- 已完成 Live2D 在网页中的基础嵌入
- 已完成 Pixi + Live2D 的基本渲染链路
- 已完成默认模型加载
- 已完成拖拽、缩放等基础交互
- 已完成嘴型与 TTS 音频联动
- 已预留点击动作和表情接口
- 已设计角色接口与模型映射接口，便于后续扩展

---

## 12. 当前实现的限制

### 12.1 当前只稳定依赖默认模型

虽然代码设计了按角色映射模型的接口，但当前项目没有实际的 `static/models/manifest.json` 和角色目录，因此：

- 当前稳定运行依赖默认路径
- 并不是一套完整多角色 Live2D 管理系统

### 12.2 动作与表情资源未正式接入网页加载入口

当前目录里存在 motion / expression 文件，但 `Taoist.model3.json` 没有声明它们，因此：

- `expression("surprised")`
- `motion("TapHead")`
- `motion("Tap")`
- `motion("TapBody")`

这些调用在当前版本中更偏“预留能力”，而不是可保证稳定生效的正式功能。

### 12.3 点击命中区域能力尚不明确

当前代码监听了 `hit` 事件，并判断 `Head` 命中区域，但当前模型入口文件里没有清楚声明 hit area 配置，因此：

- 这部分是否真实触发
- 触发范围是否准确

都还需要进一步实测和资源校验。

### 12.4 资源与代码之间存在一部分“松耦合”

当前模型资源包比网页端真正使用到的内容更完整，但二者之间的映射还没有完全建立：

- 网页端主要吃 `model3.json`
- 模型包还带有 `vtube.json`
- motion / expression 存在，但未统一接入

这也是后续前端重构时非常值得整理的部分。

---

## 13. 当前最准确的状态判断

如果用一句话总结当前 Live2D 状态：

> 当前项目已经完成了“单模型 Live2D 展示 + 基础交互 + TTS 嘴型联动”的可运行框架，但还没有完成“多角色资源规范化管理 + 动作表情正式接入 + 更完整的前端表现层”。

---

## 14. 后续重构建议

如果后续要对前端做系统性重构，建议优先处理以下几件事：

1. 统一角色资源结构  
把 `static/models`、`manifest.json`、`live2d` 路径、TTS 角色信息整理成一个统一资源协议。

2. 正式接入动作与表情  
把 `Taoist.model3.json` 扩展为能被网页直接使用 motion / expression，或者在加载层显式读取附加配置。

3. 明确 hit area  
补齐头部、身体等命中区域配置，让点击反馈从“预留”变成“稳定生效”。

4. 把默认模型逻辑改为正式角色配置  
减少硬编码 `LIVE2D_DEFAULT`，把默认角色也纳入 manifest 管理。

5. 解耦渲染层与对话层  
把 Live2D 控制逻辑、音频控制逻辑、WebSocket 聊天逻辑拆成独立模块，便于前端重构。

---

## 15. Summary

当前 Live2D 不是“空壳接入”，而是已经具备以下真实能力：

- 页面中显示虚拟人物
- 模型可加载
- 模型可拖拽、缩放
- 播放语音时可驱动嘴型
- 可和 TTS / ASR / WebSocket 聊天链路结合

但它也还不是最终形态：

- 当前主要依赖单个默认模型
- 动作和表情资源虽然存在，但尚未在网页加载入口中正式接通
- 多角色资源管理仍处于接口已设计、资源层未完成的阶段

因此，这一版更适合定义为：

> Live2D 基础接入版 / 可运行原型版

