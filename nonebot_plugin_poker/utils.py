import random, time
from typing import Dict, List, Tuple, Union
from nonebot.adapters.onebot.v11 import GroupMessageEvent


PokerState = Dict[str, Union[int, str, float, List[Tuple[int, int]], Dict[str, Union[int, str, float, List[Tuple[int, int]]]]]]


async def msg_at(event: GroupMessageEvent) -> int:
    '获取被at的第一个qq号'
    qq = 0
    for msg in event.message:
        if msg.type == 'at':
            qq = msg.data['qq']
            break
    return qq


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
                    A['DEF'] += point/2
                    A['ATK'] += point/2
                    msg += f'\n♠{point}发动了盾击，造成{point/2}伤害且防御提高{point/2}'
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
                    if A['ATK'] > W['DEF']:
                        if A['DEF'] > point: A['DEF'] -= point
                        else: A['DEF'] = 0.0
                        msg += f'，受伤时使对方防御降低{point}'
                case 2:
                    W['HP'] += point/2
                    msg += f'\n♥{point}发动了再生，生命回复{point/2}'
                    if A['ATK'] > W['DEF']:
                        W['HP'] += point
                        msg += f'，本回合受击回复{point}'
                case 3:
                    A['SP'] -= point
                    W['SP'] += point
                    msg += f'\n♣{point}发动了打断，此卡不消耗技能点并扣除了对方技能点{point}'
                case 4:
                    W['ATK'] += point/2
                    msg += f'\n♦{point}发动了反击，造成{point/2}伤害并获得50%反伤'
            if W['SP'] < 0: W['SP'] = 0
    msgs.append(msg)
    msg = ''
    

    # 回合结算
    HP_Max = W['HP'] >= 45
    if A['ATK'] > W['DEF']:
        W['HP'] -= A['ATK'] - W['DEF'] # 伤害
        A['HP'] += A['suck']*(A['ATK'] - W['DEF']) # 吸血
        if W['ATK']: A['HP'] -= (A['ATK'] - W['DEF'])/2 # 反伤
        W['DEF'] = 0.0
    else: W['DEF'] -= A['ATK']
    if W['ATK'] > A['DEF']:
        A['HP'] -= W['ATK'] - A['DEF'] # 反击
        W['HP'] += W['suck']*(W['ATK'] - A['DEF']) # 吸血
        A['DEF'] = 0.0
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
    else:
        if W['DEF'] > 2: W['DEF'] -= 2
        else: W['DEF'] = 0.0
    if W['ATK']: W['suck'] = 0
    A['ATK'] = 0
    W['ATK'] = 0
    A['hand'] = []
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

