import os
import random
import ctypes
import time
import threading
from pynput import keyboard
from PIL import Image  # 用于图片混合

# ===================== 配置项 =====================
WALLPAPER_FOLDER = r"F:\桌面美化\壁纸"
SUPPORTED_FORMATS = ('.jpg', '.jpeg', '.png', '.bmp')
AUTO_CHANGE_INTERVAL = 30  # 自动换壁纸间隔（秒）
HOTKEY_CHANGE = keyboard.Key.f12  # F12换壁纸
HOTKEY_HIDE_SHOW = {keyboard.Key.f10} # F10隐藏/显示窗口
HOTKEY_REFRESH = {keyboard.Key.f9} # F9刷新缓存
# 淡入淡出效果配置
FADE_STEPS = 3  # 过渡步数（越大越平滑）
FADE_INTERVAL = 0.03  # 每步间隔（秒），总时长=STEPS*INTERVAL
# ==================================================

# 全局状态变量
image_cache = []  # 壁纸缓存
is_setting_wallpaper = False  # 壁纸切换锁（轻量级）
auto_change_running = True
current_pressed_keys = set()
# 窗口控制相关
hwnd = None
is_window_hidden = False
# 记录当前壁纸路径（用于淡入淡出）
current_wallpaper_path = ""

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
    """基础设置壁纸函数"""
    try:
        ctypes.windll.user32.SystemParametersInfoW(
            20, 0, os.path.abspath(image_path), 3
        )
        global current_wallpaper_path
        current_wallpaper_path = image_path  # 更新当前壁纸路径
    except Exception as e:
        if not is_window_hidden:
            print(f"❌ 设置壁纸失败：{e}")

def fade_transition(new_img_path):
    """淡入淡出切换壁纸（核心函数，优化锁逻辑）"""
    global is_setting_wallpaper
    if is_setting_wallpaper or not new_img_path:
        return
    
    is_setting_wallpaper = True  # 加锁
    temp_dir = os.path.dirname(os.path.abspath(__file__))  # 脚本所在目录（有权限）
    temp_file = os.path.join(temp_dir, "temp_wallpaper_fade.png")
    
    try:
        # 第一次换壁纸直接设置（无过渡）
        if not current_wallpaper_path:
            set_wallpaper(new_img_path)
            if not is_window_hidden:
                print(f"🖼️ 已更换壁纸：{os.path.basename(new_img_path)}")
            return
        
        # 加载并统一图片尺寸
        old_img = Image.open(current_wallpaper_path).convert("RGBA")
        new_img = Image.open(new_img_path).convert("RGBA")
        new_img = new_img.resize(old_img.size, Image.Resampling.LANCZOS)
        
        # 淡入淡出核心逻辑
        for alpha in range(0, 256, max(1, int(255/FADE_STEPS))):
            if not is_setting_wallpaper:
                break
            blended = Image.blend(old_img, new_img, alpha/255)
            blended.save(temp_file)
            set_wallpaper(temp_file)
            time.sleep(FADE_INTERVAL)
        
        # 最终设置新壁纸
        set_wallpaper(new_img_path)
        if not is_window_hidden:
            print(f"🖼️ 已更换壁纸（淡入淡出）：{os.path.basename(new_img_path)}")
    
    except Exception as e:
        if not is_window_hidden:
            print(f"❌ 淡入淡出效果失败：{e}")
            set_wallpaper(new_img_path)  # 降级更换
    finally:
        # 清理临时文件+释放锁（关键！）
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass
        is_setting_wallpaper = False  # 必须释放锁

def random_change_wallpaper():
    """随机换壁纸（优化缓存检查）"""
    if not image_cache:
        if not is_window_hidden:
            print("⚠️ 壁纸缓存为空，自动刷新缓存...")
        refresh_image_cache()
        time.sleep(0.5)  # 延长缓存加载时间，避免空列表
        if not image_cache:
            if not is_window_hidden:
                print("⚠️ 刷新后仍无壁纸，请检查文件夹")
            return
    
    # 避免重复选到当前壁纸
    candidate_imgs = [img for img in image_cache if img != current_wallpaper_path]
    if not candidate_imgs:
        candidate_imgs = image_cache  # 只剩1张时直接用
    
    random_img = random.choice(candidate_imgs)
    threading.Thread(target=fade_transition, args=(random_img,), daemon=True).start()

def auto_change_wallpaper_loop():
    """自动换壁纸循环（无改动）"""
    global auto_change_running
    while auto_change_running:
        random_change_wallpaper()
        for _ in range(AUTO_CHANGE_INTERVAL):
            if not auto_change_running:
                break
            time.sleep(1)

def on_key_press(key):
    """键盘监听（核心修复：拆分单个按键和组合键逻辑）"""
    try:
        current_pressed_keys.add(key)
        
        # 1. 单个按键：F12 换壁纸（独立判断，优先级最高）
        if key == HOTKEY_CHANGE:
            if not is_setting_wallpaper:  # 仅当未切换时响应
                random_change_wallpaper()
            else:
                if not is_window_hidden:
                    print("⚠️ 正在切换壁纸，请稍等...")
        
        # 2. 组合键：F10 隐藏/显示窗口（集合判断）
        if HOTKEY_HIDE_SHOW.issubset(current_pressed_keys):
            toggle_console_window()
            current_pressed_keys.clear()  # 清空避免重复触发
        
        # 3. 组合键：F9 刷新缓存
        if HOTKEY_REFRESH.issubset(current_pressed_keys):
            refresh_image_cache()
            current_pressed_keys.clear()
    
    except Exception as e:
        if not is_window_hidden:
            print(f"热键检测出错：{e}")

def on_key_release(key):
    """清理已释放的按键（无改动）"""
    try:
        if key in current_pressed_keys:
            current_pressed_keys.remove(key)
    except:
        pass

def main():
    """主函数（优化初始化）"""
    init_dpi_awareness()
    get_console_hwnd()
    refresh_image_cache()  # 启动加载缓存
    
    # 启动自动换壁纸线程
    auto_thread = threading.Thread(target=auto_change_wallpaper_loop, daemon=True)
    auto_thread.start()
    
    # 启动键盘监听（确保监听线程正常运行）
    keyboard_listener = keyboard.Listener(
        on_press=on_key_press,
        on_release=on_key_release
    )
    keyboard_listener.start()
    
    # 程序提示
    print("="*70)
    print("🎯 壁纸更换程序已启动（修复F12响应版）")
    print(f"📁 壁纸文件夹：{WALLPAPER_FOLDER}")
    print(f"⏱️  自动更换间隔：{AUTO_CHANGE_INTERVAL}秒")
    print(f"🎨 淡入淡出时长：{FADE_STEPS * FADE_INTERVAL:.2f}秒")
    print("⌨️  F12 → 换壁纸 | F10 → 隐藏/显示窗口 | F9 → 刷新缓存")
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
        is_setting_wallpaper = False  # 强制释放锁
        keyboard_listener.stop()
        auto_thread.join(timeout=2)
        # 清理临时文件
        temp_dir = os.path.dirname(os.path.abspath(__file__))
        temp_file = os.path.join(temp_dir, "temp_wallpaper_fade.png")
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass
        print("✅ 程序已正常退出")

if __name__ == "__main__":
    # 依赖检查
    try:
        import pynput
        from PIL import Image
    except ImportError as e:
        missing_lib = "pynput" if "pynput" in str(e) else "Pillow"
        print(f"❌ 缺少依赖{missing_lib}，请执行：pip install {missing_lib}")
        os.system("pause")
    else:
        main()