import asyncio
from nonebot import on_command, on_notice, get_driver
from nonebot.permission import SUPERUSER
from nonebot.message import run_preprocessor
from nonebot.plugin import PluginMetadata
from nonebot.params import Depends, CommandArg, Matcher
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, NoticeEvent, MessageSegment, Message
from nonebot.adapters.onebot.v11.permission import GROUP, GROUP_ADMIN, GROUP_OWNER
from .utils import *


__plugin_meta__ = PluginMetadata(
    name="扑克对决",
    description="参考小游戏合集重写的扑克对决，大部分操作支持“按钮”，规则请看https://github.com/MoonofBridge24/nonebot_plugin_poker",
    usage="扑克对决/卡牌对决/接受：发起或接受对决\n重置对决：允许参与者或者群管重置本群对决\n出牌 1/2/3：出牌命令，当按钮失效的时候可以使用命令",
    type="application",
    homepage="https://github.com/MoonofBridge24/nonebot_plugin_poker",
    supported_adapters={"nonebot.adapters.onebot.v11"},
)


poker = on_command("卡牌对决", aliases={"接受","扑克对决"}, permission=GROUP)
hand_out = on_command("出牌", permission=GROUP)
reset_game = on_command("重置对决", permission=GROUP)
reaction = on_notice()


async def reset(group: int = 0):
    '数据初始化'
    global poker_state
    if not group: poker_state = {}
    else: poker_state[group] = {
        'time': int(time.time()),
        'player1': {
            'uin': 0,
            'name': '',
            'HP': 20.0,
            'ATK': 0,
            'DEF': 0.0,
            'SP': 10,
            'suck': 0,
            'hand': []
        },
        'player2': {
            'uin': 0,
            'name': '',
            'HP': 20.0,
            'ATK': 0,
            'DEF': 5.0,
            'SP': 10,
            'suck': 0,
            'hand': []
        },
        'deck': [],
        'winer': ''
    }


driver = get_driver()
@driver.on_startup
async def on_startup_():
    await reset()


@run_preprocessor
async def _(event: GroupMessageEvent):
    now_time = event.time
    keys = [key for key in poker_state.keys() if (now_time - poker_state[key]['time'] > 90)]
    for key in keys:
        del poker_state[key]


@poker.handle()
async def _(bot: Bot, event: GroupMessageEvent, matcher : Matcher):
    '发起对决'
    group_id = event.group_id
    if not group_id in poker_state: await reset(group_id)
    state = poker_state[group_id]
    if state['player1']['hand']: await poker.finish('有人正在对决呢，等会再来吧~')
    nickname = event.sender.card or event.sender.nickname
    state['time'] = event.time
    await start_game(bot, matcher, group_id, event.user_id, nickname, state)


@hand_out.handle()
async def _(bot: Bot, event: GroupMessageEvent, matcher : Matcher, args: Message = CommandArg()):
    '出牌判定'
    group_id = event.group_id
    user_id = event.user_id
    choice = int(args.extract_plain_text().strip())
    if not group_id in poker_state: await reset(group_id)
    state = poker_state[group_id]
    if not state['player1']['hand']:
        await hand_out.finish('对决还没开始呢，发起一轮新对决吧~')
    if state['player1']['uin'] != user_id:
        await hand_out.finish('没牌的瞎出干什么')
    if not choice or not (choice in range(1, len(state['player1']['hand'])+1)):
        await hand_out.finish('请正确输入出牌序号')
    state['time'] = event.time
    await process_hand_out(bot, matcher, group_id, choice, state)


