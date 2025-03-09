import os
import cv2
import tempfile
import numpy as np
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse
from pydub import AudioSegment

app = FastAPI()

def extract_audio(video_path, audio_path):
    """ Extrai o áudio do vídeo base e salva como um arquivo separado. """
    cap = cv2.VideoCapture(video_path)
    audio = AudioSegment.from_file(video_path, format="mp4")  
    audio.export(audio_path, format="mp3")
    cap.release()

def add_audio_to_video(video_path, audio_path, output_path):
    """ Insere o áudio extraído de volta ao vídeo final. """
    video = AudioSegment.from_file(video_path, format="mp4")
    audio = AudioSegment.from_file(audio_path, format="mp3")
    video = video.set_frame_rate(audio.frame_rate).overlay(audio)
    video.export(output_path, format="mp4")

def overlay_videos(video_base_path, video_overlay_path, output_path):
    """ Aplica o overlay no vídeo base e mantém o áudio original. """
    cap_base = cv2.VideoCapture(video_base_path)
    cap_overlay = cv2.VideoCapture(video_overlay_path)

    fps = cap_base.get(cv2.CAP_PROP_FPS)
    frame_width = int(cap_base.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap_base.get(cv2.CAP_PROP_FRAME_HEIGHT))

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (frame_width, frame_height))

    while cap_base.isOpened():
        ret_base, frame_base = cap_base.read()
        ret_overlay, frame_overlay = cap_overlay.read()

        if not ret_base:
            break

        if ret_overlay:
            frame_overlay_resized = cv2.resize(frame_overlay, (frame_width, frame_height))
            frame_final = cv2.addWeighted(frame_base, 1.0, frame_overlay_resized, 0.15, 0)
        else:
            frame_final = frame_base  # Continua com o vídeo base caso o overlay termine

        out.write(frame_final)

    cap_base.release()
    cap_overlay.release()
    out.release()

@app.post("/overlay/")
async def overlay_api(video_base: UploadFile = File(...), video_overlay: UploadFile = File(...)):
    temp_video_base = tempfile.mktemp(suffix='.mp4')
    temp_video_overlay = tempfile.mktemp(suffix='.mp4')
    temp_output_video = tempfile.mktemp(suffix='.mp4')
    temp_audio_path = tempfile.mktemp(suffix='.mp3')

    with open(temp_video_base, "wb") as f:
        f.write(await video_base.read())

    with open(temp_video_overlay, "wb") as f:
        f.write(await video_overlay.read())

    try:
        extract_audio(temp_video_base, temp_audio_path)  # Extrai o áudio
        overlay_videos(temp_video_base, temp_video_overlay, temp_output_video)  # Faz o overlay
        add_audio_to_video(temp_output_video, temp_audio_path, temp_output_video)  # Adiciona o áudio de volta

        return FileResponse(temp_output_video, media_type='video/mp4', filename="output.mp4")
    except Exception as e:
        return {"error": str(e)}
    finally:
        os.remove(temp_video_base)
        os.remove(temp_video_overlay)
        os.remove(temp_audio_path)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
