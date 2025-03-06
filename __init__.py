import asyncio, aiohttp
from nonebot import on_command, on_notice
from typing import Union, List, Tuple, Dict
from nonebot.permission import SUPERUSER
from nonebot.params import Depends, CommandArg, Matcher
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, NoticeEvent, MessageSegment, Message
from nonebot.adapters.onebot.v11.permission import GROUP, GROUP_ADMIN, GROUP_OWNER

poker = on_command("卡牌对决", aliases={'接受',}, permission=GROUP)
hand_out = on_command("出牌", permission=GROUP)
reset_game = on_command("重置对决", permission=SUPERUSER|GROUP_ADMIN|GROUP_OWNER)
reaction = on_notice()


async def send_post_request(data: dict, url: str = 'http://127.0.0.1:8000/poker'):
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data) as response:
            if response.status == 200:
                result = await response.json()
                return result


async def send_message(bot: Bot, event: GroupMessageEvent, matcher : Matcher, msgs: List[str], uin: int):
    for msg in msgs[:-1]:
        await matcher.send(msg)
    if uin: msg_id = await matcher.send(MessageSegment.at(uin) + msgs[-1])
    else: msg_id = await matcher.send(msgs[-1])
    if msgs[-1].endswith('再来一局') or msgs[-1].endswith('(1分钟后自动超时)'):
        await asyncio.sleep(0.5)
        await bot.set_group_reaction(group_id = event.group_id, message_id = msg_id['message_id'], 
                                     code = '424', is_add = True)
    elif msgs[-1].endswith('1/2/3'):
        await asyncio.sleep(0.5)
        for i in ['123', '79', '124']:
            await asyncio.sleep(0.5)
            await bot.set_group_reaction(group_id = event.group_id, message_id = msg_id['message_id'], 
                                         code = i, is_add = True)


@poker.handle()
async def _(bot: Bot, event: GroupMessageEvent, matcher : Matcher):
    '发起对决'
    data = {
        'group': str(event.group_id),
        'uin': event.user_id,
        'name': event.sender.nickname,
        'pick': 0,
    }
    result = await send_post_request(data)
    msgs = result['msgs']
    uin = result['uin'] if 'uin' in result else 0
    await send_message(bot, event, matcher, msgs, uin)


@hand_out.handle()
async def _(bot: Bot, event: GroupMessageEvent, matcher : Matcher, args: Message = CommandArg()):
    '出牌判定'
    data = {
        'group': str(event.group_id),
        'uin': event.user_id,
        'name': event.sender.nickname,
        'pick': int(args.extract_plain_text().strip())
    }
    result = await send_post_request(data)
    msgs = result['msgs']
    uin = result['uin'] if 'uin' in result else 0
    await send_message(bot, event, matcher, msgs, uin)


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
    if histry_event['message'][-1]['type'] == 'text': msg = str(histry_event['message'][-1]['data']['text'])
    else: return
    data = {
        'group': str(group_id),
        'uin': user_id,
        'name': nickname,
        'pick': 0
    }
    if msg.endswith('出牌 1/2/3'):
        match notice_event['code']:
                case '123':
                    choice = 1
                case '79':
                    choice = 2
                case '124':
                    choice = 3
        data['pick'] = choice
        result = await send_post_request(data)
        msgs = result['msgs']
        uin = result['uin'] if 'uin' in result else 0
        if len(msgs) <= 1: return
        await send_message(bot, event, matcher, msgs, uin)
    if msg.endswith('再来一局') or msg.endswith('(1分钟后自动超时)'):
        if notice_event['code'] == '424':
            result = await send_post_request(data)
            msgs = result['msgs']
            uin = result['uin'] if 'uin' in result else 0
            if msgs[0] == '有人正在对决呢，等会再来吧~': return
            await send_message(bot, event, matcher, msgs, uin)


@reset_game.handle()
async def _(bot: Bot, event: GroupMessageEvent, matcher : Matcher):
    data = {
        'group': str(event.group_id),
        'uin': event.user_id,
        'name': event.sender.nickname,
        'pick': -1
    }
    result = await send_post_request(data)
    msg_id = await matcher.send(result['msgs'][-1])
    if result['msgs'][-1] == '你无权操作，请稍后再试': return
    await asyncio.sleep(0.5)
    await bot.set_group_reaction(group_id = event.group_id, message_id = msg_id['message_id'], 
                                 code = '424', is_add = True)