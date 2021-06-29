from nonebot.rule import to_me
from nonebot.typing import T_State
from nonebot.adapters.cqhttp import Bot, Event, MessageSegment, Message, MessageEvent
from nonebot import on_regex, on_message

# PROBLEM: if @bot, the CQ at will be stripped therefore unable to match (as a result of get_message())
# WHAT I CAN DO IS: copy over the on_regex impl and fix the part where get_message() is used
# i.e. use Message(event.raw_message) to put together the original message
game_init = on_regex(r'^\[CQ:at.+?\] *打牌')


@game_init.handle()
async def receive(bot: Bot, event: MessageEvent, state: T_State):
    msg: Message = event.get_message()
    usr = event.get_user_id()
    print("msg: ", event.raw_message)
    msg = Message(event.raw_message)
    print("length of msg: ", len(msg))
    print(type(msg[0]), msg[0])
    at_msg: MessageSegment = msg[0]
    await game_init.send(at_msg.type + at_msg.data['qq'])
    if 'test' not in state:
        state['test'] = 'test'
        print('test added to state dict')
        await game_init.reject(MessageSegment.at(usr) + MessageSegment.text('first time received'))
    else:
        print('test already present in state dict')
        await game_init.send('first handle func finished')


@game_init.handle()
async def second_func(bot: Bot, event: Event, state: T_State):
    print('second func has previous stored value "test"', 'test' in state)
    await game_init.send('send another message to continue testing')


@game_init.receive()
async def third_func(bot: Bot, event: Event, state: T_State):
    print('third func has previous stored value "test"', 'test' in state)
    msg = event.get_message()
    await game_init.send(msg)
    await game_init.finish('finishing testing')
    print('this should not appear')
    await game_init.send('this should not appear')


# get_message() will strip the @bot CQ part in message (maybe for is_tome() purposes)
# however, event.raw_message still has everything and `Message(event.raw_message)` puts everything back
# simple_msg = on_message()
# @simple_msg.handle()
# async def receive_msg(bot: Bot, event: MessageEvent, state: T_State):
#     msg = event.get_message()
#     print(msg)
#     await simple_msg.finish(event.get_message())