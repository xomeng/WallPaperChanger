import os
import random
import ctypes
import time
import threading
from pynput import keyboard

# ===================== 配置项 =====================
WALLPAPER_FOLDER = r"F:\桌面美化\壁纸"
SUPPORTED_FORMATS = ('.jpg', '.jpeg', '.png', '.bmp')
AUTO_CHANGE_INTERVAL = 30  # 自动换壁纸间隔（秒）
HOTKEY_CHANGE = keyboard.Key.f12  # F12换壁纸
#HOTKEY_HIDE_SHOW = {keyboard.Key.ctrl, keyboard.KeyCode(char='h')} 
HOTKEY_HIDE_SHOW = {keyboard.Key.f10} #F10隐藏/显示窗口
HOTKEY_REFRESH = {keyboard.Key.f9} #{keyboard.Key.ctrl, keyboard.KeyCode(char='r')}  # Ctrl+R刷新缓存
# ==================================================

# 全局状态变量
image_cache = []  # 保留缓存
is_setting_wallpaper = False
auto_change_running = True
current_pressed_keys = set()
# 窗口控制相关
hwnd = None
is_window_hidden = False

def init_dpi_awareness():
    """初始化DPI感知"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

def get_console_hwnd():
    """获取控制台窗口句柄"""
    global hwnd
    if not hwnd:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    return hwnd

def toggle_console_window():
    """隐藏/显示控制台窗口"""
    global is_window_hidden
    hwnd = get_console_hwnd()
    if hwnd:
        if is_window_hidden:
            ctypes.windll.user32.ShowWindow(hwnd, 9)
            is_window_hidden = False
            print("✅ 控制台窗口已显示")
        else:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
            is_window_hidden = True

def refresh_image_cache():
    """刷新壁纸缓存（核心函数）"""
    global image_cache
    image_cache = []  # 清空旧缓存
    
    if not os.path.exists(WALLPAPER_FOLDER):
        if not is_window_hidden:
            print(f"❌ 错误：壁纸文件夹不存在 - {WALLPAPER_FOLDER}")
        return

    def scan_images():
        """后台扫描最新壁纸"""
        global image_cache
        for root, _, files in os.walk(WALLPAPER_FOLDER):
            for file in files:
                if file.lower().endswith(SUPPORTED_FORMATS):
                    image_cache.append(os.path.join(root, file))
        if not is_window_hidden:
            print(f"✅ 缓存已刷新，共找到 {len(image_cache)} 张壁纸")
    
    # 异步刷新，不阻塞主线程
    threading.Thread(target=scan_images, daemon=True).start()

def set_wallpaper(image_path):
    """设置壁纸"""
    global is_setting_wallpaper
    if is_setting_wallpaper or not image_path:
        return
    
    is_setting_wallpaper = True
    try:
        ctypes.windll.user32.SystemParametersInfoW(
            20, 0, os.path.abspath(image_path), 3
        )
        if not is_window_hidden:
            print(f"🖼️ 已更换壁纸：{os.path.basename(image_path)}")
    except Exception as e:
        if not is_window_hidden:
            print(f"❌ 设置壁纸失败：{e}")
    finally:
        is_setting_wallpaper = False

def random_change_wallpaper():
    """随机换壁纸（使用缓存）"""
    if not image_cache:
        if not is_window_hidden:
            print("⚠️ 壁纸缓存为空，自动刷新缓存...")
        refresh_image_cache()  # 缓存为空时自动刷新
        time.sleep(0.1)  # 等待缓存刷新完成
        if not image_cache:
            if not is_window_hidden:
                print("⚠️ 刷新后仍无壁纸，请检查文件夹")
            return
    
    random_img = random.choice(image_cache)
    threading.Thread(target=set_wallpaper, args=(random_img,), daemon=True).start()

def auto_change_wallpaper_loop():
    """自动换壁纸循环"""
    global auto_change_running
    while auto_change_running:
        random_change_wallpaper()
        for _ in range(AUTO_CHANGE_INTERVAL):
            if not auto_change_running:
                break
            time.sleep(1)

def on_key_press(key):
    """键盘监听（新增刷新缓存）"""
    try:
        current_pressed_keys.add(key)
        
        # 1. F12换壁纸
        if key == HOTKEY_CHANGE and not is_setting_wallpaper:
            random_change_wallpaper()
        
        # 2. Ctrl+H隐藏/显示窗口
        if HOTKEY_HIDE_SHOW.issubset(current_pressed_keys):
            toggle_console_window()
            current_pressed_keys.clear()
        
        # 3. Ctrl+R刷新缓存
        if HOTKEY_REFRESH.issubset(current_pressed_keys):
            refresh_image_cache()
            current_pressed_keys.clear()
    except Exception as e:
        if not is_window_hidden:
            print(f"热键检测出错：{e}")

def on_key_release(key):
    """清理已释放的按键"""
    try:
        if key in current_pressed_keys:
            current_pressed_keys.remove(key)
    except:
        pass

def main():
    # 初始化
    init_dpi_awareness()
    get_console_hwnd()
    refresh_image_cache()  # 启动时加载初始缓存
    
    # 启动自动换壁纸线程
    auto_thread = threading.Thread(target=auto_change_wallpaper_loop, daemon=True)
    auto_thread.start()
    
    # 启动键盘监听
    keyboard_listener = keyboard.Listener(
        on_press=on_key_press,
        on_release=on_key_release
    )
    keyboard_listener.start()
    
    # 程序提示
    print("="*70)
    print("🎯 壁纸更换程序已启动（缓存+刷新版）")
    print(f"📁 壁纸文件夹：{WALLPAPER_FOLDER}")
    print(f"⏱️  自动更换间隔：{AUTO_CHANGE_INTERVAL}秒")
    print("⌨️  F12 → 换壁纸 | F10 → 隐藏/显示窗口 | F9 → 刷新壁纸缓存")
    print("💡 新增/删除壁纸后，按F9即可刷新缓存，无需重启程序")
    print("💡 按 Ctrl+C 退出程序（显示窗口时生效）")
    print("="*70)
    
    # 保持主线程运行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        if is_window_hidden:
            ctypes.windll.user32.ShowWindow(hwnd, 9)
        print("\n🔌 正在退出程序...")
        auto_change_running = False
        keyboard_listener.stop()
        auto_thread.join(timeout=2)
        print("✅ 程序已正常退出")

if __name__ == "__main__":
    # 依赖检查
    try:
        import pynput
    except ImportError:
        print("❌ 缺少依赖pynput，请执行：pip install pynput")
        os.system("pause")
    else:
        main()