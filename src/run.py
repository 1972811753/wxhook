"""
微信 Hook 启动脚本
用法:
    python3 run.py                          # 附加到微信，hook 收发消息
    python3 run.py --send filehelper "你好"  # 附加后自动发一条消息测试
"""
import argparse
import json
import os
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HOOK_SCRIPT = os.path.join(SCRIPT_DIR, "hook_4_1_7_31.js")


def find_wechat_pid():
    """查找微信进程 PID"""
    try:
        result = subprocess.run(
            ["pgrep", "-x", "WeChat"],
            capture_output=True, text=True
        )
        pids = result.stdout.strip().split("\n")
        pids = [p for p in pids if p]
        if not pids:
            return None
        return int(pids[0])
    except Exception:
        return None


def check_sip():
    """检查 SIP 状态"""
    result = subprocess.run(
        ["csrutil", "status"],
        capture_output=True, text=True
    )
    return "disabled" in result.stdout.lower()


def main():
    parser = argparse.ArgumentParser(description="微信 Hook 启动脚本")
    parser.add_argument("--send", nargs=2, metavar=("RECEIVER", "CONTENT"),
                        help="附加后自动发一条消息，例: --send filehelper '你好'")
    args = parser.parse_args()

    # 1. 检查 SIP
    if not check_sip():
        print("[!] SIP 未关闭，Frida 无法附加到微信进程")
        print("    请重启进入恢复模式执行: csrutil disable")
        print("    然后重启后再运行此脚本")
        sys.exit(1)

    print("[+] SIP 已关闭")

    # 2. 检查微信是否运行
    pid = find_wechat_pid()
    if not pid:
        print("[!] 微信未运行，请先打开微信并登录")
        sys.exit(1)

    print(f"[+] 找到微信进程 PID: {pid}")

    # 3. 检查 hook 脚本
    if not os.path.exists(HOOK_SCRIPT):
        print(f"[!] Hook 脚本不存在: {HOOK_SCRIPT}")
        print("    请先运行 python3 generate_script.py 生成")
        sys.exit(1)

    # 4. 用 frida 附加
    try:
        import frida
    except ImportError:
        print("[!] frida 未安装，请执行: pip install frida frida-tools")
        sys.exit(1)

    print(f"[+] 正在附加到微信进程 (PID: {pid})...")
    try:
        session = frida.attach(pid)
    except frida.ProcessNotFoundError:
        print("[!] 无法附加到微信进程，请确认 PID 正确")
        sys.exit(1)
    except Exception as e:
        print(f"[!] 附加失败: {e}")
        if "unable to inject" in str(e).lower() or "not permitted" in str(e).lower():
            print("    可能 SIP 未完全关闭，请确认 csrutil status 显示 disabled")
        sys.exit(1)

    print("[+] 附加成功，加载 Hook 脚本...")

    with open(HOOK_SCRIPT, "r") as f:
        script_code = f.read()

    script = session.create_script(script_code)

    # 消息处理回调
    received_messages = []

    def on_message(message, data):
        if message["type"] == "send":
            payload = message.get("payload", {})
            if not isinstance(payload, dict):
                print(f"[JS] {payload}")
                return
            msg_type = payload.get("type", "")

            if msg_type == "send":
                # 收到消息
                sender = payload.get("user_id", "unknown")
                nickname = payload.get("sender", {}).get("nickname", "")
                messages = payload.get("message", [])
                content = " ".join(
                    m.get("data", {}).get("text", "")
                    for m in messages if m.get("type") == "text"
                )
                group_id = payload.get("group_id", "")
                if group_id:
                    print(f"[群消息] {group_id} | {nickname}({sender}): {content}")
                else:
                    print(f"[私聊] {nickname}({sender}): {content}")
                received_messages.append(payload)

            elif msg_type == "finish":
                print("[+] 消息发送完成")

            elif msg_type == "upload":
                self_id = payload.get("self_id", "")
                print(f"[+] 检测到微信账号: {self_id}")

            else:
                print(f"[JS payload] {payload}")

        elif message["type"] == "error":
            print(f"[!] 脚本错误: {message.get('description', '')}")
            if message.get("stack"):
                print(f"    堆栈: {message['stack']}")
        elif message["type"] == "log":
            print(f"[JS日志] {message.get('payload', '')}")

    script.on("message", on_message)
    script.load()

    print("[+] Hook 脚本已加载！")
    print("[+] 等待初始化 (3秒)...")
    time.sleep(4)  # 等待 NOP patch 完成（脚本里有 2-3 秒延迟）

    print("[+] 初始化完成！")

    # 如果指定了 --send，自动发一条消息
    if args.send:
        receiver, content = args.send
        task_id = 0x30000001
        print(f"[+] 发送消息: '{content}' -> {receiver}")

        # triggerX0 需要先被微信的一次网络调用捕获
        max_retries = 10
        for attempt in range(max_retries):
            try:
                result = script.exports_sync.trigger_send_text_message(
                    task_id, receiver, content, ""
                )
                if result == "not_ready":
                    if attempt == 0:
                        print("[*] 等待捕获 MMStartTask 的 X0 指针...")
                        print("    请在微信中手动发送一条消息（随便找个人发个\"1\"即可）")
                        print("    发送后 X0 会被自动捕获，之后就可以程序化发送了")
                    time.sleep(2)
                    continue
                print(f"[+] 发送结果: {result}")
                break
            except Exception as e:
                print(f"[!] 发送失败: {e}")
                break
        else:
            print("[!] 超时：未能捕获到微信网络请求，请手动在微信中操作后重试")

    # 保持运行，监听消息
    print("")
    print("=" * 50)
    print("  微信 Hook 已就绪")
    print("  - 收到的消息会自动打印在这里")
    print("  - 按 Ctrl+C 退出")
    print("=" * 50)
    print("")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[+] 正在断开连接...")
        script.unload()
        session.detach()
        print("[+] 已安全退出")


if __name__ == "__main__":
    main()
