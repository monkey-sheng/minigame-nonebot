from nonebot.typing import T_State
from nonebot.adapters.cqhttp import Bot, MessageSegment, Message, MessageEvent
from nonebot import on_regex
from random import random, choice
import re
from enum import Enum


class Situation(Enum):
    ONE_EACH = 1
    ALL_TIES = 2
    INITIATOR_LEAD = 3
    OPPONENT_LEAD = 4


pokemon = on_regex(r'^\[CQ:at.+?\] *对战 *\[CQ:at')

@pokemon.handle()
async def game_result_received(bot: Bot, event: MessageEvent, state: T_State):
    # the message should be from bai gu gu, the first at message should be the game initiator
    msg: Message = event.get_message()
    # at_msg1: MessageSegment = msg[0]
    # at_msg2: MessageSegment = msg[1]
    print(len(msg))
    for seg in msg:
        print(seg.type, seg)
    at_msgs = list(filter(lambda seg: seg.type == 'at', msg))
    print('all at msgs', at_msgs)
    at_msg1: MessageSegment = at_msgs[0]
    at_msg2: MessageSegment = at_msgs[1]
    initiator_qq: str = at_msg1.data['qq']
    opponent_qq: str = at_msg2.data['qq']
    # get the number of wins and losses
    pattern = re.compile(r' *[平胜负] *[平胜负] *[平胜负] *[平胜负] *[平胜负] *[平胜负] *')
    results: list = pattern.findall(str(msg))  # there should always be a find from bai gu gu message
    # may be this wasn't from bai gu gu, just a similar message
    if len(results) == 0:
        return
    result = results[0]
    wins, losses, ties = result.count('胜'), result.count('负'), result.count('平')

    if opponent_qq == '2969660651':  # bot itself
        await pokemon.finish(choice(['好疼', '别打我求求辣', '你怎么不打白咕咕呢']))
    elif initiator_qq == '2969660651':  # should not happen
        print('should not happen bot actively fought someone')
        await pokemon.finish('✌')
    elif wins == losses:
        response = choice(['有来有回', '战况焦灼']) + '  我也来试试'
        fight_against = 'initiator' if random() > 0.5 else 'opponent'
        state['situation'] = Situation.ONE_EACH
        state['fighting'] = fight_against
        state['qq'] = initiator_qq if fight_against == 'initiator' else opponent_qq  # randomly choose one to fight against
        await pokemon.send(response)
    elif ties == 6:
        response = choice(['好平', '弄肺C肝', '这么平有考虑过建机场嘛']) + '我来打破僵局'
        fight_against = 'initiator' if random() > 0.5 else 'opponent'
        state['situation'] = Situation.ALL_TIES
        state['fighting'] = fight_against
        state['qq'] = initiator_qq if fight_against == 'initiator' else opponent_qq  # randomly choose one to fight against
        await pokemon.send(response)
    elif 1 <= wins - losses <= 2 or losses - wins <= 2:  # minor lead for either
        fight_against = 'initiator' if random() > 0.5 else 'opponent'
        state['situation'] = Situation.INITIATOR_LEAD if wins > losses else Situation.OPPONENT_LEAD
        state['fighting'] = fight_against
        state['qq'] = initiator_qq if fight_against == 'initiator' else opponent_qq
        if (fight_against == 'initiator' and wins > losses) or (fight_against == 'opponent' and wins < losses):
            response = choice(['路见不平拔刀相助', '我不服', '强', '那你能赢我吗'])
            await pokemon.send(response)
        else:
            response = choice(['我来落井下石了', '我也来提款', '挑个软柿子捏捏'])
            await pokemon.send(response)
    elif 3 <= wins - losses <= 4 or 3 <= losses - wins <= 4:  # major lead for either
        response = choice(['离谱', '太狠了', '真牛蛙', '挫挫你的锐气'])
        fight_against = 'initiator' if wins > losses else 'opponent'
        state['situation'] = Situation.INITIATOR_LEAD if wins > losses else Situation.OPPONENT_LEAD
        state['fighting'] = fight_against
        state['qq'] = initiator_qq if fight_against == 'initiator' else opponent_qq
        await pokemon.send(response)
    elif 5 <= wins - losses or losses - wins >= 5:
        response = choice(['这是什么概率', '害怕'])
        fight_against = 'initiator' if wins > losses else 'opponent'
        state['situation'] = Situation.INITIATOR_LEAD if wins > losses else Situation.OPPONENT_LEAD
        state['fighting'] = fight_against
        state['qq'] = initiator_qq if fight_against == 'initiator' else opponent_qq
        await pokemon.send(response)

    fight_message = MessageSegment.at(state['qq']) + MessageSegment.text('对战')
    await pokemon.send(fight_message)


