import random, time, re
from typing import Dict, List, Tuple, Union, Optional, TypedDict

from nonebot.rule import Rule
from nonebot.adapters.onebot.v11 import GroupMessageEvent, NoticeEvent, Bot, Event


class PlayerState(TypedDict):
    uin: int
    name: str
    HP: float
    ATK: float
    DEF: float
    SP: int
    suck: float
    hand: List[Tuple[int, int]]

class PokerState(TypedDict):
    time: int
    player1: PlayerState
    player2: PlayerState
    deck: List[Tuple[int, int]]
    winer: Optional[str]


async def msg_at(event: GroupMessageEvent) -> int:
    '获取被at的第一个qq号'
    qq = 0
    for msg in event.message:
        if msg.type == 'at':
            qq = msg.data['qq']
            break
    return qq


def rule_of_reaction(rule: str = 'keyword', args: List[str] =[], codes: List[str|int] = [], atcheck: bool = True) -> Rule:
    '''
    对reaction事件进行判断
    rule: str 可选 keyword/regex
    args: list[str] 关键词/正则表达式列表，为空时跳过rule检查
    codes: list[str] 回应代码列表，code是一个数字，为空时跳过code检查
    atcheck: bool 是否检查at，默认检查，非at对象无法触发
    '''
    async def rule_checker(event: NoticeEvent, bot: Bot) -> bool:
        if rule not in ['keyword', 'regex']: return False
        event_type = event.get_event_name()
        notice = event.dict() # 转换为字典方便读取数据
        # 判断是否为添加表情回应
        if event_type != 'notice.group_msg_emoji_like' or notice['user_id'] == notice['self_id']: return False
        strcodes = [str(code) for code in codes]
        if strcodes and notice['likes'][0]['emoji_id'] not in strcodes: return False
        histry = await bot.get_msg(message_id=notice['message_id'])
        if histry['sender']['user_id'] != event.self_id: return False # 判断是否为自己发出的消息
        if all(msg['type'] != 'text' for msg in histry['message']): return False # 判断是否存在文字消息
        for msg in histry['message']: # 检测第一条at信息是否为触发者，如果消息不带at则跳过检查
            if msg['type'] == 'at':
                if int(msg['data']['qq']) != notice['user_id'] and atcheck: return False
                break
        if not args: return True
        msg = ''.join(msg['data']['text'] for msg in histry['message'] if msg['type'] == 'text') # 提取文字消息
        msg = msg.strip()
        match rule:
            case 'keyword':
                for arg in args:
                    if arg in msg: return True
            case 'regex':
                for arg in args:
                    if re.search(arg, msg): return True
        return False
    return Rule(rule_checker)


async def random_poker(n: int = 1, range_point: tuple[int, int] = (1, 14)):
    '生成随机牌库'
    poker_deck = [(suit, point) for suit in range(1, 5) for point in range(*range_point)]
    poker_deck = poker_deck * n
    random.shuffle(poker_deck)
    return poker_deck


