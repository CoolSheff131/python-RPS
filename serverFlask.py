import enum
from enum import IntEnum

import eventlet
import pydantic
import json
import copy
import itertools
import numpy as np
from model import KeyPointClassifier
import socketio


# Действия пользователя
class Action(IntEnum):
    Paper = 0
    Rock = 1
    Scissors = 2
    Undefined = 777
    Unrecognized = 666


# Кто кого побеждает
victories = {
    Action.Scissors: [Action.Paper],
    Action.Paper: [Action.Rock],
    Action.Rock: [Action.Scissors],
}

sio = socketio.Server(cors_allowed_origins='*')
app = socketio.WSGIApp(sio)


class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)


class Point(pydantic.BaseModel):
    x: float
    y: float
    z: float


keypoint_classifier = KeyPointClassifier()


def calc_landmark_list(landmarks, image_width=640, image_height=480):
    landmark_point = []
    for _, landmark in enumerate(landmarks):  # Keypoint
        landmark_x = min(int(landmark['x'] * image_width), image_width - 1)
        landmark_y = min(int(landmark['y'] * image_height), image_height - 1)
        landmark_point.append([landmark_x, landmark_y])
    return landmark_point


def pre_process_landmark(landmark_list):
    temp_landmark_list = copy.deepcopy(landmark_list)
    base_x, base_y = 0, 0  # Convert to relative coordinates
    for index, landmark_point in enumerate(temp_landmark_list):
        if index == 0:
            base_x, base_y = landmark_point[0], landmark_point[1]
        temp_landmark_list[index][0] = temp_landmark_list[index][0] - base_x
        temp_landmark_list[index][1] = temp_landmark_list[index][1] - base_y
    temp_landmark_list = list(  # Convert to a one-dimensional list
        itertools.chain.from_iterable(temp_landmark_list))
    max_value = max(list(map(abs, temp_landmark_list)))  # Normalization

    def normalize_(n):
        return n / max_value

    temp_landmark_list = list(map(normalize_, temp_landmark_list))
    return temp_landmark_list


players = {}
isGameStarted = False


@sio.event
def getGameStatus(sid):
    sio.emit('gameStatusChange', isGameStarted)


@sio.event
def connect(sid, environ):
    print('connect ', sid)
    players[sid] = {
        'ready': False,
        'losed': isGameStarted,
        'hand_sign_id': Action.Undefined
    }
    print(players)
    sio.emit('playersChange', players)


@sio.event
def recognize(sid, data):
    coordinates = None
    if 'coordinates' in data:
        coordinates = data['coordinates']
    if coordinates is not None:
        landmark_list = calc_landmark_list(coordinates)
        pre_processed_landmark_list = pre_process_landmark(landmark_list)
        hand_sign_id = keypoint_classifier(pre_processed_landmark_list)
        if hand_sign_id == 1:
            hand_sign_id = Action.Rock
        elif hand_sign_id == 0:
            hand_sign_id = Action.Paper
        else:
            hand_sign_id = Action.Scissors
    else:
        hand_sign_id = Action.Rock

    players[sid]['hand_sign_id'] = hand_sign_id
    sio.emit('playersChange', players)


def gameResult():  # Определение победителя
    global isGameStarted
    isGameStarted = True
    playersInGame = list()
    for playerId, playerData in players.items():
        if not playerData['losed']:
            playersInGame.append(playerData)
    allPlayerRecognized = True

    for playerData in playersInGame:

        if playerData['hand_sign_id'] == Action.Undefined or playerData['hand_sign_id'] == Action.Unrecognized:
            allPlayerRecognized = False
        playerData['ready'] = False

    if not allPlayerRecognized:
        return
    playersSigns = set()

    for playerData in playersInGame:
        playersSigns.add(playerData['hand_sign_id'])

    if len(playersSigns) == 3 or len(playersSigns) == 1:  # Ничья (все показали 3 разных или одинаковый)
        return sio.emit('winner', None)

    firstPlayerSign = None
    secondPlayerSign = None
    for playerData in playersInGame:  # Определяем два знака которые показывают игроки
        playerSign = playerData['hand_sign_id']
        if firstPlayerSign is None:
            firstPlayerSign = playerSign
        if firstPlayerSign is not None and playerSign is not firstPlayerSign and secondPlayerSign is None:
            secondPlayerSign = playerSign
            break

    defeats = victories[firstPlayerSign]
    winnerSign = secondPlayerSign
    if secondPlayerSign in defeats:
        winnerSign = firstPlayerSign

    print(winnerSign)
    print(firstPlayerSign)
    print(secondPlayerSign)

    playerLosedCount = 0
    for playerData in playersInGame:  # Определяем два знака которые показывают игроки

        if playerData['hand_sign_id'] is not winnerSign:
            playerData['losed'] = True
            playerLosedCount = playerLosedCount + 1

    # Остался один не проигравший. Игра закончилась
    if playerLosedCount == len(playersInGame) - 1:
        isGameStarted = False
        sio.emit('gameStatusChange', isGameStarted)

    print(playersInGame)
    return sio.emit('playersChange', players)


@sio.event
def playerReady(sid):
    players[sid]['ready'] = True
    sio.emit('playersChange', players)
    for player in players.values():
        if not player['ready'] and not player['losed']:
            return

    # Если все готовы начинаем игру
    gameResult()


@sio.event
def restartGame(sid):
    global isGameStarted
    isGameStarted = False
    for playerId, playerData in players.items():
        playerData['losed'] = False


@sio.event
def disconnect(sid):
    print('disconnect ', sid)
    del players[sid]
    print(players)
    global isGameStarted

    for player in players.values():
        if not player['ready'] and not player['losed']:
            return

        # Если все готовы начинаем игру
    gameResult()

    playersInGame = list()
    for playerId, playerData in players.items():
        if not playerData['losed']:
            playersInGame.append(playerData)

    # Остался один не проигравший. Игра закончилась
    if len(playersInGame) > 1:
        isGameStarted = False   
        sio.emit('gameStatusChange', isGameStarted)
    sio.emit('playersChange', players)


if __name__ == '__main__':
    eventlet.wsgi.server(eventlet.listen(('', 5000)), app)
