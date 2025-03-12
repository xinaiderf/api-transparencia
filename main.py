from fastapi import FastAPI, File, UploadFile, BackgroundTasks
from fastapi.responses import FileResponse
import cv2
import numpy as np
import tempfile
import os
import uvicorn
import subprocess
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm  # Biblioteca para a barra de progresso
import shutil

app = FastAPI()

def extract_audio(video_path, audio_path):
    # Extrai o áudio do vídeo base usando ffmpeg
    command = [
        'ffmpeg', '-i', video_path, '-q:a', '0', '-map', 'a', audio_path, '-y'
    ]
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

def overlay_videos_with_audio(video_base_path, video_overlay_path, output_path, transparencia, temp_dir=None):
    # Carrega os vídeos
    cap_base = cv2.VideoCapture(video_base_path)
    cap_overlay = cv2.VideoCapture(video_overlay_path)

    # Obtém propriedades do vídeo base
    width = int(cap_base.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap_base.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap_base.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap_base.get(cv2.CAP_PROP_FRAME_COUNT))

    # Configura o escritor de vídeo
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    if temp_dir is None:
        temp_video_path = tempfile.mktemp(suffix='.mp4')
    else:
        temp_video_path = os.path.join(temp_dir, 'temp_video.mp4')
    out = cv2.VideoWriter(temp_video_path, fourcc, fps, (width, height))

    def process_frame(i):
        ret_base, frame_base = cap_base.read()
        ret_overlay, frame_overlay = cap_overlay.read()

        if not ret_base:
            return None
        if not ret_overlay:
            frame_overlay = np.zeros_like(frame_base)

        # Redimensiona o frame de sobreposição para o tamanho do frame base
        frame_overlay = cv2.resize(frame_overlay, (width, height))

        # Aplica a transparência
        blended_frame = cv2.addWeighted(frame_base, 1 - transparencia, frame_overlay, transparencia, 0)

        return blended_frame

    with ThreadPoolExecutor() as executor:
        for i in tqdm(range(frame_count), desc="Processando vídeo", unit="frame"):
            blended_frame = process_frame(i)
            if blended_frame is not None:
                out.write(blended_frame)

    # Libera os recursos
    cap_base.release()
    cap_overlay.release()
    out.release()

    # Extrai o áudio do vídeo base
    if temp_dir is None:
        temp_audio_path = tempfile.mktemp(suffix='.mp3')
    else:
        temp_audio_path = os.path.join(temp_dir, 'temp_audio.mp3')
    extract_audio(video_base_path, temp_audio_path)

    # Combina o vídeo processado com o áudio original
    command = [
        'ffmpeg', '-i', temp_video_path, '-i', temp_audio_path,
        '-c:v', 'copy', '-c:a', 'aac', '-strict', 'experimental',
        output_path, '-y'
    ]
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    # Remove os arquivos temporários criados nesta função
    os.remove(temp_video_path)
    os.remove(temp_audio_path)

@app.post("/overlay/")
async def overlay_api(
    video_base: UploadFile = File(...),
    video_overlay: UploadFile = File(...),
    transparencia: float = 0.05,
    background_tasks: BackgroundTasks = None
):
    # Cria uma pasta temporária para armazenar os arquivos
    temp_folder = tempfile.mkdtemp()
    temp_video_base = os.path.join(temp_folder, 'video_base.mp4')
    temp_video_overlay = os.path.join(temp_folder, 'video_overlay.mp4')
    temp_output_video = os.path.join(temp_folder, 'output.mp4')

    # Salva os vídeos enviados na pasta temporária
    with open(temp_video_base, "wb") as f:
        f.write(await video_base.read())
    with open(temp_video_overlay, "wb") as f:
        f.write(await video_overlay.read())

    try:
        overlay_videos_with_audio(temp_video_base, temp_video_overlay, temp_output_video, transparencia, temp_dir=temp_folder)
        # Agenda a remoção da pasta temporária após o envio da resposta
        if background_tasks:
            background_tasks.add_task(shutil.rmtree, temp_folder)
        return FileResponse(temp_output_video, media_type='video/mp4', filename='output.mp4')
    except Exception as e:
        # Em caso de erro, remove a pasta temporária imediatamente
        shutil.rmtree(temp_folder, ignore_errors=True)
        return {"error": str(e)}

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8010)
