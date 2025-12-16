import urllib.request
import os
import ssl
import sys

# =================配置区域=================
# 忽略 SSL 证书验证 (解决校园网/代理问题)
ssl._create_default_https_context = ssl._create_unverified_context

# 目标下载清单
# 格式: "保存的文件名": "下载地址"
FILES = {
    # 1. PixiJS 引擎 (v6.5.10 稳定版)
    "pixi-v6.js": "https://cdnjs.cloudflare.com/ajax/libs/pixi.js/6.5.10/browser/pixi.min.js",
    
    # 2. Live2D 官方核心库 (CRITICAL: 这是最容易缺少的“大脑”)
    # 注意：这里我们强制保存为 live2dcubismcore.min.js 以区分其他 core 文件
    "live2dcubismcore.min.js": "https://cubism.live2d.com/sdk-web/cubismcore/live2dcubismcore.min.js",
    
    # 3. Pixi Live2D Display 插件 (v4.0.0 整合版)
    # 这个文件包含了插件的渲染逻辑
    "display-v4.js": "https://cdn.jsdelivr.net/npm/pixi-live2d-display@0.4.0/dist/index.min.js",

    # 4. (可选) 插件的内部 Core (为了兼容性，防止你的代码引用了它)
    "core.js": "https://cdn.jsdelivr.net/npm/pixi-live2d-display@0.4.0/dist/cubism4.min.js"
}
# =========================================

def download_files():
    # 获取当前脚本所在目录的 static 子目录
    base_dir = os.path.dirname(os.path.abspath(__file__))
    static_dir = os.path.join(base_dir, "static")
    
    if not os.path.exists(static_dir):
        try:
            os.makedirs(static_dir)
            print(f"📂 创建目录: {static_dir}")
        except Exception as e:
            print(f"❌ 无法创建目录: {e}")
            return

    print(f"🚀 开始修复前端依赖... (目标目录: {static_dir})\n")

    success_count = 0
    
    for filename, url in FILES.items():
        filepath = os.path.join(static_dir, filename)
        print(f"⬇️  正在下载: {filename} ...")
        
        try:
            # 伪装请求头，防止被服务器拦截
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            req = urllib.request.Request(url, headers=headers)
            
            with urllib.request.urlopen(req, timeout=30) as response:
                data = response.read()
                file_size_kb = len(data) / 1024
                
                # 简单校验：如果文件小于 1KB，可能是下载了错误页面
                if file_size_kb < 1:
                    print(f"   ⚠️  警告: {filename} 太小了 ({file_size_kb:.2f} KB)，可能是个空文件或错误页！")
                else:
                    with open(filepath, "wb") as f:
                        f.write(data)
                    print(f"   ✅ 成功 ({file_size_kb:.1f} KB)")
                    success_count += 1
                    
        except Exception as e:
            print(f"   ❌ 失败: {str(e)}")
            print(f"      -> 请尝试手动下载: {url}")

    print("-" * 40)
    if success_count == len(FILES):
        print("🎉 所有文件下载成功！前端环境已修复。")
        print("👉 请确保你的 index.html 引用顺序如下：")
        print("   1. pixi-v6.js")
        print("   2. live2dcubismcore.min.js")
        print("   3. display-v4.js")
        print("   4. script.js")
    else:
        print(f"⚠️  完成了 {success_count}/{len(FILES)} 个文件。请检查上方报错的网络链接。")

if __name__ == "__main__":
    download_files()