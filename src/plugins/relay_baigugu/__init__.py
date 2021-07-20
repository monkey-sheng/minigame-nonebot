from nonebot.rule import to_me, Rule
from nonebot.typing import T_State
from nonebot.adapters.cqhttp import Bot, Event, MessageSegment, Message, MessageEvent
from nonebot import on_regex, on_message

DEST_GROUP = 829619725
# DEST_GROUP = 173634948
SENDER = '771114514'
# SENDER = '1092997224'


def is_from_baigugu() -> Rule:
    async def _baigugu(bot: Bot, event: Event, state: T_State) -> bool:
        print('sender id:', event.get_user_id())
        return event.get_user_id() == SENDER
    return Rule(_baigugu)


relay = on_message(rule=is_from_baigugu())

@relay.handle()
async def receive(bot: Bot, event: MessageEvent, state: T_State):
    # print('user id and session id:', event.get_user_id(), event.get_session_id())
    messages = event.get_message()

    # await relay.finish(MessageSegment.image('78aade898696c0535c0301123fa8f2e9.image'))
    await bot.send_group_msg(group_id=DEST_GROUP, message='收到白咕咕的消息')
    await bot.send_group_msg(group_id=DEST_GROUP, message=messages)