@pokemon.receive()
async def got_result(bot: Bot, event: MessageEvent, state: T_State):
    """
    This is supposed to handle the result from bai gu gu of the previous fight
    However, bai gu gu might send something else before actually sending the result, in that case, ignore and do nothing
    """
    msg: Message = event.get_message()
    pattern = re.compile(r' *[平胜负] *[平胜负] *[平胜负] *[平胜负] *[平胜负] *[平胜负] *')
    results: list = pattern.findall(str(msg))  # there should always be a find
    if len(results) == 0:
        return
    result = results[0]
    wins, losses, ties = result.count('胜'), result.count('负'), result.count('平')

    if ties == 6:
        if state['situation'] == Situation.ALL_TIES:
            await pokemon.finish('离大谱，这合理吗')
        else:
            await pokemon.finish(choice(['就这样吧', '好平', '不亏不亏']))
    elif wins == losses:
        await pokemon.finish(choice(['什么嘛，我打的还是蛮平的嘛', '还是立于不败之地', '还行吧']))
    elif 1 <= wins - losses <= 2:  # minor win
        fight_against = state['fighting']
        prev_situation = state['situation']
        # won against the winning side
        if (fight_against == 'initiator' and prev_situation == Situation.INITIATOR_LEAD) or\
                (fight_against == 'opponent' and prev_situation == Situation.OPPONENT_LEAD):
            await pokemon.finish(choice(['干就完事了', '还好我技高一筹', '小胜小胜']))
        else:  # won against losing side
            await pokemon.finish(choice(['提款成功', '好耶', '舒服']))
    elif 1 <= losses - wins <= 2:  # minor loss
        fight_against = state['fighting']
        prev_situation = state['situation']
        # lost against the winning side
        if (fight_against == 'initiator' and prev_situation == Situation.INITIATOR_LEAD) or \
                (fight_against == 'opponent' and prev_situation == Situation.OPPONENT_LEAD):
            await pokemon.finish(choice(['尬住了', '可惜可惜', '你可能小赚，但我永远不亏', '呜呜爬了']))
        else: # lost against losing side
            await pokemon.finish(choice(['那没事了', '溜了', '呜呜送财了']))
    elif 3 <= wins - losses <= 4:  # major win
        fight_against = state['fighting']
        prev_situation = state['situation']
        # won against the winning side
        if (fight_against == 'initiator' and prev_situation == Situation.INITIATOR_LEAD) or \
                (fight_against == 'opponent' and prev_situation == Situation.OPPONENT_LEAD):
            await pokemon.finish(choice(['硬刚就完事了', '芜湖起飞', '爽到了', '谢谢你，白咕咕']))
        else:  # won against losing side
            await pokemon.finish(choice(['提大款', '有点不好意思呢', '找到一个送财童子']))
    elif 3 <= losses - wins <= 4:  # major loss
        fight_against = state['fighting']
        prev_situation = state['situation']
        # lost against the winning side
        if (fight_against == 'initiator' and prev_situation == Situation.INITIATOR_LEAD) or \
                (fight_against == 'opponent' and prev_situation == Situation.OPPONENT_LEAD):
            await pokemon.finish(choice(['寄！', '我爬了', '白咕咕你是不是故意搞我啊', '我起了，一枪秒了，有什么好说的']))
        else:  # lost against losing side
            await pokemon.finish(choice(['那没事了', '溜了', '送财童子就是我啊，那没事了']))
    elif 5 <= wins - losses:  # super win
        await pokemon.finish(choice(['逆天', '害怕', '什么情况']))
    elif losses - wins >= 5:
        await pokemon.finish(choice(['淦', '我杀我自己', '白咕咕暗箱操作我是吧']))
