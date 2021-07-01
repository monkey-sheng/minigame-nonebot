from nonebot.rule import to_me
from nonebot.typing import T_State
from nonebot.adapters.cqhttp import Bot, Event, MessageSegment, Message, MessageEvent
from nonebot import on_regex, on_message
from random import randint, random
from .blackjack_game import Blackjack, GameMessage
from .database import DB

DEFAULT_BET = 100

game = on_regex(r'^\[CQ:at.+?\] *打牌')


async def handle_message(msg: GameMessage):
    """handle the message received from game accordingly"""
    if msg.bot_action == msg.BOT_SEND:
        await game.send(msg.response)
    elif msg.bot_action == msg.BOT_REJECT:
        await game.reject(msg.response)
    elif msg.bot_action == msg.BOT_FINISH:
        await game.finish(msg.response)
    elif msg.bot_action == msg.BOT_PAUSE:
        await game.pause(msg.response)
    else:
        raise RuntimeError(f'should never happen, got unexpected {msg.bot_action}')


@game.handle()
async def first_receive(bot: Bot, event: MessageEvent, state: T_State):
    """First time getting a match from qq message"""

    msg: Message = event.get_message()
    player_qq: str = event.get_user_id()

    # get the opponent's (dealer) qq
    at_msg: MessageSegment = msg[0]
    dealer_qq: str = at_msg.data['qq']  # this should not throw an error
    # can't play against oneself
    if player_qq == dealer_qq:
        await game.finish('禁止左右互搏')

    # create a new Blackjack obj for this game session
    game_obj = Blackjack(DEFAULT_BET, player_qq, dealer_qq)
    state['game'] = game_obj
    message = game_obj.game_start()
    await handle_message(message)


@game.receive()
async def game_loop(bot: Bot, event: MessageEvent, state: T_State):
    """
    This is using receive(), so should be getting a new player input following game start
    And this will be the MAIN GAME LOOP
    """

    player_input = str(event.get_message())
    game_obj: Blackjack = state['game']
    message = game_obj.receive_input(player_input)
    await handle_message(message)


help_msg = on_regex('帮助', rule=to_me())


@help_msg.handle()
async def print_help(bot: Bot, event: MessageEvent, state: T_State):
    await help_msg.finish('21点帮助：\n发送 “@某人 打牌” 即可发起对战。\n'
                          '然后根据bot提示选择行动，例如：要牌，停牌，双倍；按照基础21点规则。\n'
                          '打牌没有时间间隔限制，也没有金钱限制，甚至可以@黑咕咕 抢钱')


rob = on_regex(' *抢钱 *', rule=to_me())


@rob.handle()
async def robbed(bot: Bot, event: MessageEvent, state: T_State):
    qq = event.get_user_id()
    original_money = DB.get_money(qq)
    if original_money is None:
        await rob.finish('刚见面就抢，这合理吗')
    elif original_money > 200:
        await rob.finish('你好有钱，憋抢啦')
    if random() < 0.8:
        amount = randint(1, 5) * 100
        total = original_money + amount
        DB.set_money(qq, total)
        await rob.finish(f'你抢了黑咕咕{amount}，你的余额{total}，黑咕咕很伤心')
    else:
        amount = randint(1, 5) * 100
        total = original_money - amount
        DB.set_money(qq, total)
        await rob.finish(f'黑咕咕心情不好决定倒打一耙，抢了你{amount}，你的余额{total}，黑咕咕心满意足了')
