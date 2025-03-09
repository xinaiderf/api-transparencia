import os
import cv2
import tempfile
import numpy as np
import ffmpeg
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse

app = FastAPI()

def overlay_videos(video_base_path, video_overlay_path, output_video_no_audio):
    """Aplica overlay sem alterar a resolução e sem áudio."""
    
    # Abrindo os vídeos com OpenCV
    cap_base = cv2.VideoCapture(video_base_path)
    cap_overlay = cv2.VideoCapture(video_overlay_path)

    fps = cap_base.get(cv2.CAP_PROP_FPS)
    frame_width = int(cap_base.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap_base.get(cv2.CAP_PROP_FRAME_HEIGHT))

    fourcc = cv2.VideoWriter_fourcc(*'avc1')  # Codec compatível
    out = cv2.VideoWriter(output_video_no_audio, fourcc, fps, (frame_width, frame_height))

    while cap_base.isOpened():
        ret_base, frame_base = cap_base.read()
        ret_overlay, frame_overlay = cap_overlay.read()

        if not ret_base:
            break

        if ret_overlay:
            frame_overlay_resized = cv2.resize(frame_overlay, (frame_width, frame_height))
            frame_final = cv2.addWeighted(frame_base, 1.0, frame_overlay_resized, 0.15, 0)
        else:
            frame_final = frame_base  # Se o overlay acabar, continua apenas com o vídeo base

        out.write(frame_final)

    cap_base.release()
    cap_overlay.release()
    out.release()


def add_original_audio(video_base_path, video_no_audio_path, output_final_path):
    """Copia o áudio original para o vídeo final sem reprocessamento."""
    ffmpeg.input(video_no_audio_path).output(
        output_final_path, 
        vcodec="copy",  # Mantém o vídeo sem reprocessar
        acodec="copy",  # Mantém o áudio original sem perda de qualidade
        map="0:v:0",  # Usa o vídeo do arquivo sem áudio
        map="1:a:0"   # Usa o áudio do vídeo base
    ).run(overwrite_output=True)


@app.post("/overlay/")
async def overlay_api(video_base: UploadFile = File(...), video_overlay: UploadFile = File(...)):
    temp_video_base = tempfile.mktemp(suffix='.mp4')
    temp_video_overlay = tempfile.mktemp(suffix='.mp4')
    temp_video_no_audio = tempfile.mktemp(suffix='.mp4')
    temp_output_video = tempfile.mktemp(suffix='.mp4')

    try:
        # Salvar arquivos temporários corretamente
        with open(temp_video_base, "wb") as f:
            f.write(await video_base.read())

        with open(temp_video_overlay, "wb") as f:
            f.write(await video_overlay.read())

        # Aplicar overlay sem áudio
        overlay_videos(temp_video_base, temp_video_overlay, temp_video_no_audio)

        # Adicionar áudio original sem reprocessamento
        add_original_audio(temp_video_base, temp_video_no_audio, temp_output_video)

        return FileResponse(temp_output_video, media_type='video/mp4', filename="output.mp4")
    
    except Exception as e:
        return {"error": str(e)}
    
    finally:
        os.remove(temp_video_base)
        os.remove(temp_video_overlay)
        os.remove(temp_video_no_audio)
        if os.path.exists(temp_output_video):
            os.remove(temp_output_video)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
