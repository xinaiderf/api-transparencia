import os
import cv2
import tempfile
import numpy as np
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse
import subprocess

app = FastAPI()

def overlay_videos(video_base_path, video_overlay_path, output_path):
    """Aplica um overlay no vídeo base sem alterar o áudio."""
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

def copy_audio(source_video, target_video):
    """ Mantém o áudio original do vídeo base no vídeo final. """
    temp_output = target_video.replace(".mp4", "_audio.mp4")
    command = [
        "ffmpeg", "-i", target_video, "-i", source_video,
        "-c", "copy", "-map", "0:v:0", "-map", "1:a:0",
        "-y", temp_output
    ]
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    os.replace(temp_output, target_video)

@app.post("/overlay/")
async def overlay_api(video_base: UploadFile = File(...), video_overlay: UploadFile = File(...)):
    temp_video_base = tempfile.mktemp(suffix='.mp4')
    temp_video_overlay = tempfile.mktemp(suffix='.mp4')
    temp_output_video = tempfile.mktemp(suffix='.mp4')

    with open