async def play_poker(state: PokerState, choice: int) -> List[str]:
    '出牌判定'
    msgs = []
    msg = ''
    A = state['player1']
    W = state['player2']
    deck = state['deck']
    hand = A['hand']
    suit = hand[choice][0]
    point = hand[choice][1]

    def SP(A, roll) -> str:
        'ACE技能判定'
        msg = ''
        i = 0
        hand: list = A['hand']
        while i < len(hand):
            suit = hand[i][0]
            point = hand[i][1] if hand[i][1] != 1 else roll
            '''if A['SP'] < 0 and suit != 3:
                msg += f'\n技能点已透支，后续技能牌无法打出'
                break'''
            A['SP'] -= point
            i += 1
            match suit:
                case 1:
                    W['DEF'] -= point/2
                    A['ATK'] += point/2
                    msg += f'\n♠{point}发动了盾击，造成{point/2}伤害且使对方防御降低{point/2}'
                case 2:
                    A['HP'] += point/2
                    A['suck'] += 0.50
                    msg += f'\n♥{point}发动了吸血，生命回复{point/2}且下次攻击附加吸血{(A["suck"]*100):.0f}%'
                case 3:
                    A['SP'] += point*2
                    hand.append((random.choice([1, 2, 4]), random.randint(4,8)))
                    msg += f'\n♣{point}发动了吟唱，技能点增加了{point}并额外打出一张随机技能牌'
                case 4:
                    A['ATK'] += point*1.5
                    A['HP'] -= point/2
                    msg += f'\n♦{point}发动了燃血，生命减少{point/2}且造成{point*1.5}伤害'
        return msg


    # 进攻方
    if point == 1:
        roll = random.randint(1, 6)
        suits = {1: "♠", 2: "♥", 3: "♣", 4: "♦"}
        msg += f'发动{suits[suit]}ACE技能，打出所有手牌，六面骰判定为{roll}\n-----'
        msg += SP(A, roll)
    else:
        match suit:
            case 1:
                A['DEF'] += point
                msg += f'{A["name"]}的DEF强化了{point}'
            case 2:
                A['HP'] += point
                msg += f'{A["name"]}的HP回复了{point}'
            case 3:
                A['SP'] += point
                msg += f'{A["name"]}的SP增加了{point}'
                roll = random.randint(1, 20)
                msg += f'\n二十面骰判定为{roll}，当前技能点{A["SP"]}'
                if A['SP'] < roll: msg += f'，技能发动失败...'
                else:
                    msg += f'，技能发动成功，打出剩余手牌\n-----'
                    del hand[choice]
                    msg += SP(A, 1)
            case 4:
                A['ATK'] += point
                msg += f'{A["name"]}发动了攻击{point}'
    msgs.append(msg)
    msg = ''
    

    # 防守方
    if W['SP'] < 1:
        msg += f'{W["name"]}的技能点不足...'
    else:
        roll = random.randint(1, 20)
        msg += f'二十面骰判定为{roll}，当前{W["name"]}的技能点为{W["SP"]}'
        if W['SP'] < roll or not deck: msg += f'，技能发动失败...'
        else:
            suit = deck[0][0]
            point = deck[0][1]
            W['SP'] -= point
            msg += f'，技能牌发动成功！'
            msg += '\n-----'
            state['deck'] = deck[1:]
            match suit:
                case 1:
                    W['DEF'] += point/2
                    msg += f'\n♠{point}发动了碎甲，防御提高{point/2}'
                    if A['ATK'] > W['DEF'] and A['ATK'] > 0:
                        A['DEF'] -= point
                        msg += f'，受伤时使对方防御降低{point}'
                case 2:
                    W['HP'] += point/2
                    msg += f'\n♥{point}发动了再生，生命回复{point/2}'
                    if A['ATK'] > W['DEF'] and A['ATK'] > 0:
                        W['HP'] += point
                        msg += f'，本回合受击回复{point}'
                case 3:
                    A['SP'] -= point
                    W['SP'] += point
                    msg += f'\n♣{point}发动了震慑，此卡不消耗技能点并扣除了对方技能点{point}'
                case 4:
                    W['ATK'] += point/2
                    msg += f'\n♦{point}发动了反击，造成{point/2}伤害并获得50%反伤'
            if W['SP'] < 0: W['SP'] = 0
    msgs.append(msg)
    msg = ''
    

    # 回合结算
    HP_Max = W['HP'] >= 45
    if A['ATK'] > W['DEF'] and A['ATK'] > 0:
        W['HP'] -= A['ATK'] - W['DEF'] # 伤害
        A['HP'] += A['suck']*(A['ATK'] - W['DEF']) # 吸血
        if W['ATK']: A['HP'] -= (A['ATK'] - W['DEF'])/2 # 反伤
        if W['DEF'] > 0: W['DEF'] = 0.0
    else: W['DEF'] -= A['ATK']
    if W['ATK'] > A['DEF'] and W['ATK'] > 0:
        A['HP'] -= W['ATK'] - A['DEF'] # 反击
        W['HP'] += W['suck']*(W['ATK'] - A['DEF']) # 吸血
        if A['DEF'] > 0: A['DEF'] = 0.0
    else: A['DEF'] -= W['ATK']
    if A['HP'] <= 0:
        state['winer'] = 'player2'
        msgs.append(f'{A["name"]} 血量见底！')
        msgs = ['\n\n'.join(msgs)]
        return msgs
    elif W['HP'] <= 0:
        state['winer'] = 'player1'
        msgs.append(f'{W["name"]} 血量见底！')
        msgs = ['\n\n'.join(msgs)]
        return msgs
    if W['HP'] >= 45 and HP_Max:
        state['winer'] = 'player2'
        msgs.append(f'{W["name"]} 肉身成圣！')
        msgs = ['\n\n'.join(msgs)]
        return msgs
    if not state['deck']:
        state['winer'] = 'player1' if A['HP'] > W['HP'] else 'player2'
        msgs.append(f'牌库已空，正在统计结果...')
        msgs = ['\n\n'.join(msgs)]
        return msgs
    if A['ATK']: A['suck'] = 0
    if W['DEF'] > 10: W['DEF'] = 10.0
    elif W['DEF'] > 2: W['DEF'] -= 2
    elif W['DEF'] < -2: W['DEF'] += 2
    else: W['DEF'] = 0.0
    if W['ATK']: W['suck'] = 0
    A['ATK'] = 0
    W['ATK'] = 0
    A['hand'] = []
    W['SP'] += 2
    if W['SP'] > -1:
        state['player1'], state['player2'] = W, A
        msgs = ['\n\n'.join(msgs)]
        return msgs
    elif A['SP'] > -1:
        msgs.append(f"{W['name']}的技能点小于0，触发力竭，取消下次行动回合并回复为5点技能点")
        W['SP'] = 5
        msgs = ['\n\n'.join(msgs)]
        return msgs
    else:
        msgs.append(f"双方技能点均小于0，触发力竭，均取消下次行动回合并回复为5点技能点")
        W['SP'] = 5
        A['SP'] = 5
        state['player1'], state['player2'] = W, A
        msgs = ['\n\n'.join(msgs)]
        return msgs


