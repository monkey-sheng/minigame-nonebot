from typing import List
from nonebot.rule import to_me, Rule
from nonebot.typing import T_State
from nonebot.adapters.cqhttp import Bot, Event, MessageSegment, Message, MessageEvent
from nonebot import on_regex
from .BilibiliClient import BilibiliClient
import re
import json

# check against this list so that not anyone can use send dynamic
ALLOWED_USERS_QQ = ['1092997224', '1330992777']  # me and malivergos
FP = open('bilibili.txt', 'r')
INFOS = json.load(FP)
COOKIES = INFOS['data']['cookie_info']['cookies']
try:
    ACCESS_TOKEN = INFOS['data']['token_info']['access_token']
    REFRESH_TOKEN = INFOS['data']['token_info']['refresh_token']
except:
    ACCESS_TOKEN, REFRESH_TOKEN = None, None
FP.close()


def is_qualified_user() -> Rule:
    async def _qualified(bot: Bot, event: Event, state: T_State):
        return event.get_user_id() in ALLOWED_USERS_QQ
    return Rule(_qualified)


# load user name and password from file
# lines = open('bilibili.txt', 'r').readlines()
# USER_NAME, PASSWORD = lines[0].strip(), lines[1].strip()

# CLIENT = BilibiliClient(USER_NAME, PASSWORD)
CLIENT = BilibiliClient()
for cookie in COOKIES:
    CLIENT._session.cookies.set(cookie['name'], cookie['value'], domain=".bilibili.com")
CLIENT.access_token, CLIENT.refresh_token = ACCESS_TOKEN, REFRESH_TOKEN
# CLIENT.refresh()  # refresh at launch

dynamic = on_regex('发动态', rule=to_me() & is_qualified_user())


@dynamic.handle()
async def first_receive(bot: Bot, event: MessageEvent, state: T_State):
    CLIENT.clear()  # make sure to start afresh
    # CLIENT.refresh()  # also refreshes its cookies and tokens
    await dynamic.send('接收中')


@dynamic.receive()
async def received(bot: Bot, event: MessageEvent, state: T_State):
    # sender_qq: str = event.get_user_id()
    # if sender_qq not in ALLOWED_USERS_QQ:
    #     await dynamic.finish('尚无权限发送动态')
    #     # return

    msg: Message = event.get_message()

    if re.compile('/取消').match(str(msg)):
        CLIENT.clear()
        await dynamic.finish('已取消')

    if re.compile('/发送|/结束').match(str(msg)):
        try:
            CLIENT.send_dynamic()
        except Exception as e:
            await dynamic.finish('发送时出现错误\n' + str(e))
        await dynamic.finish('发送成功')

    # get the text and images from user input message
    img_segments: List[MessageSegment] = list(filter(lambda m: m.type == 'image', msg))
    text_segments: List[MessageSegment] = list(filter(lambda m: m.type == 'text', msg))
    if len(img_segments) > 0:  # has images
        for i, img in enumerate(img_segments, 1):
            img_url = img.data['url']
            print('get img called with url:', img_url)
            if not CLIENT.get_image(img_url):
                await dynamic.send(f'无法接收第{i}张图片')
        # await dynamic.send(f'共收到{len(CLIENT.dynamic_img_list)}张图片')
        await dynamic.reject(f'共收到{len(CLIENT.dynamic_img_list)}张图片')

    if len(text_segments) > 0:  # has text, concat all text segments and append
        CLIENT.dynamic_text += '\n' + ''.join(map(str, text_segments))
        # await dynamic.send('收到一段文字')
        await dynamic.reject('收到一段文字')

    ###await dynamic.reject('继续接收中，输入 /发送 即可发布动态')


# call the login method on CLIENT
manual_login = on_regex('/登录|/登陆', rule=to_me() & is_qualified_user())


@manual_login.handle()
async def client_login(bot: Bot, event: MessageEvent, state: T_State):
    if CLIENT.login():
        await manual_login.finish('登录成功')
    else:
        await manual_login.finish('登录遇到一些意外，但不一定失败了')


manual_set_username_password = on_regex('/账号密码', rule=to_me() & is_qualified_user())


@manual_set_username_password.handle()
async def prompt_username_password(bot: Bot, event: MessageEvent, state: T_State):
    await manual_set_username_password.send('输入账号和密码，空格分隔')


@manual_set_username_password.receive()
async def set_username_password(bot: Bot, event: MessageEvent, state: T_State):
    msg = str(event.get_message()).split(' ')
    CLIENT.username, CLIENT.password = msg[0].strip(), msg[1].strip()
    await manual_set_username_password.finish('设置完毕')


manual_set_cookies = on_regex('/cookies', rule=to_me() & is_qualified_user())


@manual_set_cookies.handle()
async def prompt_set_cookies(bot: Bot, event: MessageEvent, state: T_State):
    await manual_set_cookies.send('输入cookies的值，name1=value1; name2=value2;形式')


@manual_set_cookies.receive()
async def set_cookies(bot: Bot, event: MessageEvent, state: T_State):
    cookies_msg = str(event.get_message()).split(';')
    with open('bilibili.txt', 'r') as fp:
        original_json = json.load(fp)

    original_json['data']['cookie_info']['cookies'] = []
    for cookie_str in cookies_msg:
        name_val_pair = cookie_str.strip()
        name_val_list = name_val_pair.split('=')
        cookie_name, cookie_value = name_val_list[0].strip(), name_val_list[1].strip()
        CLIENT._session.cookies.set(cookie_name, cookie_value, domain=".bilibili.com")
        original_json['data']['cookie_info']['cookies'].append({"name": cookie_name, "value": cookie_value})
    with open('bilibili.txt', 'w') as fp:
        fp.write(json.dumps(original_json))
    await manual_set_cookies.finish('cookies设置完毕')
