import os
import cv2
import tempfile
import numpy as np
import subprocess
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse

app = FastAPI()

def apply_overlay(video_base_path, video_overlay_path, output_video_no_audio):
    """Aplica o vídeo overlay sobre o vídeo base com 5% de transparência e mantém o tamanho original."""

    cap_base = cv2.VideoCapture(video_base_path)
    cap_overlay = cv2.VideoCapture(video_overlay_path)

    fps = cap_base.get(cv2.CAP_PROP_FPS)
    frame_width = int(cap_base.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap_base.get(cv2.CAP_PROP_FRAME_HEIGHT))

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Codec compatível com OpenCV
    out = cv2.VideoWriter(output_video_no_audio, fourcc, fps, (frame_width, frame_height))

    while cap_base.isOpened():
        ret_base, frame_base = cap_base.read()
        ret_overlay, frame_overlay = cap_overlay.read()

        if not ret_base:
            break  # Fim do vídeo base

        if ret_overlay:
            frame_overlay_resized = cv2.resize(frame_overlay, (frame_width, frame_height))
            frame_final = cv2.addWeighted(frame_base, 1.0, frame_overlay_resized, 0.05, 0)
        else:
            frame_final = frame_base  # Se o overlay acabar, mantém o vídeo base puro

        out.write(frame_final)

    cap_base.release()
    cap_overlay.release()
    out.release()

    if not os.path.exists(output_video_no_audio):
        raise FileNotFoundError("Erro ao gerar o vídeo sem áudio.")


def merge_audio(video_base_path, video_no_audio_path, output_final_path):
    """Copia o áudio original do vídeo base e adiciona ao vídeo processado, sem reprocessar."""
    temp_output = output_final_path.replace(".mp4", "_temp.mp4")

    command = [
        "ffmpeg", "-i", video_no_audio_path, "-i", video_base_path,
        "-c:v", "copy", "-c:a", "copy", "-map", "0:v:0", "-map", "1:a:0",
        "-y", temp_output
    ]
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    os.replace(temp_output, output_final_path)


@app.post("/overlay/")
async def overlay_api(video_base: UploadFile = File(...), video_overlay: UploadFile = File(...)):
    """Recebe dois vídeos e retorna o vídeo final com overlay e áudio original."""

    temp_video_base = tempfile.mktemp(suffix='.mp4')
    temp_video_overlay = tempfile.mktemp(suffix='.mp4')
    temp_video_no_audio = tempfile.mktemp(suffix='.mp4')
    temp_output_video = tempfile.mktemp(suffix='.mp4')

    try:
        with open(temp_video_base, "wb") as f:
            f.write(await video_base.read())

        with open(temp_video_overlay, "wb") as f:
            f.write(await video_overlay.read())

        apply_overlay(temp_video_base, temp_video_overlay, temp_video_no_audio)
        merge_audio(temp_video_base, temp_video_no_audio, temp_output_video)

        return FileResponse(temp_output_video, media_type='video/mp4', filename="output.mp4")

    except Exception as e:
        return {"error": str(e)}

    finally:
        for file in [temp_video_base, temp_video_overlay, temp_video_no_audio, temp_output_video]:
            if os.path.exists(file):
                os.remove(file)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
