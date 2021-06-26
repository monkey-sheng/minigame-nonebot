import nonebot
from nonebot.adapters.cqhttp import Bot

nonebot.init()

driver = nonebot.get_driver()
driver.register_adapter("cqhttp", Bot)  # 注册 CQHTTP 的 Adapter
nonebot.load_builtin_plugins()  # 加载 nonebot 内置插件

# 加载插件目录，该目录下为各插件，以下划线开头的插件将不会被加载
nonebot.load_plugins("src/plugins")

app = nonebot.get_asgi()

if __name__ == "__main__":
    nonebot.run()
