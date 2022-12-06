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

class Action(IntEnum):
    Rock = 0
    Paper = 1
    Scissors = 2
    Undefined = 777
    Unrecognized = 666

victories = {
    Action.Scissors: [Action.Paper],
    Action.Paper: [Action.Rock],
    Action.Rock: [Action.Scissors],
}

def determine_winner(first_user_action, second_user_action):

    defeats = victories[first_user_action]
    if first_user_action == second_user_action: # Ничься
        return 0
    elif second_user_action in defeats:
        return 2 # Первый победил
    else:
        return 1 # Второй победил

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


def calc_landmark_list(landmarks, image_width = 640, image_height = 480):
    # image_width, image_height = image.shape[1], image.shape[0]

    landmark_point = []

    # Keypoint
    for _, landmark in enumerate(landmarks):
        landmark_x = min(int(landmark['x'] * image_width), image_width - 1)
        landmark_y = min(int(landmark['y'] * image_height), image_height - 1)
        # landmark_z = landmark.z

        landmark_point.append([landmark_x, landmark_y])

    return landmark_point

def pre_process_landmark(landmark_list):
    temp_landmark_list = copy.deepcopy(landmark_list)

    # Convert to relative coordinates
    base_x, base_y = 0, 0
    for index, landmark_point in enumerate(temp_landmark_list):
        if index == 0:
            base_x, base_y = landmark_point[0], landmark_point[1]

        temp_landmark_list[index][0] = temp_landmark_list[index][0] - base_x
        temp_landmark_list[index][1] = temp_landmark_list[index][1] - base_y

    # Convert to a one-dimensional list
    temp_landmark_list = list(
        itertools.chain.from_iterable(temp_landmark_list))

    # Normalization
    max_value = max(list(map(abs, temp_landmark_list)))

    def normalize_(n):
        return n / max_value

    temp_landmark_list = list(map(normalize_, temp_landmark_list))

    return temp_landmark_list

players = {}

@sio.event
def connect(sid, environ):
    print('connect ', sid)
    print(players)
    players[sid] = {
        'ready': False,
        'hand_sign_id': Action.Undefined
    }

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
        if hand_sign_id == 0:
            hand_sign_id = Action.Rock
        elif hand_sign_id == 1:
            hand_sign_id = Action.Paper
        else:
            hand_sign_id = Action.Scissors
    else:
        hand_sign_id = Action.Rock


    players[sid]['hand_sign_id'] = hand_sign_id

    # isFirstRecognize = players[sid]['hand_sign_id'] == Action.Undefined
    # sio.emit('recognizeResult', json_str)
    # if isFirstRecognize:
    # json_str = json.dumps({'data': players }, cls=NpEncoder)
    sio.emit('playersChange', players)


@sio.event
def playerReady(sid):
    players[sid]['ready'] = True
    sio.emit('playersChange', players)
    for player in players.values():
        if not player['ready']:
            return
    sio.emit('gameStarted')

@sio.event
def disconnect(sid):
    print('disconnect ', sid)
    del players[sid]
    print(players)
    sio.emit('playersChange', players)

@sio.event
def gameResult(sid):
    playerValues = list(players.values())
    firstAction = playerValues[0]['hand_sign_id']
    secondAction = playerValues[1]['hand_sign_id']
    winner = determine_winner(firstAction,secondAction)
    print(firstAction)
    print(secondAction)
    print(winner)
    if winner == 0:
        return sio.emit('winner', None)

    return sio.emit('winner', list(players.keys())[winner - 1])


if __name__ == '__main__':
    eventlet.wsgi.server(eventlet.listen(('', 5000)), app)