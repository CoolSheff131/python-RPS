
import { Camera } from '@mediapipe/camera_utils';
import { drawConnectors, drawLandmarks } from '@mediapipe/drawing_utils';
import { Hands, HAND_CONNECTIONS } from '@mediapipe/hands';
import React from 'react';
import { io } from 'socket.io-client';
import './App.css';
const IP = 'localhost';

const socket = io(`ws://${IP}:5000`);
const figures = {
  0: '🤚',
  1: '🤜',
  2: '✌️',
  666: 'Не распознано',
  777: 'Не начато распознанование',
} as const;

interface IPlayer { hand_sign_id: keyof typeof figures, ready: boolean, losed: boolean }

type IPlayerData = Record<string, IPlayer>
function App() {

  const [mySocketId, setMySocketId] = React.useState('');


  const [players, setPlayers] = React.useState<IPlayerData>({})

  const [title, setTitle] = React.useState('');
  const [figure, setFigure] = React.useState('');
  const [isReadyDisabled, setIsReadyDisabled] = React.useState(false);
  const [isRestartDisabled, setIsRestartDisabled] = React.useState(false);
  const [isStarted, setIsStarted] = React.useState(false);


  const canvasRef = React.useRef<HTMLCanvasElement>(null);
  const videoRef = React.useRef<HTMLVideoElement>(null);

  const hands = new Hands({
    locateFile: file => {
      return `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`;
    },
  });

  hands.setOptions({
    maxNumHands: 2,
    modelComplexity: 1,
    minDetectionConfidence: 0.5,
    minTrackingConfidence: 0.5,
  });

  const handleReadyClick = () => {
    socket.emit('playerReady');
    setIsReadyDisabled(true)
  }
  const handleRestartClick = () => {
    socket.emit('restartGame');
    setIsRestartDisabled(true)
  }



  React.useEffect(() => {
    socket.connect()
    socket.on('playersChange', (data: IPlayerData) => {
      setPlayers(data);
      setMySocketId(socket.id);

      const figureId = data[socket.id].hand_sign_id;
      setFigure(figures[figureId]);
    });

    socket.on('gameStatusChange', isStarted => {
      setIsStarted(isStarted)
      console.log(isStarted)
      if (isStarted) {




      } else {

      }
    });

    socket.on('winner', data => {
      setIsReadyDisabled(false)

      if (!data) {
        setTitle(() => 'Ничья')

      } else if (socket.id === data) {
        setTitle(() => 'Победа')
      } else {
        setTitle(() => 'Поражение')
      }
    });

    return () => {
      socket.off('winner')
      socket.off('gameStatusChange')
      socket.off('playersChange')
      socket.disconnect()
    }
  }, [])


  React.useEffect(() => {

    hands.onResults(results => {
      if (videoRef.current && canvasRef.current) {

        videoRef.current.style.display = 'none';
        canvasRef.current.style.display = 'block';
        const canvasCtx = canvasRef.current.getContext('2d') as CanvasRenderingContext2D
        canvasCtx.save();
        canvasCtx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
        canvasCtx.drawImage(
          results.image,
          0,
          0,
          canvasRef.current.width,
          canvasRef.current.height,
        );

        if (results.multiHandLandmarks) {
          for (const landmarks of results.multiHandLandmarks) {
            drawConnectors(canvasCtx, landmarks, HAND_CONNECTIONS, {
              color: '#00FF00',
              lineWidth: 5,
            });
            drawLandmarks(canvasCtx, landmarks, {
              color: '#00AA00',
              lineWidth: 2,
            });
          }
        }

        socket.emit('recognize', { coordinates: results.multiHandLandmarks[0] });

        canvasCtx.restore();
      }
    });





    const camera = new Camera(videoRef.current!, {
      onFrame: async () => {
        await hands.send({ image: videoRef.current! });
      },
      width: 640,
      height: 480,
    });
    camera.start();


  }, [videoRef, canvasRef])



  return (
    <div className="App">
      <div className="container">
        <h3>Список игроков</h3>
        <h1>{isStarted ? 'Начата' : 'Не начата'}</h1>
        <ul id="players">
          {
            Object.entries(players).map(
              ([playerName, { hand_sign_id, ready, losed }]) => {
                return <div key={playerName}>
                  {mySocketId === playerName && 'Это вы: '} {playerName} {ready ? ' готов' : ' не готов'} {hand_sign_id === 666 || hand_sign_id === 777 ? '. Не распознано' : '. Распознано'} {losed && '.Проиграл'}
                </div>
              }
            )
          }
        </ul>
        {/* <h1 className="title">{title}</h1> */}
        <div>
          <div>Вы показываете:</div>
          <h2 className="figure">{figure}</h2>
        </div>

        <img src="" />
        <img src="" />
        <video
          ref={videoRef}

        ></video>
        <canvas
          ref={canvasRef}
          width="640px"
          height="480px"
          style={{ "display": "none" }}
        ></canvas>
        <div>
          <button onClick={() => handleReadyClick()} type="button" className="btn btn-primary" >
            Ready
          </button>
        </div>

        <div>
          <button onClick={() => handleRestartClick()} type="button" className="btn btn-primary" >
            Restart
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;
