import uvicorn
import os

if __name__ == "__main__":
    print("🚀 EcoFlow AI v2.0 正在启动...")
    print("📍 访问地址: http://localhost:8000")
    print("⚠️  请确保已经在 .env 文件中填入 GEMINI_API_KEY 和 FIREBASE_KEY_PATH")
    
    # 强制 host='localhost'，这样 Mapbox 的域名校验就会通过 localhost
    # 同时也解决了 terminal 提示跳去数字 IP 的问题
    uvicorn.run(
        "main:app", 
        host="localhost", 
        port=8000, 
        reload=True,
        log_level="info"
    )