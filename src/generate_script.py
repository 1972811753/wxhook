"""
根据 onebot/script.js 模板和 wechat_version/4_1_7_31_mac.json 偏移配置，
生成适配当前微信版本的 frida hook 脚本。
"""
import json
import re
import os

REPO_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "weixin-macos")
TEMPLATE_FILE = os.path.join(REPO_DIR, "onebot", "script.js")
CONFIG_FILE = os.path.join(REPO_DIR, "wechat_version", "4_1_7_31_mac.json")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "hook_4_1_7_31.js")


def main():
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)

    with open(TEMPLATE_FILE, "r") as f:
        template = f.read()

    # Go text/template 的 {{.key}} 替换
    def replace_placeholder(match):
        key = match.group(1)
        if key in config:
            return str(config[key]).strip()
        else:
            print(f"WARNING: key '{key}' not found in config, leaving as-is")
            return match.group(0)

    script = re.sub(r"\{\{\.(\w+)\}\}", replace_placeholder, template)

    with open(OUTPUT_FILE, "w") as f:
        f.write(script)

    print(f"Generated: {OUTPUT_FILE}")
    print(f"Offsets used from: {CONFIG_FILE}")

    # 验证没有残留的模板占位符
    remaining = re.findall(r"\{\{\.(\w+)\}\}", script)
    if remaining:
        print(f"WARNING: unresolved placeholders: {remaining}")
    else:
        print("All placeholders resolved successfully.")


if __name__ == "__main__":
    main()