async def info_show(state: PokerState) -> str:
    '发牌及信息输出'
    if not state['deck'] and not state['winer']:
        state['deck'] = await random_poker(1)
        msg = f"\n此次对决由 {state['player1']['name']} 先手\n{state['player2']['name']} 获得 5 点 DEF\n-----\n"
    else: msg = f"\n现在是{state['player1']['name']}的回合\n-----\n"

    suits = {1: "♠防御", 2: "♥恢复", 3: "♣技能", 4: "♦攻击"}
    if state['winer']:
        msg = f'对决已结束，{state[state["winer"]]["name"]} 获得胜利！\n-----\n'
    else:
        state['player1']['hand'] = state['deck'][:3] if len(state['deck']) > 2 else state['deck']
        state['deck'] = state['deck'][3:] if len(state['deck']) > 2 else []
    if state['player1']['HP'] >= 45: HP1 = f">{(state['player1']['HP']):.2f}<"
    else: HP1 = f"{(state['player1']['HP']):.2f}"
    msg += f"{state['player1']['name']}:\nHP {HP1}    SP {state['player1']['SP']}    DEF {state['player1']['DEF']}\n"
    msg += '-----\n'
    if state['player2']['HP'] >= 45: HP2 = f">{(state['player2']['HP']):.2f}<"
    else: HP2 = f"{(state['player2']['HP']):.2f}"
    msg += f"{state['player2']['name']}:\nHP {HP2}    SP {state['player2']['SP']}    DEF {state['player2']['DEF']}\n"
    if state['winer']:
        msg += f"-----\n点击按钮再来一局"
        return msg
    msg += f"-----\n{state['player1']['name']} 手牌如下(剩{len(state['deck'])}张)：\n"
    for i in state['player1']['hand']: msg += f'{suits[i[0]]}{i[1]}  ' if i[1] != 1 else f'{suits[i[0]]}A  '
    msg += '\n出牌 1/2/3'
    return msg

