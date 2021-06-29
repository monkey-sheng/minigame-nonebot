from nonebot.rule import to_me
from nonebot.typing import T_State
from nonebot.adapters.cqhttp import Bot, Event, MessageSegment, Message, MessageEvent
from nonebot import on_regex, on_message
from .blackjack import Blackjack, GameMessage

DEFAULT_BET = 100

game = on_regex(r'^\[CQ:at.+?\] *打牌')


def handle_message(msg: GameMessage):
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
async def receive(bot: Bot, event: MessageEvent, state: T_State):
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
    handle_message(message)


@game.receive()
async def game_loop(bot: Bot, event: MessageEvent, state: T_State):
    """
    This is using receive(), so should be getting a new player input following game start
    And this will be the MAIN GAME LOOP
    """

    player_input = str(event.get_message())
    game_obj: Blackjack = state['game']
    message = game_obj.receive_input(player_input)
    handle_message(message)