@reaction.handle()
async def _(bot: Bot, event: NoticeEvent, matcher : Matcher):
    '表情回应处理'
    notice_event = event.dict()
    if notice_event['notice_type'] != 'reaction' or notice_event['sub_type'] != 'add' or notice_event['operator_id'] == notice_event['self_id']: return
    group_id = notice_event['group_id']
    user_id = notice_event['operator_id']
    user_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
    nickname = user_info['card'] or user_info['nickname']
    histry_event = await bot.get_msg(message_id=notice_event['message_id'])
    if histry_event['sender']['user_id'] != event.self_id: return
    if histry_event['message'][-1]['type'] == 'text': msg = histry_event['message'][-1]['data']['text']
    else: return
    if not group_id in poker_state: await reset(group_id)
    state = poker_state[group_id]
    if msg.endswith('出牌 1/2/3'):
        match notice_event['code']:
                case '123':
                    choice = 1
                case '79':
                    choice = 2
                case '124':
                    choice = 3
        if not state['player1']['hand']: return
        if state['player1']['uin'] != user_id: return
        if not choice or not (choice in range(1, len(state['player1']['hand'])+1)): return
        state['time'] = event.time
        await process_hand_out(bot, matcher, group_id, choice, state)
    if msg.endswith('再来一局') or msg.endswith('(1分钟后自动超时)'):
        if notice_event['code'] == '424':
            if state['player1']['hand']: return
            state['time'] = event.time
            await start_game(bot, matcher, group_id, user_id, nickname, state)


async def start_game(bot: Bot, matcher : Matcher, group_id: int, user_id: int, nickname: str, state: PokerState):
    if not state['player1']['uin']:
        state['player1']['uin'] = user_id
        state['player1']['name'] = nickname
        msg_id = await matcher.send(f'{nickname} 发起了一场对决，正在等待群友接受对决...\n(1分钟后自动超时)')
        await asyncio.sleep(0.5)
        await bot.set_group_reaction(group_id = group_id, message_id = msg_id['message_id'], 
                                     code = '424', is_add = True)
        return
    state['player2']['name'] = nickname
    if state['player1']['uin'] == user_id: state['player2']['name'] = 'BOT'
    else: state['player2']['uin'] = user_id
    if random.randint(0, 1): state['player1']['name'], state['player2']['name'], state['player1']['uin'], state['player2']['uin'] = state['player2']['name'], state['player1']['name'], state['player2']['uin'], state['player1']['uin']
    await matcher.send('唰唰唰 正在洗牌...')
    await asyncio.sleep(0.5)
    msg = await info_show(state)
    if not state['player1']['uin']:
        pick = random.randint(1, len(state['player1']['hand']))
        await matcher.send(msg)
        await process_hand_out(bot, matcher, group_id, pick, state)
    msg_id = await matcher.send(MessageSegment.at(state['player1']['uin']) + msg)
    await asyncio.sleep(0.5)
    for i in ['123', '79', '124']:
        await asyncio.sleep(0.5)
        await bot.set_group_reaction(group_id = group_id, message_id = msg_id['message_id'], 
                                     code = i, is_add = True)


async def process_hand_out(bot: Bot, matcher : Matcher, group_id: int, choice: int, state: PokerState):
    msgs = await play_poker(state, choice - 1)
    msg = await info_show(state)
    while not state['player1']['uin'] and not state['winer']:
        msgs.append(msg)
        pick = random.randint(1, len(state['player1']['hand']))
        msgs += await play_poker(state, pick - 1)
        msg = await info_show(state)
    for i in msgs: await matcher.send(i)
    if state['winer']:
        await reset(group_id)
        msg_id = await matcher.send(msg)
        await asyncio.sleep(0.5)
        await bot.set_group_reaction(group_id = group_id, message_id = msg_id['message_id'], 
                                     code = '424', is_add = True)
        await matcher.finish()
    else:
        msg_id = await matcher.send(MessageSegment.at(state['player1']['uin']) + msg)
        await asyncio.sleep(0.5)
        for i in ['123', '79', '124']:
            await asyncio.sleep(0.5)
            await bot.set_group_reaction(group_id = group_id, message_id = msg_id['message_id'], 
                                         code = i, is_add = True)
        await matcher.finish()


@reset_game.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    if not group_id in poker_state: await reset(group_id)
    state = poker_state[group_id]
    if event.sender.role != 'admin' and not event.user_id in [state['player1']['uin'], state['player2']['uin']]:
        await reset_game.finish('你无权操作，请稍后再试')
    await reset(group_id)
    msg_id = await reset_game.send('重置成功，点击按钮再来一局')
    await asyncio.sleep(0.5)
    await bot.set_group_reaction(group_id = group_id, message_id = msg_id['message_id'], 
                                 code = '424', is_add = True)

